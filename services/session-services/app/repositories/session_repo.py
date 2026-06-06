import uuid
import hashlib
from datetime import datetime, timezone
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session
from app.schemas.session import CreateSessionRequest

def _has_token(raw_token: str) -> str:
    """SHA-256 hash of a raw refresh token."""
    return hashlib.sha256(raw_token.encode()).hexdigest()

class SessionRepository:
    """
    Database access for sessions
    SQL requests only — no business logic
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: CreateSessionRequest) -> Session:
        """Insert a new session into the database"""
        session = Session(
            id=str(uuid.uuid4()),
            user_id=data.user_id,
            refresh_token_hash=data.refresh_token_hash,
            device_info=data.device_info,
            is_revoked=False,
            expires_at=data.expires_at,
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def get_by_id(self, session_id: str) -> Session | None:
        """Retrieve a session by its ID"""
        result = await self.db.execute(select(Session).where(Session.id == session_id))
        return result.scalar_one_or_none()

    async def get_by_token_hash(self, token_hash: str) -> Session | None:
        """
        Retrieve a session by its refresh token hash
        Used to validate a entry refresh token
        """
        result = await self.db.execute(select(Session).where(Session.refresh_token_hash == token_hash))
        return result.scalar_one_or_none()

    async def get_active_by_user(self, user_id: str) -> list[Session]:
        """
        Retrieve all active sessions for a user
        Actives = non-revoked and non-expired sessions
        """
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(Session)
            .where(
                Session.user_id == user_id,
                Session.is_revoked == False,
                Session.expires_at > now,
            )
            .order_by(Session.created_at.desc())
        )
        return list(result.scalars().all())

    async def count_active_by_user(self, user_id: str) -> int:
        """Count the number of active sessions for a user"""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(func.count(Session.id)).where(
                Session.user_id == user_id,
                Session.is_revoked == False,
                Session.expires_at > now,
            )
        )
        return result.scalar_one()

    async def revoke_by_token_hash(self, token_hash: str) -> bool:
        """
        Revoke a session by its refresh token hash
        Returns True if the session was successfully revoked, False otherwise
        """
        result = await self.db.execute(
            update(Session)
            .where(Session.refresh_token_hash == token_hash)
            .values(
                is_revoked=True,
                updated_at=datetime.now(timezone.utc),
            )
        )
        return result.rowcount > 0

    async def revoke_by_id(self, session_id: str) -> bool:
        """Revoke a session by its ID"""
        result = await self.db.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(
                is_revoked=True,
                updated_at=datetime.now(timezone.utc),
            )
        )
        return result.rowcount > 0

    async def revoke_all_by_user(self, user_id: str) -> int:
        """
        Revoke all active sessions for a user
        Returns the number of revoked sessions
        """
        result = await self.db.execute(
            update(Session)
            .where(Session.user_id == user_id, Session.is_revoked == False)
            .values(is_revoked=True, updated_at=datetime.now(timezone.utc))
        )
        return result.rowcount

    async def update_token_hash(self, session_id: str, new_token_hash: str, new_expires_at: datetime) -> bool:
        """
        Updates the refresh token hash for a session.
        Used during token rotation.
        """
        result = await self.db.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(
                refresh_token_hash=new_token_hash,
                expires_at=new_expires_at,
                updated_at=datetime.now(timezone.utc),
            )
        )
        return result.rowcount > 0