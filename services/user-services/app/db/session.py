from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# SQLAlchemy requires psycopg as its async driver
# We replace postgresql:// with postgres+psycopg://
_db_url = settings.database_url.replace("postgresql://", "postgresql+psycopg://")

engine = create_async_engine(
    _db_url,
    echo=settings.debug,  # displays SQL queries in debug mode
    pool_pre_ping=True,  # checks the connection before each request
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models in the service.
    Each model inherits from this class.
    """
    pass


async def get_db() -> AsyncSession:
    """
    FastAPI dependency injection.

    Usage in a route:
        async def my_route(db: AsyncSession = Depends(get_db)):
            ...

    Automatically handles commit/rollback/close.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
