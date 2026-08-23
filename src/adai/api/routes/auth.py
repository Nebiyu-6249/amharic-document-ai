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
from adai.db import get_auth_sessionmaker, get_session, set_rls_context
from adai.logging import get_logger
from adai.models import User
from adai.schemas import LoginRequest, RegisterRequest, UserOut
from adai.security.audit import record_audit_event
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
    # Generate the id up front and scope the transaction to it before inserting.
    # SQLAlchemy appends RETURNING for the server-side created_at default, and RETURNING
    # is evaluated against the SELECT policy -- with no context set, the row we just
    # wrote would be invisible and the INSERT would fail. Scoping to the new user's own
    # id is also semantically right: for the rest of this transaction, that is who we are.
    new_id = uuid.uuid4()
    await set_rls_context(session, new_id)
    user = User(id=new_id, email=payload.email.lower(), password_hash=encoded)
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        # Address already registered. Same response, same status, same shape.
        await record_audit_event(session, event_type="register", outcome="duplicate")
        log.info("register", outcome="duplicate")
        return _GENERIC_ACCEPTED
    await record_audit_event(
        session, event_type="register", outcome="success", actor_user_id=user.id
    )
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
    # Pre-authentication lookup on the narrowly-scoped auth connection: there is no
    # identity yet, so the request session (subject to RLS) cannot see the row.
    stmt = select(User).where(User.email == payload.email.lower())
    async with get_auth_sessionmaker()() as auth_session:
        user = (await auth_session.execute(stmt)).scalar_one_or_none()

    # verify_password runs the Argon2 verify even when user is None, against a dummy
    # hash, so a missing account costs the same as a wrong password (C-12).
    ok = verify_password(payload.password, user.password_hash if user else None)
    if not ok or user is None or not user.is_active:
        await record_audit_event(
            session, event_type="login", outcome="failure", actor_user_id=user.id if user else None
        )
        log.info("login", outcome="failure")
        return {"status": "rejected", "detail": _GENERIC_REJECTED}

    # Scope the request session to the now-authenticated user before writing anything.
    await set_rls_context(session, user.id)
    _set_session_cookie(response, issue_session(user, settings), settings)
    await record_audit_event(session, event_type="login", outcome="success", actor_user_id=user.id)
    log.info("login", outcome="success")
    return {"status": "ok"}


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(current_user)]) -> User:
    return user
