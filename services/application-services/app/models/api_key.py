"""
`api_keys` table — API key registry for applications.

Security model (PRD §5.2):
  - key_id (DB)   : prefix + 8 chars of the random part — indexed, NOT secret,
                    used for fast lookups and dashboard identification.
  - key_hash (DB) : SHA-256 of the full secret string — never stored in plain.
  - The full key (`pk_live_...`/`sk_live_...` + 24 base62 chars) is only ever
    shown once, at creation or rotation.

`environment` is locked to 'live' in V1.1 (CHECK constraint in migration) —
the column exists now to avoid a costly migration once test keys ship.
`scopes` is stored but not enforced yet (reserved for V2 RBAC).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # Cascades: deleting an application deletes its keys
    application_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Prefix + 8 chars — the indexed, non-secret lookup portion
    key_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    # SHA-256 of the full secret string
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # 'publishable' | 'secret'
    key_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # 'live' only in V1.1 (CHECK constraint in migration)
    environment: Mapped[str] = mapped_column(String(20), default="live", nullable=False)

    # Reserved for V2 RBAC — stored, not enforced in V1.1
    scopes: Mapped[list] = mapped_column(
        JSON().with_variant(postgresql.JSONB, "postgresql"),
        default=list,
        nullable=False,
    )

    # 'active' | 'revoked'
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
