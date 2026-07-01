import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class User(Base):
    """
    Table 'users' in identyx_users.

    Avatar columns:
        avatar_url: Public raw URL of the avatar
                    (GitHub raw in Phase 3, S3/other in future versions)
    avatar_provider: Provider of the photo
                    - "default": System default photo
                    - "upload": Uploaded by the user
                    - "google": Retrieved from the Google provider (future)
                    - "linkedin": Retrieved from the LinkedIn provider (future)
                    - "github_oauth": Retrieved from the GitHub OAuth provider (future)

    Important note: The password is NOT stored here.
    It belongs exclusively to auth-service.
    """
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True) # None = default profile picture (resolved dynamically via config)
    avatar_provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default='default',
        # Possible values: "default", "upload",
        # "google", "linkedin", "github_oauth" (future versions)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)
