"""
Repository for the password_resets table.
SQL queries only — no business logic.
"""
import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.password_reset import PasswordReset


def _hash_token(raw_token: str) -> str:
    """SHA-256 hash of the raw token. The token is never stored in plain text"""
    return hashlib.sha256(raw_token.encode()).hexdigest()

class PasswordResetRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
            self,
            user_id: str,
            raw_token: str,
            expires_in_minutes: int = 60,
    ) -> PasswordReset:
        """
        Creates a new password reset token.
        Stores only the SHA-256 hash of the raw token.
        """
        reset = PasswordReset(
            id=str(uuid.uuid4()),
            user_id=user_id,
            token_hash=_hash_token(raw_token),
            is_used=False,
            expires_at=datetime.now(UTC) + timedelta(minutes=expires_in_minutes),
        )
        self.db.add(reset)
        await self.db.flush()
        await self.db.refresh(reset)
        return reset

    async def get_by_token(self, raw_token: str) -> PasswordReset | None:
        """
        Retrieves a reset token using the raw token.
        Hashes the token for lookup.
        """
        token_hash = _hash_token(raw_token)
        result = await self.db.execute(
            select(PasswordReset).where(
                PasswordReset.token_hash == token_hash
            )
        )
        return result.scalar_one_or_none()

    async def mark_as_used(self, reset_id: str) -> None:
        """Marks a token as used — it can no longer be reused."""
        await self.db.execute(
            update(PasswordReset)
            .where(PasswordReset.id == reset_id)
            .values(
                is_used=True,
                updated_at=datetime.now(UTC),
            )
        )
