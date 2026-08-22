"""
Add tenant_id to sessions table, backfill native tenant.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-22 00:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NATIVE_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.add_column("sessions", sa.Column("tenant_id", sa.String(36), nullable=True))
    op.execute(
        f"UPDATE sessions SET tenant_id = '{NATIVE_TENANT_ID}' WHERE tenant_id IS NULL"
    )
    op.alter_column("sessions", "tenant_id", nullable=False, server_default=NATIVE_TENANT_ID)
    op.create_index("ix_sessions_tenant_id", "sessions", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_sessions_tenant_id", table_name="sessions")
    op.drop_column("sessions", "tenant_id")
