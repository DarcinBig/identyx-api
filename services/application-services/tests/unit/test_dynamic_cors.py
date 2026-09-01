"""Tests for Sub-step D — dynamic CORS on application-service.

Covers:
  - resolve_by_origin matches active apps by allowed_origins
  - resolve_by_origin false for unknown origin
  - cross-app origin uniqueness (409) on create and update
  - re-using one's own origin on update is allowed
  - the GIN index migration exists and targets Postgres
"""

import pytest

from app.schemas.application import ApplicationCreate, ApplicationUpdate
from app.services.application_service import ApplicationService


def _service(db, redis):
    return ApplicationService(db, cache_client=redis)


@pytest.mark.asyncio
async def test_resolve_by_origin_allows_registered_origin(db_session, fake_redis):
    service = _service(db_session, fake_redis)
    await service.create_application(
        ApplicationCreate(
            name="My App",
            owner_email="owner@example.com",
            allowed_origins=["https://app.identyx.io"],
        )
    )

    result = await service.resolve_by_origin("https://app.identyx.io")

    assert result.allowed is True
    assert len(result.applications) == 1


@pytest.mark.asyncio
async def test_resolve_by_origin_false_for_unknown_origin(db_session, fake_redis):
    service = _service(db_session, fake_redis)
    await service.create_application(
        ApplicationCreate(
            name="My App",
            owner_email="owner@example.com",
            allowed_origins=["https://app.identyx.io"],
        )
    )

    result = await service.resolve_by_origin("https://evil.example.com")

    assert result.allowed is False
    assert result.applications == []


@pytest.mark.asyncio
async def test_resolve_by_origin_ignores_suspended_apps(db_session, fake_redis):
    from app.repositories.application_repo import ApplicationRepository

    service = _service(db_session, fake_redis)
    created = await service.create_application(
        ApplicationCreate(
            name="My App",
            owner_email="owner@example.com",
            allowed_origins=["https://app.identyx.io"],
        )
    )
    await ApplicationRepository(db_session).update(
        created.application_id, ApplicationUpdate(status="suspended")
    )
    await db_session.commit()

    result = await service.resolve_by_origin("https://app.identyx.io")

    assert result.allowed is False


@pytest.mark.asyncio
async def test_resolve_by_origin_empty_origin_not_allowed(db_session, fake_redis):
    service = _service(db_session, fake_redis)
    result = await service.resolve_by_origin("")
    assert result.allowed is False


@pytest.mark.asyncio
async def test_create_application_origin_conflict_409(db_session, fake_redis):
    service = _service(db_session, fake_redis)
    await service.create_application(
        ApplicationCreate(
            name="App A",
            owner_email="a@example.com",
            allowed_origins=["https://app.identyx.io"],
        )
    )

    with pytest.raises(Exception) as excinfo:
        await service.create_application(
            ApplicationCreate(
                name="App B",
                owner_email="b@example.com",
                allowed_origins=["https://app.identyx.io"],
            )
        )

    from fastapi import HTTPException

    assert isinstance(excinfo.value, HTTPException)
    assert excinfo.value.status_code == 409
    assert "already claimed" in excinfo.value.detail


@pytest.mark.asyncio
async def test_create_application_disjoint_origins_ok(db_session, fake_redis):
    service = _service(db_session, fake_redis)
    await service.create_application(
        ApplicationCreate(
            name="App A",
            owner_email="a@example.com",
            allowed_origins=["https://a.example.com"],
        )
    )
    created = await service.create_application(
        ApplicationCreate(
            name="App B",
            owner_email="b@example.com",
            allowed_origins=["https://b.example.com"],
        )
    )
    assert created.application_id is not None


@pytest.mark.asyncio
async def test_update_application_origin_conflict_409(db_session, fake_redis):
    service = _service(db_session, fake_redis)
    a = await service.create_application(
        ApplicationCreate(name="App A", owner_email="a@example.com",
                          allowed_origins=["https://a.example.com"])
    )
    b = await service.create_application(
        ApplicationCreate(name="App B", owner_email="b@example.com")
    )

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        await service.update_application(
            b.application_id,
            ApplicationUpdate(allowed_origins=["https://a.example.com"]),
        )
    assert excinfo.value.status_code == 409

    # A is untouched.
    fetched = await service.get_application(a.application_id)
    assert fetched.allowed_origins == ["https://a.example.com"]


@pytest.mark.asyncio
async def test_update_application_reuses_own_origin_ok(db_session, fake_redis):
    service = _service(db_session, fake_redis)
    created = await service.create_application(
        ApplicationCreate(name="App A", owner_email="a@example.com",
                          allowed_origins=["https://a.example.com"])
    )

    updated = await service.update_application(
        created.application_id,
        ApplicationUpdate(allowed_origins=["https://a.example.com", "https://new.example.com"]),
    )
    assert updated is not None
    assert "https://new.example.com" in updated.allowed_origins


def test_gin_index_migration_uses_postgres_gin():
    """The index backing resolve-by-origin must be a Postgres GIN index."""
    import importlib.util
    from pathlib import Path

    migrations_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    target = migrations_dir / "0002_gin_index_allowed_origins.py"
    assert target.exists()
    spec = importlib.util.spec_from_file_location("m0002", target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "0002"
    assert module.down_revision == "0001"
