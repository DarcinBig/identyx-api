import uuid
from datetime import datetime, timezone
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credential import UserCredential

class CredentialRepository:
    """
    Database access for credentials.
    SQL queries only — no business logic.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: str, hashed_password: str) -> UserCredential:
        """Insert a new credential into the database."""
        credential = UserCredential(
            id=str(uuid.uuid4()),
            user_id=user_id,
            hashed_password=hashed_password,
        )
        self.db.add(credential)
        await self.db.flush()
        await self.db.refresh(credential)
        return credential


    async def get_by_user_id(self, user_id: str) -> UserCredential | None:
        """Retrieve a credential by its user_id."""
        result = await self.db.execute(
            select(UserCredential).where(UserCredential.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update_password(self, user_id: str, new_hashed_password: str) -> bool:
        """
        Updates the password hash.
        Used for `needs_rehash` after a successful login.
        Returns True if updated, False if not found.
        """
        result = await self.db.execute(
            update(UserCredential)
            .where(UserCredential.user_id == user_id)
            .values(
                hashed_password=new_hashed_password,
                updated_at=datetime.now(timezone.utc),
            )
        )
        return result.rowcount > 0

    async def delete_by_user_id(self, user_id: str) -> bool:
        """
        Deletes a user's credentials.
        Called if profile creation fails (full rollback).
        """
        result = await self.db.execute(
            delete(UserCredential)
            .where(UserCredential.user_id == user_id)
        )
        return result.rowcount > 0