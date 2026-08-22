"""
Add tenant_id to users + token tables, backfill native tenant,
change email unique constraint to (tenant_id, email).

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-22 00:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NATIVE_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    # --- users table ---
    op.add_column("users", sa.Column("tenant_id", sa.String(36), nullable=True))
    op.execute(
        f"UPDATE users SET tenant_id = '{NATIVE_TENANT_ID}' WHERE tenant_id IS NULL"
    )
    op.alter_column("users", "tenant_id", nullable=False, server_default=NATIVE_TENANT_ID)
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    # Drop old unique constraint on email, add composite (tenant_id, email)
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.create_unique_constraint(
        "uq_users_tenant_email", "users", ["tenant_id", "email"]
    )

    # --- email_verifications ---
    op.add_column("email_verifications", sa.Column("tenant_id", sa.String(36), nullable=True))
    op.execute(
        f"UPDATE email_verifications SET tenant_id = '{NATIVE_TENANT_ID}' WHERE tenant_id IS NULL"
    )
    op.alter_column("email_verifications", "tenant_id", nullable=False, server_default=NATIVE_TENANT_ID)
    op.create_index("ix_email_verifications_tenant_id", "email_verifications", ["tenant_id"])

    # --- password_resets ---
    op.add_column("password_resets", sa.Column("tenant_id", sa.String(36), nullable=True))
    op.execute(
        f"UPDATE password_resets SET tenant_id = '{NATIVE_TENANT_ID}' WHERE tenant_id IS NULL"
    )
    op.alter_column("password_resets", "tenant_id", nullable=False, server_default=NATIVE_TENANT_ID)
    op.create_index("ix_password_resets_tenant_id", "password_resets", ["tenant_id"])

    # --- deletion_requests ---
    op.add_column("deletion_requests", sa.Column("tenant_id", sa.String(36), nullable=True))
    op.execute(
        f"UPDATE deletion_requests SET tenant_id = '{NATIVE_TENANT_ID}' WHERE tenant_id IS NULL"
    )
    op.alter_column("deletion_requests", "tenant_id", nullable=False, server_default=NATIVE_TENANT_ID)
    op.create_index("ix_deletion_requests_tenant_id", "deletion_requests", ["tenant_id"])

    # --- email_changes ---
    op.add_column("email_changes", sa.Column("tenant_id", sa.String(36), nullable=True))
    op.execute(
        f"UPDATE email_changes SET tenant_id = '{NATIVE_TENANT_ID}' WHERE tenant_id IS NULL"
    )
    op.alter_column("email_changes", "tenant_id", nullable=False, server_default=NATIVE_TENANT_ID)
    op.create_index("ix_email_changes_tenant_id", "email_changes", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_email_changes_tenant_id", table_name="email_changes")
    op.drop_column("email_changes", "tenant_id")

    op.drop_index("ix_deletion_requests_tenant_id", table_name="deletion_requests")
    op.drop_column("deletion_requests", "tenant_id")

    op.drop_index("ix_password_resets_tenant_id", table_name="password_resets")
    op.drop_column("password_resets", "tenant_id")

    op.drop_index("ix_email_verifications_tenant_id", table_name="email_verifications")
    op.drop_column("email_verifications", "tenant_id")

    op.drop_constraint("uq_users_tenant_email", "users", type_="unique")
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_column("users", "tenant_id")
