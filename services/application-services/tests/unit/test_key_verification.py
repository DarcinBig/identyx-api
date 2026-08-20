"""Unit tests for API key verification — the core of application-service.

Covers: valid key, wrong secret, revoked key, missing key, suspended app
(even with an active key), and cache round-trips.
"""

from unittest.mock import patch

import pytest

from app.schemas.application import ApplicationCreate, ApplicationUpdate
from app.security.key_generation import get_key_id
from app.services.application_service import ApplicationService


def _service(db, redis):
    return ApplicationService(db, cache_client=redis)


@pytest.mark.asyncio
async def test_verify_key_valid_secret(db_session, fake_redis):
    service = _service(db_session, fake_redis)
    created = await service.create_application(
        ApplicationCreate(name="My App", owner_email="owner@example.com")
    )

    result = await service.verify_key(created.secret_key, created.secret_key)

    assert result is not None
    assert result.tenant_id == created.tenant_id
    assert result.application_id == created.application_id
    assert result.key_type == "secret"
    assert result.status == "active"


@pytest.mark.asyncio
async def test_verify_key_wrong_secret_returns_none(db_session, fake_redis):
    service = _service(db_session, fake_redis)
    created = await service.create_application(
        ApplicationCreate(name="My App", owner_email="owner@example.com")
    )

    result = await service.verify_key(created.publishable_key, created.publishable_key + "tampered")

    assert result is None


@pytest.mark.asyncio
async def test_verify_key_unknown_key_returns_none(db_session, fake_redis):
    service = _service(db_session, fake_redis)
    result = await service.verify_key("pk_live_00000000", "whatever")
    assert result is None


@pytest.mark.asyncio
async def test_verify_key_publishable_key(db_session, fake_redis):
    """A publishable key must resolve too (used by the browser SDK)."""
    service = _service(db_session, fake_redis)
    created = await service.create_application(
        ApplicationCreate(name="My App", owner_email="owner@example.com")
    )

    result = await service.verify_key(created.publishable_key, created.publishable_key)

    assert result is not None
    assert result.key_type == "publishable"
    assert result.tenant_id == created.tenant_id


@pytest.mark.asyncio
async def test_verify_key_revoked_key_returns_none(db_session, fake_redis):
    service = _service(db_session, fake_redis)
    created = await service.create_application(
        ApplicationCreate(name="My App", owner_email="owner@example.com")
    )

    await service.revoke_key(created.application_id, get_key_id(created.publishable_key))

    result = await service.verify_key(created.publishable_key, created.publishable_key)
    assert result is None


@pytest.mark.asyncio
async def test_verify_key_revoked_secret_key_returns_none(db_session, fake_redis):
    service = _service(db_session, fake_redis)
    created = await service.create_application(
        ApplicationCreate(name="My App", owner_email="owner@example.com")
    )

    await service.revoke_key(created.application_id, get_key_id(created.secret_key))

    result = await service.verify_key(created.secret_key, created.secret_key)
    assert result is None


@pytest.mark.asyncio
async def test_verify_key_suspended_application_returns_none(db_session, fake_redis):
    """An app with status='suspended' blocks all its keys, even active ones."""
    from app.repositories.application_repo import ApplicationRepository

    service = _service(db_session, fake_redis)
    created = await service.create_application(
        ApplicationCreate(name="My App", owner_email="owner@example.com")
    )

    repo = ApplicationRepository(db_session)
    await repo.update(created.application_id, ApplicationUpdate(status="suspended"))
    await db_session.commit()

    result = await service.verify_key(created.secret_key, created.secret_key)
    assert result is None


@pytest.mark.asyncio
async def test_verify_key_caches_result(db_session, fake_redis):
    """After a first hit, the resolution must come from the Redis cache (DB 3)."""
    service = _service(db_session, fake_redis)
    created = await service.create_application(
        ApplicationCreate(name="My App", owner_email="owner@example.com")
    )

    await service.verify_key(created.secret_key, created.secret_key)
    cache_key = f"apikey:{get_key_id(created.secret_key)}"
    cached = await fake_redis.get(cache_key)
    assert cached is not None

    result = await service.verify_key(created.secret_key, created.secret_key)
    assert result is not None
    assert result.tenant_id == created.tenant_id


