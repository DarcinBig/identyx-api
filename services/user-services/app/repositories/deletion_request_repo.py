"""
Repository for the deletion_requests table.
SQL queries only — no business logic.
"""
import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deletion_request import DeletionRequest


def _hash_token(raw_token: str) -> str:
    """SHA-256 hash of the raw token. The token is never stored in plain text"""
    return hashlib.sha256(raw_token.encode()).hexdigest()

class DeletionRequestRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
            self,
            user_id: str,
            raw_token: str,
            expires_in_hours: int = 24,
    ) -> DeletionRequest:
        """
        Creates a new deletion confirmation token.
        Stores only the SHA-256 hash of the raw token.
        """
        deletion_request = DeletionRequest(
            id=str(uuid.uuid4()),
            user_id=user_id,
            token_hash=_hash_token(raw_token),
            is_used=False,
            expires_at=datetime.now(UTC) + timedelta(hours=expires_in_hours),
        )
        self.db.add(deletion_request)
        await self.db.flush()
        await self.db.refresh(deletion_request)
        return deletion_request

    async def get_by_token(self, raw_token: str) -> DeletionRequest | None:
        """
        Retrieves a deletion request using the raw token.
        Hashes the token for lookup.
        """
        token_hash = _hash_token(raw_token)
        result = await self.db.execute(
            select(DeletionRequest).where(
                DeletionRequest.token_hash == token_hash
            )
        )
        return result.scalar_one_or_none()

    async def mark_as_used(self, deletion_request_id: str) -> None:
        """Marks a deletion request as used — it can no longer be reused."""
        await self.db.execute(
            update(DeletionRequest)
            .where(DeletionRequest.id == deletion_request_id)
            .values(
                is_used=True,
                updated_at=datetime.now(UTC),
            )
        )

    async def get_latest_for_user(self, user_id: str) -> DeletionRequest | None:
        """
        Retrieves the most recent unused deletion request for a user.
        """
        result = await self.db.execute(
            select(DeletionRequest)
            .where(
                DeletionRequest.user_id == user_id,
                DeletionRequest.is_used == False,      # noqa: E712
            )
            .order_by(DeletionRequest.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
