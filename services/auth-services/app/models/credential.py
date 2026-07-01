# The auth-service only stores credentials — never the profile.
# The profile belongs to the user-service.
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class UserCredential(Base):
    """
    The 'user_credentials' table is located in identyx_auth.

    Fundamental rule:
        - user_id corresponds to the UUID created by the user service.
        - Email and username are NOT stored here.
        - Passwords are NOT stored in plain text — only the Argon2id hash.
        - The hash already contains the salt, parameters, and Argon2 version.

    This separation ensures that even if identyx_auth is compromised,
    the attacker only obtains Argon2id hashes without any user profiles.
    """
    __tablename__ = "user_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # user-service side UUID
    # No foreign key — each service is independent
    user_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)

    # Hash Argon2id of password
    # Format: $argon2id$v=19$m=65536,t=2,p=2$<sel>$<hash>
    hashed_password: Mapped[str] = mapped_column(Text,nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)
