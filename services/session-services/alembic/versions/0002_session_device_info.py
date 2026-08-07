"""
Add index on device_info

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-06 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_sessions_device_info", "sessions", ["device_info"])


def downgrade() -> None:
    op.drop_index("ix_sessions_device_info", table_name="sessions")
