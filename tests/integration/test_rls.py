"""Row Level Security as defence in depth (control C-17, threat T-02).

These tests bypass the application entirely and talk to Postgres directly. That is the
point: C-16 (application-level ownership checks) is tested elsewhere, and this file
asks the different question of whether the database ALSO refuses, so that a future bug
in a query predicate does not become a data breach.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.integration, pytest.mark.security]

USER_A = uuid.UUID("aaaaaaaa-1111-1111-1111-111111111111")
USER_B = uuid.UUID("bbbbbbbb-2222-2222-2222-222222222222")


async def _seed() -> None:
    """Insert two users' documents via the BYPASSRLS worker role."""
    from adai.db import get_worker_sessionmaker

    async with get_worker_sessionmaker()() as session:
        await session.execute(text("DELETE FROM users"))
        for user_id, email in ((USER_A, "rls-a@example.com"), (USER_B, "rls-b@example.com")):
            await session.execute(
                text(
                    "INSERT INTO users (id,email,password_hash,is_active,session_epoch) "
                    "VALUES (:i,:e,'h',true,0)"
                ),
                {"i": user_id, "e": email},
            )
            await session.execute(
                text(
                    "INSERT INTO documents (id,owner_id,original_filename,blob_key,"
                    "content_type,byte_size,sha256,width,height,status,originals_expire_at) "
                    "VALUES (gen_random_uuid(),:o,'f.jpg',:k,'image/jpeg',10,'x',10,10,"
                    "'pending', now() + interval '90 days')"
                ),
                {"o": user_id, "k": f"key-{user_id}"},
            )
        await session.commit()


async def _count_as(user_id: uuid.UUID | None) -> int:
    """Count documents visible to the RLS-scoped application role."""
    from adai.db import get_sessionmaker, set_rls_context

    async with get_sessionmaker()() as session:
        await set_rls_context(session, user_id)
        return int((await session.execute(text("SELECT count(*) FROM documents"))).scalar_one())


async def test_unscoped_session_sees_nothing() -> None:
    """Fails closed: no context means no rows, not all rows."""
    await _seed()
    assert await _count_as(None) == 0


async def test_each_user_sees_only_their_own() -> None:
    await _seed()
    assert await _count_as(USER_A) == 1
    assert await _count_as(USER_B) == 1


async def test_direct_id_lookup_across_users_returns_nothing() -> None:
    """The IDOR attempt, at the database layer: even a query with no ownership
    predicate returns nothing for another user's row."""
    from adai.db import get_sessionmaker, get_worker_sessionmaker, set_rls_context

    await _seed()
    async with get_worker_sessionmaker()() as session:
        b_doc = (
            await session.execute(
                text("SELECT id FROM documents WHERE owner_id = :o"), {"o": USER_B}
            )
        ).scalar_one()

    async with get_sessionmaker()() as session:
        await set_rls_context(session, USER_A)
        found = (
            await session.execute(
                text("SELECT count(*) FROM documents WHERE id = :i"), {"i": b_doc}
            )
        ).scalar_one()
    assert found == 0


async def test_application_role_cannot_read_the_audit_log() -> None:
    """C-38/C-18: the app appends to the audit log and can never read it back."""
    from adai.db import get_sessionmaker, set_rls_context

    async with get_sessionmaker()() as session:
        await set_rls_context(session, USER_A)
        count = (await session.execute(text("SELECT count(*) FROM audit_events"))).scalar_one()
    assert count == 0


async def test_rls_is_forced_so_it_applies_to_the_table_owner() -> None:
    """Without FORCE, the owning role silently bypasses every policy."""
    from adai.db import get_worker_sessionmaker

    async with get_worker_sessionmaker()() as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT relname FROM pg_class WHERE relname IN "
                        "('users','documents','consent_records','transcriptions',"
                        "'audit_events','password_reset_tokens') "
                        "AND (relrowsecurity = false OR relforcerowsecurity = false)"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert rows == [], f"RLS not enabled+forced on: {rows}"


async def test_worker_role_has_bypassrls_and_the_app_role_does_not() -> None:
    """C-18: the privilege split is the whole design, so assert it explicitly."""
    from adai.db import get_worker_sessionmaker

    async with get_worker_sessionmaker()() as session:
        rows = dict(
            (
                await session.execute(
                    text(
                        "SELECT rolname, rolbypassrls FROM pg_roles "
                        "WHERE rolname IN ('adai_app','adai_worker')"
                    )
                )
            ).all()
        )
    assert rows.get("adai_app") is False, "the API role must be subject to RLS"
    assert rows.get("adai_worker") is True, "the worker role needs cross-user access"
