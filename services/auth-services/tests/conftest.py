"""
Shared fixtures for auth-service tests.

- db_session : in-memory async SQLAlchemy session (SQLite)
- mock_redis  : in-memory Redis (fakeredis)
- app_client  : httpx.AsyncClient for the FastAPI app
- sample_user : test user data
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, get_db
from app.main import app

# --- In-memory database ------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    async_session = sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session

# --- Client App --------------------------------------------------

@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    """HTTP client against the FastAPI app with an in-memory database"""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as app_client:
        yield app_client

    app.dependency_overrides.clear()

# --- Test data ---------------------------------------------------

@pytest.fixture
def sample_user_data():
    return {
        "email": "test@example.com",
        "username": "testuser",
        "password": "TestPassword@123",
    }

@pytest.fixture
def invalid_password_data():
    """Passwords that must be rejected"""
    return [
        "short",
        "nouppercase@1",
        "NOLOWER@1",
        "NoSpecial1",
        "NoNumber@A",
    ]