import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.schemas.application import ApplicationCreate, ApplicationUpdate


class ApplicationRepository:
    """
    Database access for applications — SQL queries only.
    No business logic here.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: ApplicationCreate) -> Application:
        """Insert a new application with a fresh tenant_id (1 app = 1 tenant)."""
        application = Application(
            id=str(uuid.uuid4()),
            tenant_id=str(uuid.uuid4()),
            name=data.name.strip(),
            owner_email=data.owner_email.lower().strip(),
            allowed_origins=list(data.allowed_origins),
            webhook_url=data.webhook_url,
            status="active",
        )
        self.db.add(application)
        await self.db.flush()
        await self.db.refresh(application)
        return application

    async def get_by_id(self, application_id: str) -> Application | None:
        result = await self.db.execute(select(Application).where(Application.id == application_id))
        return result.scalar_one_or_none()

    async def get_by_tenant_id(self, tenant_id: str) -> Application | None:
        result = await self.db.execute(
            select(Application).where(Application.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def list_by_owner_email(self, owner_email: str) -> list[Application]:
        result = await self.db.execute(
            select(Application)
            .where(Application.owner_email == owner_email.lower().strip())
            .order_by(Application.created_at.desc())
        )
        return list(result.scalars().all())

    async def find_active_by_origins(self, origins: list[str]) -> list[Application]:
        """Active applications whose `allowed_origins` overlap the given origins.

        Used for:
          - dynamic CORS resolution (which app(s) allow an origin), and
          - enforcing cross-app origin uniqueness at write time.
        Postgres uses the GIN index on the array column; SQLite (tests) filters
        in Python because it stores the array as JSON.
        """
        origins = [o for o in origins if o]
        if not origins:
            return []

        dialect = self.db.bind.dialect.name if self.db.bind is not None else ""
        if dialect == "postgresql":
            from sqlalchemy import or_

            conditions = [Application.allowed_origins.any(origin) for origin in origins]
            result = await self.db.execute(
                select(Application)
                .where(Application.status == "active", or_(*conditions))
            )
        else:
            result = await self.db.execute(
                select(Application).where(Application.status == "active")
            )
            return [
                app
                for app in result.scalars().all()
                if any(o in (app.allowed_origins or []) for o in origins)
            ]
        return list(result.scalars().all())

    async def update(self, application_id: str, data: ApplicationUpdate) -> Application | None:
        fields = data.model_dump(exclude_none=True)
        if not fields:
            return await self.get_by_id(application_id)
        if "name" in fields:
            fields["name"] = fields["name"].strip()
        fields["updated_at"] = datetime.now(UTC)
        await self.db.execute(
            update(Application).where(Application.id == application_id).values(**fields)
        )
        return await self.get_by_id(application_id)

    async def delete(self, application_id: str) -> bool:
        from sqlalchemy import delete

        result = await self.db.execute(delete(Application).where(Application.id == application_id))
        return result.rowcount > 0

    async def count(self) -> int:
        result = await self.db.execute(select(func.count(Application.id)))
        return result.scalar_one()
