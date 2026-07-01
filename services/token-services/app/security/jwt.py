"""
JWT generation and validation with python-jose.

Payload access token:
    {
        "sub": "user_id",
        "type": "access",
        "jti": "uuid4", ← unique identifier for the blacklist
        "iat": timestamp,
        "exp": timestamp,

    }

Refresh token:
    - Opaque token generated with secrets.token_urlsafe(64)
    - SHA-256 hashed before storage (sessions-service)
    - Never decoded — only compared to the stored hash
"""
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import get_settings

settings = get_settings()

def generate_access_token(user_id: str) -> tuple[str, str, datetime]:
    """
    Generates a JWT access token signed HS256.

    :return:
        - The JWT token (str)
        - The token's JTI (str) — for blacklisting
        - The expiration date (UTC datetime)
    """
    jti = str(uuid.uuid4())
    now = datetime.now(UTC)
    expires_at = now + timedelta(
        minutes=settings.access_token_expire_minutes,
    )

    payload = {
        "sub": user_id,
        "type": "access",
        "jti": jti,
        "iat": now,
        "exp": expires_at,
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token, jti, expires_at

def decode_access_token(token: str) -> dict:
    """
    Decodes and validates a JWT access token.

    Checks: signature, expiration, type = "access".
    Returns the decoded payload.

    Reasons:
        401 if invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload

def generate_refresh_token() -> tuple[str, str]:
    """
    Generates an opaque refresh token.

    Returns:
        - raw_token: sent to the client (never stored in plain text)
        - token_hash: SHA-256 hash, stored in the database in sessions-service
    """
    raw_token = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash

def hash_refresh_token(raw_token: str) -> str:
    """SHA-256 hash of a raw refresh token."""
    return hashlib.sha256(raw_token.encode()).hexdigest()
