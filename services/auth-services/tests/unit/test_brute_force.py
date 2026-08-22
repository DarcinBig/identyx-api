"""
Unit tests for the brute-force protection (per-account + per-IP).

The per-account counter (brute:email:{tenant_id}:{email}) must keep
protecting the account even when the attacker rotates IPs — that is the
core guarantee against credential stuffing with distributed sources.
Keys are now tenant-scoped: brute:email:{tenant_id}:{email}.
"""
from unittest.mock import patch

import fakeredis.aioredis as aioredis
import pytest
from fastapi import HTTPException

TENANT = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
async def fake_redis():
    redis = aioredis.FakeRedis(decode_responses=True)
    yield redis
    await redis.flushall()
    await redis.aclose()


async def _patch_redis(redis):
    """Patches get_brute_force_redis so the module uses the fake Redis."""
    from app.security import brute_force as brute_module

    async def _get(redis_url):
        return redis

    return patch.object(brute_module, "get_brute_force_redis", _get)


@pytest.mark.asyncio
async def test_failed_attempts_increment_account_counter(fake_redis):
    from app.security.brute_force import record_failed_attempt

    with await _patch_redis(fake_redis):
        for _ in range(3):
            await record_failed_attempt(
                email="victim@example.com",
                ip="10.0.0.1",
                redis_url="redis://x",
                lockout_minutes=15,
            )

    assert int(await fake_redis.get(f"brute:email:{TENANT}:victim@example.com")) == 3
    assert int(await fake_redis.get(f"brute:ip:{TENANT}:10.0.0.1")) == 3


@pytest.mark.asyncio
async def test_account_locked_regardless_of_ip_rotation(fake_redis):
    """
    An attacker rotating IPs must still be blocked once the account
    counter reaches the threshold — the account counter is IP-independent.
    """
    from fastapi import status

    from app.security.brute_force import check_brute_force, record_failed_attempt

    with await _patch_redis(fake_redis):
        # 5 failures from 5 different IPs (IP rotation)
        for i in range(5):
            await record_failed_attempt(
                email="victim@example.com",
                ip=f"10.0.0.{i}",
                redis_url="redis://x",
                lockout_minutes=15,
            )

        # A new, never-seen IP is blocked because the ACCOUNT is locked.
        with pytest.raises(HTTPException) as exc:
            await check_brute_force(
                email="victim@example.com",
                ip="203.0.113.99",
                redis_url="redis://x",
                max_attempts=5,
                lockout_minutes=15,
            )
        assert exc.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.asyncio
async def test_single_ip_attacking_many_accounts_is_blocked(fake_redis):
    """Many accounts from one IP → the IP counter (x3) locks out."""
    from fastapi import status

    from app.security.brute_force import check_brute_force, record_failed_attempt

    with await _patch_redis(fake_redis):
        for i in range(15):  # 15 > 5 * 3
            await record_failed_attempt(
                email=f"user{i}@example.com",
                ip="10.0.0.1",
                redis_url="redis://x",
                lockout_minutes=15,
            )

        with pytest.raises(HTTPException) as exc:
            await check_brute_force(
                email="brand-new@example.com",
                ip="10.0.0.1",
                redis_url="redis://x",
                max_attempts=5,
                lockout_minutes=15,
            )
        assert exc.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.asyncio
async def test_below_threshold_is_allowed(fake_redis):
    from app.security.brute_force import check_brute_force, record_failed_attempt

    with await _patch_redis(fake_redis):
        await record_failed_attempt(
            email="victim@example.com",
            ip="10.0.0.1",
            redis_url="redis://x",
            lockout_minutes=15,
        )

        # 1 < 5 → no exception
        await check_brute_force(
            email="victim@example.com",
            ip="10.0.0.1",
            redis_url="redis://x",
            max_attempts=5,
            lockout_minutes=15,
        )


@pytest.mark.asyncio
async def test_successful_login_resets_counters(fake_redis):
    from app.security.brute_force import (
        check_brute_force,
        record_failed_attempt,
        reset_brute_force,
    )

    with await _patch_redis(fake_redis):
        await record_failed_attempt(
            email="victim@example.com",
            ip="10.0.0.1",
            redis_url="redis://x",
            lockout_minutes=15,
        )

        await reset_brute_force(
            email="victim@example.com",
            ip="10.0.0.1",
            redis_url="redis://x",
        )

        # Counters are gone → allowed
        await check_brute_force(
            email="victim@example.com",
            ip="10.0.0.1",
            redis_url="redis://x",
            max_attempts=5,
            lockout_minutes=15,
        )

        assert await fake_redis.get(f"brute:email:{TENANT}:victim@example.com") is None


@pytest.mark.asyncio
async def test_fail_open_when_redis_unavailable(fake_redis):
    """
    If Redis is down, the login must not be blocked (fail-open).
    The check swallows exceptions and lets the request proceed.
    """
    from app.security import brute_force as brute_module

    async def _boom(redis_url):
        raise ConnectionError("redis down")

    with patch.object(brute_module, "get_brute_force_redis", _boom):
        await brute_module.check_brute_force(
            email="victim@example.com",
            ip="10.0.0.1",
            redis_url="redis://x",
            max_attempts=5,
            lockout_minutes=15,
        )
