"""
Brute-force protection on login.

Principle:
    - Redis key: brute:{ip}:{email}
    - After each failed login → increment the counter
    - After 5 failed logins → 15-minute lockout
    - After a successful login → reset the counter

Double IP + email key to protect:
    - the account (someone tests an email address from multiple IP addresses)
    - the IP address (someone tests multiple email addresses from the same IP address)

We use two separate keys:
    brute:email:{email} → protects the account
    brute:ip:{ip} → protects against distributed attacks
"""
import logging

import redis.asyncio as aioredis
from fastapi import HTTPException, status

logger = logging.getLogger("auth.brute_force")

# Shared Redis client
_redis: aioredis.Redis | None = None

async def get_brute_force_redis(redis_url: str) -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


async def check_brute_force(
    email: str,
    ip: str,
    redis_url: str,
    max_attempts: int = 5,
    lockout_minutes: int = 15,
) -> None:
    """
    Checks if the email or IP address is locked out.

    Reasons:
        429 if locked out, with the time remaining in the message.
    """
    try:
        redis = await get_brute_force_redis(redis_url)

        email_key = f"brute:email:{email.lower()}"
        ip_key = f"brute:ip:{ip}"

        # Check the lockout status on the email
        email_attempts = await redis.get(email_key)
        if email_attempts and int(email_attempts) >= max_attempts:
            ttl = await redis.ttl(email_key)
            logger.warning(
                "Brute force lockout: email=%s ip=%s ttl=%ds",
                email, ip, ttl
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Too many failed attempts. "
                    f"Account locked for {ttl} seconds."
                ),
                headers={"Retry-After": str(ttl)},
            )

        # Check the IP lockout
        ip_attempts = await redis.get(ip_key)
        if ip_attempts and int(ip_attempts) >= max_attempts * 3:
            # The IP address is more tolerant (x3) because multiple users
            # can share the same IP address (NAT, offices, etc.)
            ttl = await redis.ttl(ip_key)
            logger.warning(
                "IP brute force lockout: ip=%s ttl=%ds", ip, ttl
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Too many failed attempts from this IP. "
                    f"Blocked for {ttl} seconds."
                ),
                headers={"Retry-After": str(ttl)},
            )

    except HTTPException:
        raise
    except Exception as exc:
        # Fail open — si Redis est down, on laisse passer
        logger.warning("Brute force Redis unavailable: %s", exc)


async def record_failed_attempt(
    email: str,
    ip: str,
    redis_url: str,
    lockout_minutes: int = 15,
) -> None:
    """
    Logs a failed login attempt.
    Increments email and IP counters.
    TTL = lockout duration.
    """
    try:
        redis = await get_brute_force_redis(redis_url)
        lockout_seconds = lockout_minutes * 60

        email_key = f"brute:email:{email.lower()}"
        ip_key = f"brute:ip:{ip}"

        pipe = redis.pipeline()
        pipe.incr(email_key)
        pipe.expire(email_key, lockout_seconds)
        pipe.incr(ip_key)
        pipe.expire(ip_key, lockout_seconds)
        await pipe.execute()

        logger.info(
            "Failed login recorded: email=%s ip=%s",
            email, ip
        )

    except Exception as exc:
        logger.warning("Brute force record failed: %s", exc)


async def get_failed_attempts_count(
    email: str,
    ip: str,
    redis_url: str,
) -> int:
    """
    Reads the current failed-attempt counter for the email key.

    Must be called BEFORE reset_brute_force() so the caller can decide
    whether a successful login follows prior failures (suspicious login).

    Returns 0 if Redis is unavailable (fail-open).
    """
    try:
        redis = await get_brute_force_redis(redis_url)
        count = await redis.get(f"brute:email:{email.lower()}")
        return int(count) if count else 0
    except Exception as exc:
        logger.warning("Brute force counter read failed: %s", exc)
        return 0


async def reset_brute_force(
    email: str,
    ip: str,
    redis_url: str,
) -> None:
    """
    Resets the counters after a successful login.
    """
    try:
        redis = await get_brute_force_redis(redis_url)
        await redis.delete(
            f"brute:email:{email.lower()}",
            f"brute:ip:{ip}",
        )
        logger.info(
            "Brute force reset after successful login: email=%s",
            email
        )
    except Exception as exc:
        logger.warning("Brute force reset failed: %s", exc)