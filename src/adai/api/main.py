"""FastAPI application factory.

This process contains NO machine-learning dependencies. That is control C-45 and it is
enforced by CI (``scripts/check_api_isolation.py``), not by good intentions: surya
would drag in pillow 10.4.0, which has 24 known CVEs, onto the exact code path that
decodes hostile uploads. See ADR-0007.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from adai import __version__
from adai.api.routes import auth, documents, health
from adai.config import get_settings
from adai.db import dispose_engine
from adai.logging import configure_logging, get_logger
from adai.queue import close_pool
from adai.security.headers import SecurityHeadersMiddleware

log = get_logger("adai.api")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(json_output=settings.environment != "dev")
    log.info("api_start", environment=settings.environment, version=__version__)
    yield
    await close_pool()
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Amharic Document AI",
        version=__version__,
        lifespan=lifespan,
        # No interactive docs outside dev: the schema is a map of the attack surface.
        docs_url="/docs" if settings.environment == "dev" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.environment == "dev" else None,
    )

    app.add_middleware(
        SecurityHeadersMiddleware,
        force_https=settings.force_https,
        hsts_max_age=settings.hsts_max_age,
    )
    # C-04: an explicit allowlist. Settings rejects "*", and the Origin header is
    # never reflected back.
    if settings.cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_allow_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["content-type", "x-csrf-token"],
            max_age=600,
        )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(documents.router)

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        """Never leak a stack trace or an internal message to a client (C-21)."""
        log.error("unhandled_exception", error_type=type(exc).__name__)
        return JSONResponse(
            status_code=500, content={"detail": "internal server error", "code": "internal"}
        )

    return app


configure_logging(json_output=False, level=logging.INFO)
app = create_app()
