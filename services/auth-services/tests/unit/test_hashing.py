"""Unit tests for the Argon2id hashing module."""
from app.security.hashing import hash_password, needs_rehash, verify_password


class TestHashing:
    def test_hash_password_returns_string(self):
        result = hash_password("TestPassword@1")
        assert isinstance(result, str)

    def test_hash_password_starts_with_argon2id(self):
        result = hash_password("TestPassword@1")
        assert result.startswith("$argon2id")

    def test_hash_password_is_unique(self):
        """Two hashes of the same password must be different (salt)."""
        h1 = hash_password("TestPassword@1")
        h2 = hash_password("TestPassword@1")
        assert h1 != h2

    def test_verify_password_correct(self):
        password = "TestPassword@1"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_wrong(self):
        hashed = hash_password("TestPassword@1")
        assert verify_password("WrongPassword@1", hashed) is False

    def test_verify_password_empty(self):
        hashed = hash_password("TestPassword@1")
        assert verify_password("", hashed) is False

    def test_needs_rehash_fresh_hash(self):
        """A newly created hash must not require re-hashing."""
        hashed = hash_password("TestPassword@1")
        assert needs_rehash(hashed) is False