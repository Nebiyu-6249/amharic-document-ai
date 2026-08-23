"""row level security and reset tokens

Adds:
  * Row Level Security on every user-data table (control C-17, threat T-02), as defence
    in depth *behind* the application's object-level checks (C-16), never instead of them.
  * Password-reset token storage (control C-10, threat T-10).
  * Encrypted-column support for sensitive text (control C-37).

On FORCE ROW LEVEL SECURITY: a table's owner bypasses RLS by default, and in the
development setup the application role owns its tables. FORCE removes that exemption so
the policies actually apply. In production the tables should additionally be owned by a
separate migration role -- see scripts/db_roles.sql (control C-18).

Policies key off the transaction-local GUC ``adai.current_user_id``, set by
``adai.db.set_rls_context``. If it is unset, ``current_setting(..., true)`` returns NULL
and every policy evaluates false, so an unscoped session sees nothing. That is the
correct failure direction.

Revision ID: 0002_rls
Revises: ae7928986f3f
Create Date: 2026-08-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_rls"
down_revision: str | None = "ae7928986f3f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Tables carrying user data, and the SQL locating their owning user.
_OWNER_PREDICATE = {
    "users": "id = NULLIF(current_setting('adai.current_user_id', true), '')::uuid",
    "documents": "owner_id = NULLIF(current_setting('adai.current_user_id', true), '')::uuid",
    "consent_records": (
        "document_id IN (SELECT id FROM documents "
        "WHERE owner_id = NULLIF(current_setting('adai.current_user_id', true), '')::uuid)"
    ),
    "transcriptions": (
        "document_id IN (SELECT id FROM documents "
        "WHERE owner_id = NULLIF(current_setting('adai.current_user_id', true), '')::uuid)"
    ),
}


def upgrade() -> None:
    # --- C-10: password reset tokens, hashed at rest, single use -------------------
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # SHA-256 hex of the token. The plaintext is emailed and never stored.
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
        # Set atomically on use; a non-null value means the token is spent.
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    # --- C-37: encrypted column for sensitive derived text -------------------------
    op.add_column(
        "transcriptions", sa.Column("encrypted_text", sa.Text(), nullable=True)
    )

    # --- C-17: row level security --------------------------------------------------
    for table, predicate in _OWNER_PREDICATE.items():
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        if table == "users":
            # Registration is unauthenticated: there is no current user yet, so an
            # INSERT cannot satisfy an ownership predicate. Creating a user row leaks
            # nothing (uniqueness is enforced by the constraint, and the API returns an
            # identical response either way for anti-enumeration, C-12), so INSERT is
            # allowed and the confidentiality-relevant commands stay scoped.
            op.execute(
                "CREATE POLICY users_insert_open ON users FOR INSERT WITH CHECK (true)"
            )
            for command in ("SELECT", "UPDATE", "DELETE"):
                clause = (
                    f"USING ({predicate}) WITH CHECK ({predicate})"
                    if command == "UPDATE"
                    else f"USING ({predicate})"
                )
                op.execute(
                    f"CREATE POLICY users_{command.lower()}_own ON users "
                    f"FOR {command} {clause}"
                )
        else:
            op.execute(
                f"CREATE POLICY {table}_owner_isolation ON {table} "
                f"USING ({predicate}) WITH CHECK ({predicate})"
            )

    # Reset tokens follow the owning user.
    op.execute("ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE password_reset_tokens FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY password_reset_tokens_owner_isolation ON password_reset_tokens "
        "USING (user_id = NULLIF(current_setting('adai.current_user_id', true), '')::uuid) "
        "WITH CHECK (user_id = NULLIF(current_setting('adai.current_user_id', true), '')::uuid)"
    )

    # Audit events are append-only from the application's perspective: it may INSERT,
    # and RLS grants no SELECT policy, so no user session can read the audit log.
    op.execute("ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_events FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY audit_events_append_only ON audit_events FOR INSERT WITH CHECK (true)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS audit_events_append_only ON audit_events")
    op.execute("ALTER TABLE audit_events NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY")

    op.execute(
        "DROP POLICY IF EXISTS password_reset_tokens_owner_isolation ON password_reset_tokens"
    )
    op.execute("DROP POLICY IF EXISTS users_insert_open ON users")
    for command in ("select", "update", "delete"):
        op.execute(f"DROP POLICY IF EXISTS users_{command}_own ON users")
    for table in _OWNER_PREDICATE:
        op.execute(f"DROP POLICY IF EXISTS {table}_owner_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_column("transcriptions", "encrypted_text")
    op.drop_table("password_reset_tokens")
