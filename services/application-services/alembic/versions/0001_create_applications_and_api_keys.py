"""
Initial migration — applications + api_keys.

Revision ID: 0001
Revises:
Create Date: 2026-08-12 00:00:00.000000

Follows the PRD §5.2 data model:
  - 1 application = 1 tenant (`tenant_id` UNIQUE).
  - `environment` is locked to 'live' in V1.1 (CHECK constraint) — the column
    exists now to avoid a costly migration once test keys ship.
  - `scopes` is stored (JSONB) but not enforced yet (reserved for V2 RBAC).
  - `key_id` is the non-secret lookup portion (prefix + 8 chars), `key_hash`
    is SHA-256 of the full secret string.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("owner_email", sa.String(255), nullable=False),
        sa.Column(
            "allowed_origins",
            postgresql.ARRAY(sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("webhook_url", sa.Text(), nullable=True),
        sa.Column("webhook_secret_hash", sa.String(64), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            server_default="active",
            nullable=False,
        ),
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
        sa.UniqueConstraint("tenant_id", name="uq_applications_tenant_id"),
        sa.CheckConstraint(
            "status IN ('active', 'suspended')",
            name="ck_applications_status",
        ),
    )
    op.create_index("ix_applications_tenant_id", "applications", ["tenant_id"])
    op.create_index("ix_applications_owner_email", "applications", ["owner_email"])

    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("key_id", sa.String(64), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("key_type", sa.String(20), nullable=False),
        sa.Column(
            "environment",
            sa.String(20),
            server_default="live",
            nullable=False,
        ),
        sa.Column(
            "scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            server_default="active",
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            ondelete="CASCADE",
            name="fk_api_keys_application_id",
        ),
        sa.UniqueConstraint("key_id", name="uq_api_keys_key_id"),
        sa.CheckConstraint(
            "key_type IN ('publishable', 'secret')",
            name="ck_api_keys_key_type",
        ),
        sa.CheckConstraint(
            "environment = 'live'",
            name="ck_api_keys_environment",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_api_keys_status",
        ),
    )
    op.create_index("ix_api_keys_application_id", "api_keys", ["application_id"])
    op.create_index("ix_api_keys_key_id", "api_keys", ["key_id"])


def downgrade() -> None:
    op.drop_index("ix_api_keys_key_id", table_name="api_keys")
    op.drop_index("ix_api_keys_application_id", table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_index("ix_applications_owner_email", table_name="applications")
    op.drop_index("ix_applications_tenant_id", table_name="applications")
    op.drop_table("applications")
