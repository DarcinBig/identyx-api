"""
Repository for the email_verifications table.
SQL queries only — no business logic.
"""
import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_verification import EmailVerification


def _hash_token(raw_token: str) -> str:
    """SHA-256 hash of the raw token. The token is never stored in plain text"""
    return hashlib.sha256(raw_token.encode()).hexdigest()

class EmailVerificationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
            self,
            user_id: str,
            raw_token: str,
            expires_in_hours: int = 24,
    ) -> EmailVerification:
        """
        Creates a new verification token.
        Stores only the SHA-256 hash of the raw token.
        """
        verification = EmailVerification(
            id=str(uuid.uuid4()),
            user_id=user_id,
            token_hash=_hash_token(raw_token),
            is_used=False,
            expires_at=datetime.now(UTC) + timedelta(hours=expires_in_hours),
        )
        self.db.add(verification)
        await self.db.flush()
        await self.db.refresh(verification)
        return verification

    async def get_by_token(self, raw_token: str) -> EmailVerification | None:
        """
        Retrieves a verification token using the raw token.
        Hashes the token for lookup.
        """
        token_hash = _hash_token(raw_token)
        result = await self.db.execute(
            select(EmailVerification).where(
                EmailVerification.token_hash == token_hash
            )
        )
        return result.scalar_one_or_none()

    async def mark_as_used(self, verification_id: str) -> None:
        """Marks a token as used — it can no longer be reused."""
        await self.db.execute(
            update(EmailVerification)
            .where(EmailVerification.id == verification_id)
            .values(
                is_used=True,
                updated_at=datetime.now(UTC),
            )
        )

    async def get_latest_for_user(self, user_id: str) -> EmailVerification | None:
        """
        Retrieves the most recent unused token for a user.
        Useful for resending the verification email.
        """
        result = await self.db.execute(
            select(EmailVerification)
            .where(
                EmailVerification.user_id == user_id,
                EmailVerification.is_used == False,      # noqa: E712
            )
            .order_by(EmailVerification.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()