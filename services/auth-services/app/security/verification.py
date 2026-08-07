"""
Generation and verification of HMAC-SHA256 tokens for email verification.

Why HMAC instead of JWT?
  - The verification token does not contain complex claims
  - HMAC is more lightweight and sufficient for this use case
  - Expiration is managed in the database (email_verifications table)
  - Revocation is managed in the database (is_used=True)

Raw token format:
  {user_id}.{timestamp}.{hmac_signature}

  - user_id        : User UUID
  - timestamp      : Creation Unix timestamp (int)
  - hmac_signature : HMAC-SHA256 of "{user_id}.{timestamp}" using JWT_SECRET_KEY

The raw token is sent in the email link.
Only the SHA-256 hash of the raw token is stored in the database.
"""
import hashlib
import hmac
import time

from app.core.config import get_settings

settings = get_settings()

def generate_verification_token(user_id: str) -> str:
    """
    Generates an HMAC-SHA256 verification token.

    Args:
        user_id: User's UUID

    Returns:
        Raw token in the format "{user_id}.{timestamp}.{signature}"
        This token is sent in the email link.
        The SHA-256 hash of this token is stored in the database.
    """
    timestamp = int(time.time())
    message = f"{user_id}.{timestamp}"

    signature = hmac.new(
        settings.jwt_secret_key.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()

    return f"{message}.{signature}"

def verify_verification_token(raw_token: str) -> tuple[bool, str | None]:
    """
    Verifies the HMAC signature of a verification token.

    Args:
        raw_token: The raw token received from the email link.

    Returns:
        (True, user_id) if the signature is valid.
        (False, None) if the signature is invalid or the format is incorrect.

    Note: This function verifies ONLY the cryptographic signature.
    Expiration and is_used status are checked separately in the database.
    """
    try:
        parts = raw_token.split(".")
        if len(parts) != 3:
            return False, None

        user_id, timestamp_str, received_signature = parts

        # Recalculate the expected signature
        message = f"{user_id}.{timestamp_str}"
        expected_signature = hmac.new(
            settings.jwt_secret_key.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        # Constant-time comparison — protection against timing attacks
        if not hmac.compare_digest(expected_signature, received_signature):
            return False, None

        return True, user_id

    except Exception:
        return False, None