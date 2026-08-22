from pydantic import BaseModel


class GenerateTokenRequest(BaseModel):
    """
    Request to generate a token pair.
    Called by the auth-service after successful login or registration.
    """
    user_id: str
    application_id: str = "identyx-api"
    tenant_id: str = "00000000-0000-0000-0000-000000000001"

class VerifyTokenRequest(BaseModel):
    """
    Request to validate an access token.
    Returns valid=True/False without raising an exception.
    """
    access_token: str

class RevokeTokenRequest(BaseModel):
    """
    Request to revoke an access token.
    The JTI is blacklisted on Redis with a TTL.
    """
    access_token: str

class TokenPairResponse(BaseModel):
    """
    Token pair returned after generation.

    `refresh_token_hash`: SHA-256 hash of the refresh token.
    Returned so that the session service can store it in sessions-service.
    """
    access_token: str
    refresh_token: str              # raw token → sent to the client
    refresh_token_hash: str         # SHA-256 hash → stored in the database (sessions-service)
    token_type: str = 'Bearer'
    expires_in: int                 # seconds before access token expires

class VerifyTokenResponse(BaseModel):
    """Result of access token validation."""
    valid: bool
    user_id: str | None = None
    jti: str | None = None
    application_id: str | None = None
    tenant_id: str | None = None

class RevokeTokenResponse(BaseModel):
    """Confirmation of revocation."""
    message: str