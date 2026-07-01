import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Session(Base):
    """
    Table 'sessions' in identyx_sessions.

    Each row represents an active session for a user.
    A user can have multiple sessions (multi-device).

    Columns:
        user_id:            User's UUID (from user-service)
                            No foreign key — independent services

        refresh_token_hash: SHA-256 hash of the raw refresh token
                            Never the token in plain text — default security

        device_info:        Device information (User-Agent, IP)
                            Optional — to display "Connected from iPhone"

        is_revoked:         True if the session has been revoked
        expires_at:         Refresh token expiration date
        created_at:         Session creation date
        updated_at:         Last modified date
    """
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    # SHA-256 hash of the raw refresh token
    # Format: 64 hexadecimal characters
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    # Device information (optional)
    # Ex: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0...)"
    device_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)