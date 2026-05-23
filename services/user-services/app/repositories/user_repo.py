from datetime import datetime, timezone
import uuid
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate

class UserRepository:
    """
    Database access — SQL queries only.
    No business logic here.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: UserCreate) -> User:
        """Insert new user data into the database. The password is not stored here"""
        user = User(
            id=str(uuid.uuid4()),
            email=data.email.lower().strip(),
            username=data.username.strip(),
            avatar_url=None,         # Resolved by default in schema
            avatar_provider="default",
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def get_by_id(self, user_id: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.email == email.lower().strip())
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.username == username.strip())
        )
        return result.scalar_one_or_none()

    async def update(self, user_id: str, data: UserUpdate) -> User | None:
        fields = data.model_dump(exclude_none=True)
        if not fields:
            return await self.get_by_id(user_id)
        if "email" in fields:
            fields["email"] = fields["email"].lower().strip()
        fields["updated_at"] = datetime.now(timezone.utc)
        await self.db.execute(
            update(User).where(User.id == user_id).values(**fields)
        )
        return await self.get_by_id(user_id)

    async def update_avatar(self, user_id: str, avatar_url: str | None, avatar_provider: str) -> User | None:
        """
        Update the avatar of the user.

        avatar_url=None + avatar_provider="default" -> return to default profile picture
        """
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                avatar_url=avatar_url,
                avatar_provider=avatar_provider,
                updated_at=datetime.now(timezone.utc),
            )
        )
        return await self.get_by_id(user_id)

    async def delete(self, user_id: str) -> bool:
        result = await self.db.execute(delete(User).where(User.id == user_id))
        return result.rowcount > 0

    async def count(self) -> int:
        result = await self.db.execute(select(func.count(User.id)))
        return result.scalar_one()

    async def get_all(self, page: int = 1, page_size: int = 20) -> list[User]:
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(User)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().all())

