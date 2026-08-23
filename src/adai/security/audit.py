"""Security event logging (control C-38, threats T-08/T-09/T-10/T-19/T-24).

Audit rows are written with a Core INSERT against the table, deliberately **without**
RETURNING. The RLS policy on ``audit_events`` grants INSERT and nothing else, so the
application can append to the audit log but can never read it back. An ORM
``session.add`` would append ``RETURNING id`` for the generated primary key, and
RETURNING is evaluated against the (absent) SELECT policy, so it would fail.

That is the control working, not a bug to route around: an application that cannot read
its own audit log cannot be used to quietly tamper with it either.

``detail`` must never carry secrets or document content; :mod:`adai.logging` redacts the
structured log, and this function keeps the database side to identifiers and codes.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import Table, insert
from sqlalchemy.ext.asyncio import AsyncSession

from adai.models import AuditEvent


async def record_audit_event(
    session: AsyncSession,
    *,
    event_type: str,
    outcome: str,
    actor_user_id: uuid.UUID | None = None,
    source_ip: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Append one security event. Never raises for a missing optional field."""
    # .inline() suppresses SQLAlchemy's implicit "RETURNING id" for the autoincrement
    # primary key. RETURNING is evaluated against the SELECT policy, and audit_events
    # deliberately has none -- see the module docstring.
    await session.execute(
        insert(cast(Table, AuditEvent.__table__))
        .inline()
        .values(
            event_type=event_type,
            outcome=outcome,
            actor_user_id=actor_user_id,
            source_ip=source_ip,
            detail=detail or {},
        )
    )
