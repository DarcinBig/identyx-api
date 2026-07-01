from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

settings = get_settings()

# Instantiated only once when the service starts
# PasswordHasher is thread-safe
_hasher = PasswordHasher(
    time_cost=settings.argon2_time_cost,
    memory_cost=settings.argon2_memory_cost,
    parallelism=settings.argon2_parallelism,
    hash_len=settings.argon2_hash_len,
    salt_len=settings.argon2_salt_len,
)

def hash_password(plain_password: str) -> str:
    """
    Hashes a plaintext password using Argon2id.

    - Salt is randomly generated on each call.
    - Two calls with the same password produce two different hashes.
    - Returns the full hash to be stored directly in the database.
    :param plain_password:
    :return: _hasher.hash()
    """
    return _hasher.hash(plain_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies that a password matches the stored hash.

    - Returns True if correct, False otherwise
    - Never propagates an exception to the caller
    - Resistant to timing attacks (natively handled by argon2-cffi)
    :param plain_password:
    :param hashed_password:
    :return: True if correct, False otherwise
    """
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False

def needs_rehash(hashed_password: str) -> bool:
    """
    Checks if an existing hash needs to be recalculated.

    Useful when changing Argon2 settings in production:
    After a successful login, you can silently update
    the hash without invalidating existing accounts.
    :param hashed_password:
    :return: _hasher.check_needs_rehash()
    """
    return _hasher.check_needs_rehash(hashed_password)