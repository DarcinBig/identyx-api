"""Unit tests for the ApiKeyRepository (CRUD, revocation)."""

import pytest
from sqlalchemy import select

from app.models.api_key import ApiKey
from app.repositories.api_key_repo import ApiKeyRepository
from app.security.key_generation import generate_api_key, get_key_id, hash_api_key


def _secret_key() -> tuple[str, str]:
    """Returns (raw_secret, key_id) for a fresh secret key."""
    secret = generate_api_key("secret")
    return secret, get_key_id(secret)


async def _create_application(db_session) -> str:
    from app.repositories.application_repo import ApplicationRepository
    from app.schemas.application import ApplicationCreate

    repo = ApplicationRepository(db_session)
    app = await repo.create(ApplicationCreate(name="My App", owner_email="owner@example.com"))
    await db_session.commit()
    return app.id


@pytest.mark.asyncio
async def test_create_api_key(db_session):
    application_id = await _create_application(db_session)
    secret, key_id = _secret_key()

    repo = ApiKeyRepository(db_session)
    key = await repo.create(
        application_id=application_id,
        key_id=key_id,
        key_hash=hash_api_key(secret),
        key_type="secret",
    )

    assert key.id is not None
    assert key.application_id == application_id
    assert key.key_id == key_id
    assert key.key_hash == hash_api_key(secret)
    assert key.key_type == "secret"
    assert key.environment == "live"
    assert key.status == "active"
    assert key.scopes == []


@pytest.mark.asyncio
async def test_get_by_key_id(db_session):
    application_id = await _create_application(db_session)
    secret, key_id = _secret_key()

    repo = ApiKeyRepository(db_session)
    await repo.create(
        application_id=application_id,
        key_id=key_id,
        key_hash=hash_api_key(secret),
        key_type="secret",
    )
    await db_session.commit()

    found = await repo.get_by_key_id(key_id)
    assert found is not None
    assert found.key_id == key_id
    assert found.application_id == application_id


@pytest.mark.asyncio
async def test_get_by_key_id_missing_returns_none(db_session):
    repo = ApiKeyRepository(db_session)
    assert await repo.get_by_key_id("pk_live_00000000") is None


@pytest.mark.asyncio
async def test_list_by_application_id(db_session):
    application_id = await _create_application(db_session)
    repo = ApiKeyRepository(db_session)

    for _ in range(3):
        secret, key_id = _secret_key()
        await repo.create(
            application_id=application_id,
            key_id=key_id,
            key_hash=hash_api_key(secret),
            key_type="secret",
        )
    await db_session.commit()

    keys = await repo.list_by_application_id(application_id)
    assert len(keys) == 3
    assert all(k.application_id == application_id for k in keys)


@pytest.mark.asyncio
async def test_list_by_application_id_isolates_applications(db_session):
    app_a = await _create_application(db_session)
    app_b = await _create_application(db_session)
    repo = ApiKeyRepository(db_session)

    secret_a, key_id_a = _secret_key()
    secret_b, key_id_b = _secret_key()
    await repo.create(
        application_id=app_a, key_id=key_id_a, key_hash=hash_api_key(secret_a), key_type="secret"
    )
    await repo.create(
        application_id=app_b, key_id=key_id_b, key_hash=hash_api_key(secret_b), key_type="secret"
    )
    await db_session.commit()

    keys_a = await repo.list_by_application_id(app_a)
    assert [k.key_id for k in keys_a] == [key_id_a]


@pytest.mark.asyncio
async def test_revoke_key(db_session):
    application_id = await _create_application(db_session)
    secret, key_id = _secret_key()

    repo = ApiKeyRepository(db_session)
    await repo.create(
        application_id=application_id,
        key_id=key_id,
        key_hash=hash_api_key(secret),
        key_type="secret",
    )
    await db_session.commit()

    revoked = await repo.revoke(key_id)
    assert revoked is True
    await db_session.commit()

    stored = (await db_session.execute(select(ApiKey).where(ApiKey.key_id == key_id))).scalar_one()
    assert stored.status == "revoked"
    assert stored.revoked_at is not None


@pytest.mark.asyncio
async def test_revoke_missing_key_returns_false(db_session):
    repo = ApiKeyRepository(db_session)
    assert await repo.revoke("pk_live_00000000") is False


@pytest.mark.asyncio
async def test_delete_by_key_id(db_session):
    application_id = await _create_application(db_session)
    secret, key_id = _secret_key()

    repo = ApiKeyRepository(db_session)
    await repo.create(
        application_id=application_id,
        key_id=key_id,
        key_hash=hash_api_key(secret),
        key_type="secret",
    )
    await db_session.commit()

    deleted = await repo.delete_by_key_id(key_id)
    assert deleted is True
    await db_session.commit()

    remaining = (await db_session.execute(select(ApiKey))).scalars().all()
    assert remaining == []


@pytest.mark.asyncio
async def test_key_id_unique_constraint(db_session):
    application_id = await _create_application(db_session)
    secret, key_id = _secret_key()

    repo = ApiKeyRepository(db_session)
    await repo.create(
        application_id=application_id,
        key_id=key_id,
        key_hash=hash_api_key(secret),
        key_type="secret",
    )
    await db_session.commit()

    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await repo.create(
            application_id=application_id,
            key_id=key_id,
            key_hash=hash_api_key(secret),
            key_type="secret",
        )
        await db_session.commit()
