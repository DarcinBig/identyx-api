"""Unit tests for purpose-bound HMAC verification tokens."""

import hashlib
import hmac

from app.core.config import get_settings
from app.security.verification import (
    PURPOSE_DELETE_ACCOUNT,
    PURPOSE_EMAIL_VERIFICATION,
    PURPOSE_PASSWORD_RESET,
    generate_verification_token,
    verify_verification_token,
)

settings = get_settings()


def test_token_roundtrip():
    """A token generated for a purpose must verify for that same purpose."""
    raw = generate_verification_token("uuid-123", purpose=PURPOSE_EMAIL_VERIFICATION)
    valid, user_id = verify_verification_token(raw, purpose=PURPOSE_EMAIL_VERIFICATION)
    assert valid is True
    assert user_id == "uuid-123"


def test_token_rejected_for_another_purpose():
    """A token minted for one flow must NOT verify in another flow."""
    raw = generate_verification_token("uuid-123", purpose=PURPOSE_DELETE_ACCOUNT)
    valid, _ = verify_verification_token(raw, purpose=PURPOSE_EMAIL_VERIFICATION)
    assert valid is False


def test_password_reset_purpose_roundtrip():
    """The password reset flow keeps working with its own purpose."""
    raw = generate_verification_token("uuid-123", purpose=PURPOSE_PASSWORD_RESET)
    valid, user_id = verify_verification_token(raw, purpose=PURPOSE_PASSWORD_RESET)
    assert valid is True
    assert user_id == "uuid-123"


def test_forged_signature_rejected():
    """A token with an invalid signature must be rejected."""
    message = "uuid-123.delete_account.1234"
    forged_sig = hmac.new(
        b"wrong-secret",
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    raw = f"{message}.{forged_sig}"
    valid, _ = verify_verification_token(raw, purpose=PURPOSE_DELETE_ACCOUNT)
    assert valid is False


def test_malformed_token_rejected():
    """A token with the wrong number of parts must be rejected."""
    valid, _ = verify_verification_token("only-two.parts", purpose=PURPOSE_EMAIL_VERIFICATION)
    assert valid is False
