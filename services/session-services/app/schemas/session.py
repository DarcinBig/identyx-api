from datetime import datetime

from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    """
    Creates a new session after login or registration.
    Called by auth-service with the hash of the refresh token
    returned by token-service.
    """
    user_id: str
    refresh_token_hash: str      # SHA-256 hash from token-service
    device_info: str | None = None
    expires_at: datetime    # refresh token expiration date

class ValidateSessionRequest(BaseModel):
    """
    Validates an incoming refresh token.
    The raw token is hashed and retrieved from the database.
    """
    refresh_token: str      # raw token sent by the client

class RevokeSessionRequest(BaseModel):
    """Revokes a session using its refresh token."""
    refresh_token: str      # raw token sent by the client

class RotateSessionRequest(BaseModel):
    old_refresh_token: str
    new_refresh_token_hash: str
    new_expires_at: datetime

class SessionResponse(BaseModel):
    """Public presentation of a session."""
    id: str
    user_id: str
    device_info: str | None
    is_revoked: bool
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}

class ValidateSessionResponse(BaseModel):
    """
    Result of refreshing token validation.
    If valid=True, user_id and session_id are provided.
    """
    valid: bool
    user_id: str | None = None
    session_id: str | None = None

class SessionListResponse(BaseModel):
    """List of a user's active sessions."""
    sessions: list[SessionResponse]
    total: int

class MessageResponse(BaseModel):
    """Simple response with message."""
    message: str