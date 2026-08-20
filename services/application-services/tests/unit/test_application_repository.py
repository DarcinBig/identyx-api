"""Unit tests for the ApplicationRepository (CRUD)."""

import uuid

import pytest
from sqlalchemy import select

from app.repositories.application_repo import ApplicationRepository
from app.schemas.application import ApplicationCreate, ApplicationUpdate


@pytest.mark.asyncio
async def test_create_application(db_session):
    repo = ApplicationRepository(db_session)
    app = await repo.create(
        ApplicationCreate(
            name="My App",
            owner_email="owner@example.com",
            allowed_origins=["https://app.example.com"],
        )
    )

    assert app.id is not None
    assert app.tenant_id is not None
    assert app.name == "My App"
    assert app.owner_email == "owner@example.com"
    assert app.allowed_origins == ["https://app.example.com"]
    assert app.status == "active"


@pytest.mark.asyncio
async def test_create_application_assigns_tenant_id(db_session):
    """1 application = 1 tenant in V1.1: tenant_id is assigned at creation."""
    repo = ApplicationRepository(db_session)
    first = await repo.create(ApplicationCreate(name="App 1", owner_email="a@example.com"))
    second = await repo.create(ApplicationCreate(name="App 2", owner_email="a@example.com"))

    assert first.tenant_id != second.tenant_id


@pytest.mark.asyncio
async def test_get_by_id(db_session):
    repo = ApplicationRepository(db_session)
    created = await repo.create(ApplicationCreate(name="My App", owner_email="owner@example.com"))
    await db_session.commit()

    found = await repo.get_by_id(created.id)
    assert found is not None
    assert found.id == created.id


@pytest.mark.asyncio
async def test_get_by_id_missing_returns_none(db_session):
    repo = ApplicationRepository(db_session)
    assert await repo.get_by_id(str(uuid.uuid4())) is None


@pytest.mark.asyncio
async def test_get_by_tenant_id(db_session):
    repo = ApplicationRepository(db_session)
    created = await repo.create(ApplicationCreate(name="My App", owner_email="owner@example.com"))

    found = await repo.get_by_tenant_id(created.tenant_id)
    assert found is not None
    assert found.tenant_id == created.tenant_id


@pytest.mark.asyncio
async def test_update_application(db_session):
    repo = ApplicationRepository(db_session)
    created = await repo.create(
        ApplicationCreate(
            name="My App",
            owner_email="owner@example.com",
            allowed_origins=["https://a.example.com"],
        )
    )
    await db_session.commit()

    updated = await repo.update(
        created.id,
        ApplicationUpdate(name="Renamed", allowed_origins=["https://b.example.com"]),
    )
    assert updated is not None
    assert updated.name == "Renamed"
    assert updated.allowed_origins == ["https://b.example.com"]
    assert updated.owner_email == "owner@example.com"  # untouched


@pytest.mark.asyncio
async def test_update_missing_returns_none(db_session):
    repo = ApplicationRepository(db_session)
    result = await repo.update(str(uuid.uuid4()), ApplicationUpdate(name="X"))
    assert result is None


@pytest.mark.asyncio
async def test_delete_application_cascades_keys(db_session):
    from app.models.api_key import ApiKey
    from app.repositories.api_key_repo import ApiKeyRepository
    from app.security.key_generation import generate_api_key, hash_api_key

    app_repo = ApplicationRepository(db_session)
    key_repo = ApiKeyRepository(db_session)

    created = await app_repo.create(
        ApplicationCreate(name="My App", owner_email="owner@example.com")
    )
    await key_repo.create(
        application_id=created.id,
        key_id="pk_live_4f8a1c9d",
        key_hash=hash_api_key(generate_api_key("publishable")),
        key_type="publishable",
    )
    await db_session.commit()

    await app_repo.delete(created.id)
    await db_session.commit()

    assert await app_repo.get_by_id(created.id) is None
    remaining = (await db_session.execute(select(ApiKey))).scalars().all()
    assert remaining == []


@pytest.mark.asyncio
async def test_list_by_owner_email(db_session):
    repo = ApplicationRepository(db_session)
    await repo.create(ApplicationCreate(name="App 1", owner_email="owner@example.com"))
    await repo.create(ApplicationCreate(name="App 2", owner_email="owner@example.com"))
    await repo.create(ApplicationCreate(name="Other", owner_email="other@example.com"))
    await db_session.commit()

    apps = await repo.list_by_owner_email("owner@example.com")
    assert len(apps) == 2
    assert {a.name for a in apps} == {"App 1", "App 2"}