@pytest.mark.asyncio
async def test_verify_key_resolves_from_cache_without_db(db_session, fake_redis):
    """Once cached, a resolution must not touch the DB (fast path < ~5ms p95)."""
    from app.repositories.api_key_repo import ApiKeyRepository

    service = _service(db_session, fake_redis)
    created = await service.create_application(
        ApplicationCreate(name="My App", owner_email="owner@example.com")
    )
    await service.verify_key(created.secret_key, created.secret_key)

    # Revoke in DB but NOT in cache — a cache hit must still return the cached
    # (stale) value, proving the DB was not consulted.
    repo = ApiKeyRepository(db_session)
    await repo.revoke(get_key_id(created.secret_key))
    await db_session.commit()

    with patch.object(ApiKeyRepository, "get_by_key_id", wraps=repo.get_by_key_id) as mocked:
        result = await service.verify_key(created.secret_key, created.secret_key)
        mocked.assert_not_called()

    assert result is not None
    assert result.status == "active"


@pytest.mark.asyncio
async def test_verify_key_cache_hit_still_validates_secret(db_session, fake_redis):
    """Regression: a cache hit must NOT bypass the secret check.

    The cache is keyed by key_id (prefix + first 8 random chars), so any
    presented key sharing that key_id hits the fast path. The secret must be
    re-validated against the stored hash even there — otherwise a wrong
    secret with the same key_id would be accepted during the TTL window.
    """
    service = _service(db_session, fake_redis)
    created = await service.create_application(
        ApplicationCreate(name="My App", owner_email="owner@example.com")
    )
    # Warm the cache with the real key.
    assert await service.verify_key(created.secret_key, created.secret_key) is not None
    assert await fake_redis.get(f"apikey:{get_key_id(created.secret_key)}") is not None

    tampered = created.secret_key[:-1] + ("X" if created.secret_key[-1] != "X" else "Y")
    assert tampered != created.secret_key
    assert get_key_id(tampered) == get_key_id(created.secret_key)

    result = await service.verify_key(tampered, tampered)
    assert result is None


@pytest.mark.asyncio
async def test_revoke_key_invalidates_cache(db_session, fake_redis):
    """Revocation must actively invalidate the cache — no 60s TTL wait."""
    service = _service(db_session, fake_redis)
    created = await service.create_application(
        ApplicationCreate(name="My App", owner_email="owner@example.com")
    )
    await service.verify_key(created.secret_key, created.secret_key)

    cache_key = f"apikey:{get_key_id(created.secret_key)}"
    assert await fake_redis.get(cache_key) is not None

    await service.revoke_key(created.application_id, get_key_id(created.secret_key))

    assert await fake_redis.get(cache_key) is None
    result = await service.verify_key(created.secret_key, created.secret_key)
    assert result is None


@pytest.mark.asyncio
async def test_create_application_returns_key_pair(db_session, fake_redis):
    service = _service(db_session, fake_redis)
    created = await service.create_application(
        ApplicationCreate(name="My App", owner_email="owner@example.com")
    )

    assert created.application_id is not None
    assert created.tenant_id is not None
    assert created.publishable_key.startswith("pk_live_")
    assert created.secret_key.startswith("sk_live_")
    assert created.secret_key != created.publishable_key


@pytest.mark.asyncio
async def test_rotate_key_issues_new_pair(db_session, fake_redis):
    service = _service(db_session, fake_redis)
    created = await service.create_application(
        ApplicationCreate(name="My App", owner_email="owner@example.com")
    )
    await service.verify_key(created.secret_key, created.secret_key)

    rotated = await service.create_key(created.application_id)

    assert rotated.publishable_key != created.publishable_key
    assert rotated.secret_key != created.secret_key
    # The old key must still work during rotation (double-active for no downtime).
    assert await service.verify_key(created.secret_key, created.secret_key) is not None
    # And the new one too.
    assert await service.verify_key(rotated.secret_key, rotated.secret_key) is not None
