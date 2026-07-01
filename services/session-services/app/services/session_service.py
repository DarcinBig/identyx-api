import hashlib
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.repositories.session_repo import SessionRepository
from app.schemas.session import (
    CreateSessionRequest,
    MessageResponse,
    RevokeSessionRequest,
    SessionListResponse,
    SessionResponse,
    ValidateSessionRequest,
    ValidateSessionResponse,
)

settings = get_settings()

def _hash_token(raw_token: str) -> str:
    """SHA-256 hash of a raw refresh token."""
    return hashlib.sha256(raw_token.encode()).hexdigest()

class SessionService:
    """
    Session service business logic.

    Rules:
        - A revoked refresh token can never be reused.
        - An expired refresh token is treated as revoked.
        - Rotation invalidates the old token and creates a new hash.
        - Revoke-all disconnects all devices from a user.
    """
    def __init__(self, db: AsyncSession):
        self.repo = SessionRepository(db)

    async def create_session(self, data: CreateSessionRequest) -> SessionResponse:
        """
        Creates a new session after login or registration.

        The refresh token hash comes directly from token-service.
        The raw token is never stored.
        """
        session = await self.repo.create(data)
        return SessionResponse.model_validate(session)

    async def validate_session(self, data: ValidateSessionRequest) -> ValidateSessionResponse:
        """
        Validates an incoming refresh token.

        Flow:
            1. Hash the raw token received from the client
            2. Search the database by hash
            3. Check: not revoked + not expired

        Returns `valid=True` + `user_id` + `session_id` if valid.
        Returns `valid=False` otherwise — without raising an exception.
        """
        token_hash = _hash_token(data.refresh_token)
        session = await self.repo.get_by_token_hash(token_hash)

        if not session:
            return ValidateSessionResponse(valid=False)
        if session.is_revoked:
            return ValidateSessionResponse(valid=False)

        now = datetime.now(UTC)
        if session.expires_at.replace(tzinfo=UTC) < now:
            return ValidateSessionResponse(valid=False)

        return ValidateSessionResponse(
            valid=True,
            user_id=session.user_id,
            session_id=session.id
        )

    async def revoke_session(self, data: RevokeSessionRequest) -> MessageResponse:
        """
        Revokes a session using its refresh token.
        Used during logout.

        If the token does not exist or has already been revoked,
        `success` is returned — no error.
        """
        token_hash = _hash_token(data.refresh_token)
        await self.repo.revoke_by_token_hash(token_hash)
        return MessageResponse(message="Session revoked successfully.")

    async def revoke_session_by_id(self, session_id: str, user_id: str) -> MessageResponse:
        """
        Revokes a session by its ID.
        Verifies that the session belongs to the correct user.

        Raises:
            404 if the session does not exist
            403 if the session belongs to another user
        """
        session = await self.repo.get_by_id(session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found."
            )

        if session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot revoke another user's session."
            )
        await self.repo.revoke_by_id(session_id)
        return MessageResponse(message="Session revoked successfully.")

    async def revoke_all_sessions(self, user_id: str) -> MessageResponse:
        """
        Revokes all active sessions for a user.
        Used to "disconnect all devices".
        """
        count = await self.repo.revoke_all_by_user(user_id)
        return MessageResponse(
            message=f"{count} session(s) revoked successfully.",
        )

    async def list_sessions(self, user_id: str) -> SessionListResponse:
        """
        Returns all active sessions for a user.
        Allows the user to see their connected devices.
        """
        sessions = await self.repo.get_active_by_user(user_id)
        total = await self.repo.count_active_by_user(user_id)
        return SessionListResponse(
            sessions=[SessionResponse.model_validate(session) for session in sessions],
            total=total,
        )

    async def rotate_session(
            self,
            old_refresh_token: str,
            new_refresh_token_hash: str,
            new_expires_at: datetime,
    ) -> ValidateSessionResponse:
        """
        Refresh token rotation.

        Flow:
            1. Hash the raw token and retrieve the session directly from the database.
            2. Check: not revoked + not expired.
            3. Update the hash with the new token.
            4. If the old hash no longer matches, it is automatically invalidated.

        We do not reuse `validate_session()` to avoid SQLAlchemy transaction issues in the same query context.
        """
        # Step 1 – Search for the session directly by hash
        old_token_hash = _hash_token(old_refresh_token)
        session = await self.repo.get_by_token_hash(old_token_hash)

        # Step 2 – Checks
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token.",
            )

        if session.is_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token.",
            )

        now = datetime.now(UTC)
        session_expires = session.expires_at
        if session_expires.tzinfo is None:
            session_expires = session_expires.replace(tzinfo=UTC)

        if session_expires < now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token.",
            )

        # Step 3 – Update the hash
        await self.repo.update_token_hash(
            session_id=session.id,
            new_token_hash=new_refresh_token_hash,
            new_expires_at=new_expires_at,
        )

        return ValidateSessionResponse(
            valid=True,
            user_id=session.user_id,
            session_id=session.id,
        )