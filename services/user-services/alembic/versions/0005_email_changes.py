"""
Add email_changes table

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-09 00:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_changes",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("pending_email", sa.String(255), nullable=False),
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
        sa.UniqueConstraint("token_hash", name="uq_email_changes_token_hash"),
    )
    op.create_index(
        "ix_email_changes_user_id",
        "email_changes",
        ["user_id"],
    )
    op.create_index(
        "ix_email_changes_pending_email",
        "email_changes",
        ["pending_email"],
    )
    op.create_index(
        "ix_email_changes_token_hash",
        "email_changes",
        ["token_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_changes_token_hash", table_name="email_changes")
    op.drop_index("ix_email_changes_pending_email", table_name="email_changes")
    op.drop_index("ix_email_changes_user_id", table_name="email_changes")
    op.drop_table("email_changes")
