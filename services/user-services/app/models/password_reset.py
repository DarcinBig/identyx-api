"""
`password_resets` table — stores password reset tokens.

A token is created when a suspicious login is detected
(a successful login following several failed attempts).
It is marked `used=True` after a successful password change.
It expires after 1 hour (`expires_at`).

Rules:
  - A user can have multiple tokens (multiple alerts).
  - Only the most recent unused and unexpired token is valid.
  - Never store the raw token in plain text — only the SHA-256 hash.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class PasswordReset(Base):
    __tablename__ = "password_resets"

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

    # Expiration — 1h after creation
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
