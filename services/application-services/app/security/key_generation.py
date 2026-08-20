"""
API key generation, hashing and constant-time verification.

Key format (Stripe-aligned, decided in the PRD):
    pk_live_<24 base62 chars>     publishable key (browser-safe)
    sk_live_<24 base62 chars>     secret key (server-only)

The full string (prefix + 24 chars) IS the secret. There is no split between
a public and a private portion inside the key itself:
  - key_id (DB, for fast lookup)  : prefix + first 8 chars of the random part
  - key_hash (DB)                 : SHA-256 of the full secret string

Hashing scheme:
  - NOT Argon2id — API keys are verified on every request under load;
    Argon2id is deliberately slow and would blow up latency.
  - SHA-256 + hmac.compare_digest: the key already carries ~142 bits of
    entropy (24 base62 chars), so a fast hash is not brute-forceable, and
    compare_digest avoids a timing side-channel.
"""

import hashlib
import hmac
import secrets
import string
from dataclasses import dataclass

# 24 base62 chars ≈ 142 bits of entropy (coherent with Stripe/GitHub).
_RANDOM_PART_LENGTH = 24

# Portion of the random part stored as the (non-secret) lookup key_id.
_KEY_ID_LENGTH = 8

_BASE62 = string.ascii_uppercase + string.ascii_lowercase + string.digits

_PREFIX_BY_TYPE = {
    "publishable": "pk_live_",
    "secret": "sk_live_",
}


def generate_api_key(key_type: str) -> str:
    """Generates a full API key: `pk_live_`/`sk_live_` + 24 base62 chars."""
    try:
        prefix = _PREFIX_BY_TYPE[key_type]
    except KeyError:
        raise ValueError(f"Unknown key type: {key_type!r}") from None
    random_part = "".join(secrets.choice(_BASE62) for _ in range(_RANDOM_PART_LENGTH))
    return f"{prefix}{random_part}"


def get_key_id(full_key: str) -> str:
    """Extracts the lookup portion: prefix + first 8 random chars.

    key_id is not a secret — it is indexed in the DB for fast lookups and
    reused for visual identification in the dashboard.
    """
    for prefix in _PREFIX_BY_TYPE.values():
        if full_key.startswith(prefix):
            return full_key[: len(prefix) + _KEY_ID_LENGTH]
    raise ValueError("Invalid API key format.")


def hash_api_key(full_key: str) -> str:
    """SHA-256 hex digest of the full secret string."""
    return hashlib.sha256(full_key.encode()).hexdigest()


def verify_api_key(full_key: str, stored_hash: str, key_id: str | None = None) -> bool:
    """Verifies a full key against a stored hash in constant time.

    Optional `key_id` guards against lookups where the derived key_id does
    not match the row actually loaded (belt and braces on top of the DB
    lookup which is already keyed by key_id).
    """
    if not full_key:
        return False
    if key_id is not None:
        try:
            if get_key_id(full_key) != key_id:
                return False
        except ValueError:
            return False
    digest = hash_api_key(full_key)
    return hmac.compare_digest(stored_hash, digest)


def is_valid_key_format(full_key: str, key_type: str | None = None) -> bool:
    """Validates the full format: known prefix + exactly 24 base62 chars."""
    if not full_key:
        return False
    expected_prefixes = (
        [_PREFIX_BY_TYPE[key_type]] if key_type is not None else list(_PREFIX_BY_TYPE.values())
    )
    for prefix in expected_prefixes:
        if not full_key.startswith(prefix):
            continue
        random_part = full_key[len(prefix) :]
        if len(random_part) != _RANDOM_PART_LENGTH:
            return False
        return all(c in _BASE62 for c in random_part)
    return False


@dataclass(frozen=True)
class KeyPair:
    """A publishable/secret key pair for an application."""

    publishable: str
    secret: str


def generate_key_pair() -> KeyPair:
    """Generates a fresh publishable + secret key pair."""
    return KeyPair(
        publishable=generate_api_key("publishable"),
        secret=generate_api_key("secret"),
    )
