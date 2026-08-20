import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey


class ApiKeyRepository:
    """
    Database access for API keys — SQL queries only.
    No business logic here.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        application_id: str,
        key_id: str,
        key_hash: str,
        key_type: str,
        environment: str = "live",
        scopes: list | None = None,
    ) -> ApiKey:
        key = ApiKey(
            id=str(uuid.uuid4()),
            application_id=application_id,
            key_id=key_id,
            key_hash=key_hash,
            key_type=key_type,
            environment=environment,
            scopes=list(scopes or []),
            status="active",
        )
        self.db.add(key)
        await self.db.flush()
        await self.db.refresh(key)
        return key

    async def get_by_key_id(self, key_id: str) -> ApiKey | None:
        """Lookup by the indexed (non-secret) portion of the key."""
        result = await self.db.execute(select(ApiKey).where(ApiKey.key_id == key_id))
        return result.scalar_one_or_none()

    async def list_by_application_id(self, application_id: str) -> list[ApiKey]:
        result = await self.db.execute(
            select(ApiKey)
            .where(ApiKey.application_id == application_id)
            .order_by(ApiKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def revoke(self, key_id: str) -> bool:
        """Soft delete: status='revoked' + revoked_at. The row stays for audit."""
        result = await self.db.execute(
            update(ApiKey)
            .where(ApiKey.key_id == key_id)
            .values(status="revoked", revoked_at=datetime.now(UTC))
        )
        return result.rowcount > 0

    async def delete_by_key_id(self, key_id: str) -> bool:
        """Hard delete — used on cascading application deletion fallback."""
        result = await self.db.execute(delete(ApiKey).where(ApiKey.key_id == key_id))
        return result.rowcount > 0
