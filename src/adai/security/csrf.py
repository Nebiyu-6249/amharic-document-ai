"""CSRF protection: synchroniser token pattern (control C-08, threat T-11).

THREAT_MODEL.md section 6.1 argues the choice. In short: double-submit rests on the
assumption that an attacker cannot write cookies for our domain, and a sibling subdomain
can. We already run Redis for the queue and rate limiting, so server-side tokens cost
nothing we are not already paying, and they do not depend on an assumption we cannot
enforce.

The token is bound to the session id, stored in Redis with a TTL, and compared in
constant time. `SameSite=Lax` (C-07) already blocks most CSRF; this covers what it does
not -- top-level POST navigations and clients with weak SameSite defaults.
"""

from __future__ import annotations

import hmac
import secrets
from typing import Final

from redis.asyncio import Redis

#: Tokens outlive a form sitting open but not a working day.
TOKEN_TTL_SECONDS: Final[int] = 60 * 60 * 8
_KEY_PREFIX: Final[str] = "csrf:"
#: Methods that change state and therefore require a token.
UNSAFE_METHODS: Final[frozenset[str]] = frozenset({"POST", "PUT", "PATCH", "DELETE"})
CSRF_HEADER: Final[str] = "x-csrf-token"


def _key(session_id: str) -> str:
    return f"{_KEY_PREFIX}{session_id}"


async def issue_token(redis: Redis, session_id: str) -> str:
    """Mint and store a CSRF token bound to this session."""
    token = secrets.token_urlsafe(32)
    await redis.setex(_key(session_id), TOKEN_TTL_SECONDS, token)
    return token


async def validate_token(redis: Redis, session_id: str, presented: str | None) -> bool:
    """Constant-time comparison against the stored token.

    Returns False for a missing session, a missing token, or a mismatch -- never raises,
    so a caller cannot accidentally treat an error as a pass.
    """
    if not presented or not session_id:
        return False
    stored = await redis.get(_key(session_id))
    if stored is None:
        return False
    stored_str = stored.decode() if isinstance(stored, bytes) else str(stored)
    return hmac.compare_digest(stored_str, presented)


async def revoke_token(redis: Redis, session_id: str) -> None:
    """Drop the token, e.g. on logout or password change."""
    await redis.delete(_key(session_id))
