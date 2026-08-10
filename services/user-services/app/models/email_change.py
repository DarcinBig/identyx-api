"""
`email_changes` table — stores pending email change requests.

A request is created when the owner asks to change their email address.
It is sent by email to the NEW address and must be confirmed before the
change is applied. It is marked `used=True` after confirmation.
It expires after 24 hours (`expires_at`).

Rules:
  - A user can have multiple pending requests (re-requests).
  - Only the most recent unused and unexpired token is valid.
  - The `pending_email` column stores the target email — it only replaces
    the user's email once the token has been confirmed.
  - Never store the raw token in plain text — only the SHA-256 hash.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EmailChange(Base):
    __tablename__ = "email_changes"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # User UUID (from user-service)
    # No foreign key — independent services
    user_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    # Target email — replaces the user's email on confirmation
    pending_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    # SHA-256 hash of the raw token
    # We never store the token in plain text
    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    # Token already used — cannot be reused
    is_used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Expiration — 24h after creation
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
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
