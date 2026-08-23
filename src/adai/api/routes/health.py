"""Liveness and readiness."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from adai import __version__
from adai.db import get_session

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness. Deliberately does not touch the database."""
    return {"status": "ok", "version": __version__}


@router.get("/readyz")
async def readyz(session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, str]:
    """Readiness. Confirms the database is actually reachable."""
    await session.execute(text("SELECT 1"))
    return {"status": "ready"}
