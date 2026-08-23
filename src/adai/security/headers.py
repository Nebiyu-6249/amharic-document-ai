"""Security response headers and HTTPS enforcement (controls C-01, C-02, C-03).

CSP uses a per-response nonce and never ``unsafe-inline``. The nonce is exposed on
``request.state.csp_nonce`` so a template can stamp it onto any script tag it emits.
"""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

_PERMISSIONS_POLICY = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), "
    "microphone=(), payment=(), usb=()"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds the full header set and, optionally, redirects plain HTTP."""

    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        *,
        force_https: bool,
        hsts_max_age: int,
    ) -> None:
        super().__init__(app)
        self.force_https = force_https
        self.hsts_max_age = hsts_max_age

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if self.force_https and forwarded_proto == "http":
            https_url = request.url.replace(scheme="https")
            return RedirectResponse(str(https_url), status_code=308)

        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce
        response = await call_next(request)

        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "font-src 'self'; "
            "object-src 'none'; "
            "base-uri 'none'; "
            "form-action 'self'; "
            "frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = _PERMISSIONS_POLICY
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        # The Server header is suppressed at the uvicorn layer
        # (--no-server-header); setting one here would only duplicate it.
        if self.force_https and forwarded_proto == "https":
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains"
            )
        return response
