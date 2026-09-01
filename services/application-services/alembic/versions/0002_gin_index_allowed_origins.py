"""
Add GIN index on allowed_origins for origin lookups.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-01 00:00:00.000000

Sub-step D — dynamic (resolve-by-origin) CORS:
effective per-origin lookups across all active applications require a
bloom-friendly index on the array column. Postgres GIN indexes the array
elements so `WHERE allowed_origins @> ARRAY[:origin]` can use it.

The model declares the same index with `postgresql_using="gin"`; SQLite
(tests) skips it because GIN is a Postgres-only access method.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_applications_allowed_origins_gin",
        "applications",
        ["allowed_origins"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_applications_allowed_origins_gin",
        table_name="applications",
        postgresql_using="gin",
    )
