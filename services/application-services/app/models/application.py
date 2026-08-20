"""
`applications` table — third-party applications registry.

1 application = 1 tenant in V1.1 (PRD): `tenant_id` is UNIQUE and assigned
at creation. `owner_email` references the developer account in
`identyx-platform` — a plain reference, no cross-DB foreign key.

`allowed_origins` drives the per-app CORS policy for publishable keys
(browser side). `webhook_url` / `webhook_secret_hash` are reserved for the
webhook delivery feature (not implemented in V1.1).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # 1 app = 1 tenant in V1.1 — unique by design
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Developer account email (reference to identyx-platform, no FK)
    owner_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # CORS origins allowed for publishable keys (browser side)
    # PostgreSQL: native TEXT[]; SQLite (tests): JSON array.
    allowed_origins: Mapped[list[str]] = mapped_column(
        ARRAY(Text).with_variant(JSON, "sqlite"),
        default=list,
        nullable=False,
    )

    webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # SHA-256 of the webhook signing secret — never stored in plain text
    webhook_secret_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # 'active' | 'suspended' — a suspended app blocks all its keys
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
