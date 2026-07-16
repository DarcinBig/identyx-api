"""
Initial migration — table sessions

Revision ID: 0001
Revises:
Create Date: 2026-07-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("refresh_token_hash", sa.String(64), nullable=False),
        sa.Column("device_info", sa.Text(), nullable=True),
        sa.Column(
            "is_revoked",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "refresh_token_hash",
            name="uq_sessions_refresh_token_hash",
        ),
    )
    op.create_index("ix_sessions_id", "sessions", ["id"])
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index(
        "ix_sessions_refresh_token_hash",
        "sessions",
        ["refresh_token_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_sessions_refresh_token_hash", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_index("ix_sessions_id", table_name="sessions")
    op.drop_table("sessions")