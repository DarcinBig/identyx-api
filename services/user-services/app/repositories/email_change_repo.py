"""
Repository for the email_changes table.
SQL queries only — no business logic.
"""
import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_change import EmailChange


def _hash_token(raw_token: str) -> str:
    """SHA-256 hash of the raw token. The token is never stored in plain text"""
    return hashlib.sha256(raw_token.encode()).hexdigest()

class EmailChangeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
            self,
            user_id: str,
            raw_token: str,
            pending_email: str,
            expires_in_hours: int = 24,
    ) -> EmailChange:
        """
        Creates a new email change request.
        Stores only the SHA-256 hash of the raw token.
        """
        email_change = EmailChange(
            id=str(uuid.uuid4()),
            user_id=user_id,
            pending_email=pending_email,
            token_hash=_hash_token(raw_token),
            is_used=False,
            expires_at=datetime.now(UTC) + timedelta(hours=expires_in_hours),
        )
        self.db.add(email_change)
        await self.db.flush()
        await self.db.refresh(email_change)
        return email_change

    async def get_by_token(self, raw_token: str) -> EmailChange | None:
        """
        Retrieves an email change request using the raw token.
        Hashes the token for lookup.
        """
        token_hash = _hash_token(raw_token)
        result = await self.db.execute(
            select(EmailChange).where(
                EmailChange.token_hash == token_hash
            )
        )
        return result.scalar_one_or_none()

    async def mark_as_used(self, email_change_id: str) -> None:
        """Marks an email change request as used — it can no longer be reused."""
        await self.db.execute(
            update(EmailChange)
            .where(EmailChange.id == email_change_id)
            .values(
                is_used=True,
                updated_at=datetime.now(UTC),
            )
        )

    async def get_latest_for_user(self, user_id: str) -> EmailChange | None:
        """
        Retrieves the most recent unused email change request for a user.
        """
        result = await self.db.execute(
            select(EmailChange)
            .where(
                EmailChange.user_id == user_id,
                EmailChange.is_used == False,      # noqa: E712
            )
            .order_by(EmailChange.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
