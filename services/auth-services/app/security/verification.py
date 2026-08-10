"""
Generation and verification of HMAC-SHA256 one-time tokens.

Why HMAC instead of JWT?
  - The token does not contain complex claims
  - HMAC is more lightweight and sufficient for this use case
  - Expiration is managed in the database (email_verifications table)
  - Revocation is managed in the database (is_used=True)

Raw token format:
  {user_id}.{purpose}.{timestamp}.{hmac_signature}

  - user_id        : User UUID
  - purpose        : "email_verification" | "password_reset" |
                     "delete_account" | "email_change"
  - timestamp      : Creation Unix timestamp (int)
  - hmac_signature : HMAC-SHA256 of "{user_id}.{purpose}.{timestamp}"
                     using JWT_SECRET_KEY

The purpose is bound to the signature, so a token minted for one flow
cannot be replayed in another (e.g. a delete_account token cannot verify
an email).

The raw token is sent in the email link.
Only the SHA-256 hash of the raw token is stored in the database.
"""
import hashlib
import hmac
import time

from app.core.config import get_settings

settings = get_settings()

PURPOSE_EMAIL_VERIFICATION = "email_verification"
PURPOSE_PASSWORD_RESET = "password_reset"
PURPOSE_DELETE_ACCOUNT = "delete_account"
PURPOSE_EMAIL_CHANGE = "email_change"

def generate_verification_token(user_id: str, purpose: str = PURPOSE_EMAIL_VERIFICATION) -> str:
    """
    Generates an HMAC-SHA256 one-time token.

    Args:
        user_id: User's UUID
        purpose: Flow the token is minted for (bound into the signature)

    Returns:
        Raw token in the format "{user_id}.{purpose}.{timestamp}.{signature}"
        This token is sent in the email link.
        The SHA-256 hash of this token is stored in the database.
    """
    timestamp = int(time.time())
    message = f"{user_id}.{purpose}.{timestamp}"

    signature = hmac.new(
        settings.jwt_secret_key.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()

    return f"{message}.{signature}"

def verify_verification_token(
    raw_token: str,
    purpose: str = PURPOSE_EMAIL_VERIFICATION,
) -> tuple[bool, str | None]:
    """
    Verifies the HMAC signature of a one-time token.

    Args:
        raw_token: The raw token received from the email link.
        purpose: Expected purpose (must match the one used at generation).

    Returns:
        (True, user_id) if the signature is valid and the purpose matches.
        (False, None) if the signature is invalid or the format is incorrect.

    Note: This function verifies ONLY the cryptographic signature.
    Expiration and is_used status are checked separately in the database.
    """
    try:
        parts = raw_token.split(".")
        if len(parts) != 4:
            return False, None

        user_id, token_purpose, timestamp_str, received_signature = parts

        if token_purpose != purpose:
            return False, None

        # Recalculate the expected signature
        message = f"{user_id}.{token_purpose}.{timestamp_str}"
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