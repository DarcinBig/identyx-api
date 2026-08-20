"""Unit tests for API key generation.

Covers the Stripe-aligned key format decided in the PRD:
  - publishable key:  pk_live_ + 24 base62 chars
  - secret key:       sk_live_ + 24 base62 chars
  - key_id (stored in DB for fast lookup): prefix + first 8 chars of the random part
  - the full string (prefix + 24 chars) IS the secret — never split.
"""

import pytest

from app.security.key_generation import (
    _RANDOM_PART_LENGTH,
    generate_api_key,
    generate_key_pair,
    get_key_id,
    is_valid_key_format,
)


class TestGenerateApiKey:
    def test_generate_secret_key_has_correct_format(self):
        secret = generate_api_key("secret")
        assert secret.startswith("sk_live_")
        assert len(secret) == len("sk_live_") + _RANDOM_PART_LENGTH

    def test_generate_publishable_key_has_correct_format(self):
        key = generate_api_key("publishable")
        assert key.startswith("pk_live_")
        assert len(key) == len("pk_live_") + _RANDOM_PART_LENGTH

    def test_random_part_is_base62(self):
        """The 24 random chars must only use [a-zA-Z0-9] (base62)."""
        import string

        allowed = set(string.ascii_letters + string.digits)
        secret = generate_api_key("secret")[len("sk_live_") :]
        assert all(c in allowed for c in secret)
        assert len(secret) == _RANDOM_PART_LENGTH

    @pytest.mark.parametrize("key_type", ["secret", "publishable"])
    def test_entropy_is_high(self, key_type):
        """24 base62 chars ≈ 142 bits — two consecutive keys must differ."""
        a = generate_api_key(key_type)
        b = generate_api_key(key_type)
        assert a != b

    def test_uniqueness_across_10000_generations(self):
        seen = {generate_api_key("secret") for _ in range(10_000)}
        assert len(seen) == 10_000

    def test_invalid_key_type_rejected(self):
        with pytest.raises(ValueError):
            generate_api_key("invalid")


class TestKeyIdExtraction:
    def test_key_id_is_prefix_plus_first_8_chars(self):
        """key_id stored in DB: pk_live_ + 8 chars (lookup portion, not secret)."""
        full = generate_api_key("publishable")
        expected = full[: len("pk_live_") + 8]
        assert get_key_id(full) == expected

    def test_key_id_is_short_and_identifiable(self):
        full = generate_api_key("secret")
        key_id = get_key_id(full)
        assert key_id.startswith("sk_live_")
        assert len(key_id) == len("sk_live_") + 8
        assert key_id in full  # visually present in the full key

    def test_invalid_key_id_raises(self):
        with pytest.raises(ValueError):
            get_key_id("not-a-valid-key")


class TestKeyPair:
    def test_key_pair_returns_pk_and_sk(self):
        pair = generate_key_pair()
        assert pair.publishable.startswith("pk_live_")
        assert pair.secret.startswith("sk_live_")
        assert pair.publishable != pair.secret

    def test_key_pair_ids(self):
        pair = generate_key_pair()
        assert get_key_id(pair.publishable).startswith("pk_live_")
        assert get_key_id(pair.secret).startswith("sk_live_")


class TestKeyFormatValidation:
    def test_valid_formats(self):
        assert is_valid_key_format(generate_api_key("secret"))
        assert is_valid_key_format(generate_api_key("publishable"))

    @pytest.mark.parametrize(
        "candidate",
        [
            "sk_live_short",
            "pk_test_1234567890abcdefghijklmnopqrstuv",
            "pk_live_",
            "pk_live_" + "a" * 23,
            "sk_live_" + "A" * 25,
            "jwt.token.here",
            "",
        ],
    )
    def test_invalid_formats(self, candidate):
        assert is_valid_key_format(candidate) is False

    def test_wrong_prefix_for_type_rejected(self):
        """A secret key must not be accepted as a publishable key and vice versa."""
        secret = generate_api_key("secret")
        publishable = generate_api_key("publishable")
        assert is_valid_key_format(secret, key_type="publishable") is False
        assert is_valid_key_format(publishable, key_type="secret") is False
