"""Request dependencies: session decoding and object-level authorisation."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adai.config import Settings, get_settings
from adai.db import get_session
from adai.models import Document, User

SESSION_COOKIE = "adai_session"
SESSION_MAX_AGE = 60 * 60 * 12


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key.get_secret_value(), salt="adai-session")


def issue_session(user: User, settings: Settings) -> str:
    """Mint a signed session cookie value bound to the user's session epoch (C-09)."""
    return _serializer(settings).dumps({"uid": str(user.id), "epoch": user.session_epoch})


async def current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    adai_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    """Resolve the authenticated user, or 401.

    Authentication is enforced here, server-side, on every route that depends on it
    (C-15). There is no client-side gating anywhere in this application.
    """
    unauthorised = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required"
    )
    if not adai_session:
        raise unauthorised
    try:
        payload = _serializer(settings).loads(adai_session, max_age=SESSION_MAX_AGE)
    except BadSignature as exc:
        raise unauthorised from exc

    user = await session.get(User, uuid.UUID(payload["uid"]))
    if user is None or not user.is_active:
        raise unauthorised
    # A password change bumps session_epoch, which invalidates every issued cookie.
    if payload.get("epoch") != user.session_epoch:
        raise unauthorised
    return user


async def owned_document(
    document_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> Document:
    """Fetch a document, enforcing object-level authorisation (control C-16, threat T-02).

    Ownership is part of the WHERE clause, not an afterthought check. And a document
    owned by someone else returns **404, not 403** -- a 403 would confirm the id exists,
    which is an enumeration oracle.
    """
    stmt = select(Document).where(
        Document.id == document_id,
        Document.owner_id == user.id,
        Document.deleted_at.is_(None),
    )
    document = (await session.execute(stmt)).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    return document
