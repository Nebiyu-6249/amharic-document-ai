"""Async database engine and session factory."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from adai.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            # Never echo SQL in a deployed environment: bound parameters can contain
            # personal data, and SQL logs are a classic T-19 leak.
            echo=settings.debug and settings.environment == "dev",
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session with commit/rollback handling."""
    async with get_sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


_worker_engine: AsyncEngine | None = None
_worker_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_worker_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Sessions for the background worker, using the BYPASSRLS role (control C-18)."""
    global _worker_engine, _worker_sessionmaker
    if _worker_sessionmaker is None:
        settings = get_settings()
        _worker_engine = create_async_engine(
            settings.effective_worker_database_url, pool_pre_ping=True, echo=False
        )
        _worker_sessionmaker = async_sessionmaker(_worker_engine, expire_on_commit=False)
    return _worker_sessionmaker


_auth_engine: AsyncEngine | None = None
_auth_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_auth_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Sessions for pre-authentication user lookup ONLY (control C-18).

    Login has to find a user by email before any identity exists, so the RLS predicate
    cannot be satisfied and the row would be invisible. This connection uses a role that
    can read `users` and do nothing else. It must never be used for anything but the
    credential lookup.
    """
    global _auth_engine, _auth_sessionmaker
    if _auth_sessionmaker is None:
        settings = get_settings()
        _auth_engine = create_async_engine(
            settings.effective_auth_database_url, pool_pre_ping=True, echo=False
        )
        _auth_sessionmaker = async_sessionmaker(_auth_engine, expire_on_commit=False)
    return _auth_sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker, _worker_engine, _worker_sessionmaker
    global _auth_engine, _auth_sessionmaker
    for engine in (_engine, _worker_engine, _auth_engine):
        if engine is not None:
            await engine.dispose()
    _engine = None
    _sessionmaker = None
    _worker_engine = None
    _worker_sessionmaker = None
    _auth_engine = None
    _auth_sessionmaker = None


async def set_rls_context(session: AsyncSession, user_id: uuid.UUID | None) -> None:
    """Bind the Postgres RLS predicate to a user for this transaction (control C-17).

    Sets ``adai.current_user_id`` transaction-locally (the ``true`` third argument to
    ``set_config``), so it cannot leak to the next checkout of a pooled connection.

    When ``user_id`` is None the setting is cleared, which makes every policy evaluate
    false and the session see nothing. That is the correct direction to fail: an
    unscoped session reads no user data rather than all of it.
    """
    await session.execute(
        text("SELECT set_config('adai.current_user_id', :uid, true)"),
        {"uid": str(user_id) if user_id else ""},
    )
