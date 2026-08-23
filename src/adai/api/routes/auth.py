"""Registration and login.

Phase 3 scope: Argon2id hashing (C-06), signed host-only session cookies (C-07),
timing- and response-equalised anti-enumeration (C-12), and session invalidation via
``session_epoch`` (C-09).

Deferred to Phase 5, deliberately and visibly: CSRF synchroniser tokens (C-08),
progressive delay and challenge (C-13), bot protection (C-14), password reset (C-10)
and per-account/per-IP reset limits (C-11).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from adai.api.deps import SESSION_COOKIE, SESSION_MAX_AGE, current_user, issue_session
from adai.config import Settings, get_settings
from adai.db import get_session
from adai.logging import get_logger
from adai.models import AuditEvent, User
from adai.schemas import LoginRequest, RegisterRequest, UserOut
from adai.security.passwords import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger("adai.auth")

#: Identical for success and failure on both register and login. Anything that differs
#: between "account exists" and "account does not exist" is an enumeration oracle (T-09).
_GENERIC_ACCEPTED = {"status": "accepted"}
_GENERIC_REJECTED = "invalid credentials"


def _set_session_cookie(response: Response, value: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        value,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=settings.force_https,
        samesite="lax",
        path="/",
        # No domain= : the cookie stays host-only, so a sibling subdomain cannot read
        # or overwrite it.
    )


async def _audit(
    session: AsyncSession, event_type: str, outcome: str, user_id: uuid.UUID | None = None
) -> None:
    session.add(
        AuditEvent(
            event_type=event_type,
            outcome=outcome,
            actor_user_id=user_id,
            detail={},
        )
    )


@router.post("/register", status_code=status.HTTP_202_ACCEPTED)
async def register(
    payload: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    """Register an account.

    Always returns 202 with the same body, whether or not the address was already
    registered. The password is hashed either way so the timing profile matches.
    """
    encoded = hash_password(payload.password)
    user = User(email=payload.email.lower(), password_hash=encoded)
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        # Address already registered. Same response, same status, same shape.
        await _audit(session, "register", "duplicate")
        log.info("register", outcome="duplicate")
        return _GENERIC_ACCEPTED
    await _audit(session, "register", "success", user.id)
    log.info("register", outcome="success")
    return _GENERIC_ACCEPTED


@router.post("/login")
async def login(
    payload: LoginRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    """Log in. Identical response and comparable timing for unknown vs wrong password."""
    stmt = select(User).where(User.email == payload.email.lower())
    user = (await session.execute(stmt)).scalar_one_or_none()

    # verify_password runs the Argon2 verify even when user is None, against a dummy
    # hash, so a missing account costs the same as a wrong password (C-12).
    ok = verify_password(payload.password, user.password_hash if user else None)
    if not ok or user is None or not user.is_active:
        await _audit(session, "login", "failure", user.id if user else None)
        log.info("login", outcome="failure")
        return {"status": "rejected", "detail": _GENERIC_REJECTED}

    _set_session_cookie(response, issue_session(user, settings), settings)
    await _audit(session, "login", "success", user.id)
    log.info("login", outcome="success")
    return {"status": "ok"}


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(current_user)]) -> User:
    return user
