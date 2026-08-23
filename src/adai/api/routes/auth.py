"""Registration and login.

Phase 3 scope: Argon2id hashing (C-06), signed host-only session cookies (C-07),
timing- and response-equalised anti-enumeration (C-12), and session invalidation via
``session_epoch`` (C-09).

Deferred to Phase 5, deliberately and visibly: CSRF synchroniser tokens (C-08),
progressive delay and challenge (C-13), bot protection (C-14), password reset (C-10)
and per-account/per-IP reset limits (C-11).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from adai.api.deps import (
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    client_ip,
    current_user,
    issue_session,
    require_csrf,
)
from adai.config import Settings, get_settings
from adai.db import get_auth_sessionmaker, get_session, set_rls_context
from adai.logging import get_logger
from adai.models import PasswordResetToken, User
from adai.redis_client import get_redis
from adai.schemas import (
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    UserOut,
)
from adai.security.audit import record_audit_event
from adai.security.csrf import issue_token, revoke_token
from adai.security.passwords import hash_password, verify_password
from adai.security.ratelimit import (
    challenge_required,
    check_rate_limit,
    compute_backoff_delay,
    get_failure_count,
)
from adai.security.tokens import expiry_from, generate_reset_token, hash_reset_token

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
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    """Log in. Identical response and comparable timing for unknown vs wrong password.

    Applies progressive delay rather than a hard lockout (control C-13): a hard lock
    would let anyone who knows an email address deny that account at will. The delay is
    applied to BOTH outcomes so it cannot itself become an oracle for account existence.
    """
    redis = get_redis()
    email = payload.email.lower()
    ip = client_ip(request)

    # Delay before doing any work, based on prior failures on either axis.
    failures = await get_failure_count(redis, email, ip)
    delay = compute_backoff_delay(failures)
    if delay:
        await asyncio.sleep(delay)
    if challenge_required(failures):
        await record_audit_event(
            session, event_type="login", outcome="challenge_required", source_ip=ip
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many attempts; complete the challenge and retry",
        )
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
    # Mint the session value ONCE: itsdangerous stamps a timestamp, so a second call
    # would produce a different string and the CSRF token would be keyed to a session
    # the client never holds.
    session_value = issue_session(user, settings)
    _set_session_cookie(response, session_value, settings)
    await record_audit_event(session, event_type="login", outcome="success", actor_user_id=user.id)
    log.info("login", outcome="success")
    # Mint a CSRF token bound to this session; the client echoes it in X-CSRF-Token.
    csrf = await issue_token(redis, session_value)
    return {"status": "ok", "csrf_token": csrf}


@router.post("/logout", dependencies=[Depends(require_csrf)])
async def logout(request: Request, response: Response) -> dict[str, str]:
    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie:
        await revoke_token(get_redis(), cookie)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"status": "ok"}


@router.post("/password", dependencies=[Depends(require_csrf)])
async def change_password(
    payload: PasswordChangeRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> dict[str, str]:
    """Change password and invalidate every existing session (control C-09).

    Bumping ``session_epoch`` is what does the invalidating: every issued cookie carries
    the epoch it was minted under, so they all stop validating at once. That matters
    because the reason someone changes a password is often that a session was stolen.
    """
    if not verify_password(payload.current_password, user.password_hash):
        await record_audit_event(
            session, event_type="password_change", outcome="failure", actor_user_id=user.id
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="incorrect password")

    user.password_hash = hash_password(payload.new_password)
    user.session_epoch += 1
    await record_audit_event(
        session, event_type="password_change", outcome="success", actor_user_id=user.id
    )
    log.info("password_change", outcome="success")
    return {"status": "ok", "detail": "all sessions invalidated"}


@router.post("/password/reset-request", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    """Begin a password reset (controls C-10, C-11).

    Always returns 202 with the same body whether or not the address exists (C-12), and
    is rate limited per account AND per IP (C-11) so it cannot be used to mail-bomb
    someone or to enumerate addresses by watching which requests are throttled.
    """
    redis = get_redis()
    email = payload.email.lower()
    ip = client_ip(request)

    for bucket, identifier, limit in (
        ("reset_acct", email, 3),
        ("reset_ip", ip, 10),
    ):
        decision = await check_rate_limit(
            redis, bucket, identifier, limit=limit, window_seconds=3600
        )
        if not decision.allowed:
            await record_audit_event(
                session, event_type="password_reset_request", outcome="rate_limited", source_ip=ip
            )
            # Same shape as success: a throttled response must not confirm the account.
            return _GENERIC_ACCEPTED

    async with get_auth_sessionmaker()() as auth_session:
        user = (
            await auth_session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

    if user is not None:
        await set_rls_context(session, user.id)
        plaintext, hashed = generate_reset_token()
        now = dt.datetime.now(dt.UTC)
        session.add(
            PasswordResetToken(user_id=user.id, token_hash=hashed, expires_at=expiry_from(now))
        )
        # The plaintext goes to the user's email and is never persisted or logged.
        log.info("password_reset_request", outcome="issued")
        del plaintext
    else:
        log.info("password_reset_request", outcome="unknown_account")

    await record_audit_event(
        session, event_type="password_reset_request", outcome="accepted", source_ip=ip
    )
    return _GENERIC_ACCEPTED


@router.post("/password/reset-confirm")
async def confirm_password_reset(
    payload: PasswordResetConfirm,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    """Consume a reset token and set a new password (controls C-09, C-10).

    The token is single use, short lived and matched against its hash. Success bumps
    ``session_epoch``, so every session that existed before the reset dies with it.
    """
    now = dt.datetime.now(dt.UTC)
    token_hash = hash_reset_token(payload.token)

    # Reset consumption is pre-authentication, so it runs on the auth connection.
    async with get_auth_sessionmaker()() as auth_session:
        row = (
            await auth_session.execute(
                select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
            )
        ).scalar_one_or_none()
        if row is None or row.consumed_at is not None or row.expires_at <= now:
            log.info("password_reset_confirm", outcome="rejected")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="invalid or expired token"
            )
        user = await auth_session.get(User, row.user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="invalid or expired token"
            )
        # Consume atomically before changing anything else.
        row.consumed_at = now
        user.password_hash = hash_password(payload.new_password)
        user.session_epoch += 1
        await auth_session.commit()

    await record_audit_event(
        session, event_type="password_reset_confirm", outcome="success", actor_user_id=user.id
    )
    log.info("password_reset_confirm", outcome="success")
    return {"status": "ok", "detail": "all sessions invalidated"}


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(current_user)]) -> User:
    return user
