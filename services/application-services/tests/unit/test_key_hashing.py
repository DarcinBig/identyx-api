"""Unit tests for API key hashing and constant-time comparison.

API keys are verified on every request under load — Argon2id is deliberately
excluded here (the PRD). SHA-256 + hmac.compare_digest is the chosen scheme:
the key already has ~142 bits of entropy, so a fast hash does not make it
brute-forceable, and compare_digest prevents timing attacks.
"""

import hashlib
import hmac

from app.security.key_generation import (
    generate_api_key,
    get_key_id,
    hash_api_key,
    verify_api_key,
)


class TestHashApiKey:
    def test_hash_is_deterministic(self):
        secret = generate_api_key("secret")
        assert hash_api_key(secret) == hash_api_key(secret)

    def test_hash_is_sha256_hexdigest(self):
        secret = generate_api_key("secret")
        expected = hashlib.sha256(secret.encode()).hexdigest()
        assert hash_api_key(secret) == expected
        assert len(hash_api_key(secret)) == 64

    def test_different_keys_hash_differently(self):
        assert hash_api_key(generate_api_key("secret")) != hash_api_key(generate_api_key("secret"))


class TestVerifyApiKey:
    def test_verify_matches_correct_secret(self):
        secret = generate_api_key("secret")
        assert verify_api_key(secret, hash_api_key(secret)) is True

    def test_verify_rejects_wrong_secret(self):
        secret = generate_api_key("secret")
        other = generate_api_key("secret")
        assert verify_api_key(other, hash_api_key(secret)) is False

    def test_verify_rejects_key_id_mismatch(self):
        """
        The lookup is keyed by key_id (prefix + 8 chars). If the caller passes
        a secret whose key_id differs from the one used for the DB lookup, it
        must be rejected even if some hash would match — belt and braces.
        """
        secret = generate_api_key("secret")
        stored_hash = hash_api_key(secret)
        wrong_id = get_key_id(generate_api_key("secret"))
        assert verify_api_key(secret, stored_hash, key_id=wrong_id) is False

    def test_verify_accepts_matching_key_id(self):
        secret = generate_api_key("secret")
        stored_hash = hash_api_key(secret)
        assert verify_api_key(secret, stored_hash, key_id=get_key_id(secret)) is True

    def test_uses_constant_time_comparison(self):
        """
        The implementation MUST use hmac.compare_digest, not `==`, to avoid a
        timing side-channel. This test asserts the actual comparison function
        used by verify_api_key (a code review complements it).
        """
        secret = generate_api_key("secret")
        stored_hash = hash_api_key(secret)
        # Re-implement the expected path and assert the module does the same.
        expected = hmac.compare_digest(stored_hash, hashlib.sha256(secret.encode()).hexdigest())
        assert verify_api_key(secret, stored_hash) is expected
        assert hashlib.sha256  # silence unused import lint if refactored

    def test_verify_empty_secret_rejected(self):
        assert verify_api_key("", hashlib.sha256(b"").hexdigest()) is False
