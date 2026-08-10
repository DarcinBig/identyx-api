"""
Add deletion_requests table

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-09 00:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "deletion_requests",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "is_used",
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
        sa.UniqueConstraint("token_hash", name="uq_deletion_requests_token_hash"),
    )
    op.create_index(
        "ix_deletion_requests_user_id",
        "deletion_requests",
        ["user_id"],
    )
    op.create_index(
        "ix_deletion_requests_token_hash",
        "deletion_requests",
        ["token_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_deletion_requests_token_hash", table_name="deletion_requests")
    op.drop_index("ix_deletion_requests_user_id", table_name="deletion_requests")
    op.drop_table("deletion_requests")
