"""
Alembic env.py — user-service.

Reads database_url from app/core/config.py (Settings).
Imports UserCredential so that Base.metadata is aware of the table.
"""
import asyncio
import logging
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Add the service's root directory to the path
# so that "from app.xxx import yyy" works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.db.session import Base
from app.models.deletion_request import DeletionRequest  # noqa: F401
from app.models.email_change import EmailChange  # noqa: F401
from app.models.email_verification import EmailVerification  # noqa: F401

# IMPORTANT — import all models here
# so that Base.metadata registers them
from app.models.password_reset import PasswordReset  # noqa: F401
from app.models.user import User  # noqa: F401

settings = get_settings()

# Alembic config object (reads alembic.ini)
config = context.config

# Inject the URL from our Python config
# Replace postgresql:// with postgresql+psycopg:// for psycopg v3 async
_db_url = settings.database_url.replace(
    "postgresql://",
    "postgresql+psycopg://"
)
config.set_main_option("sqlalchemy.url", _db_url)

# Configure logging from alembic.ini
# disable_existing_loggers=False → alembic must NOT silence the
# application's loggers (they run in the same process during startup).
if config.config_file_name is not None:
    _app_root = logging.getLogger()
    _app_root_level = _app_root.level
    _app_root_handlers = _app_root.handlers[:]
    fileConfig(config.config_file_name, disable_existing_loggers=False)
    # fileConfig() replaces the root logger's level + handlers with the
    # values from alembic.ini ([logger_root] level=WARNING). When migrations
    # run inside the service process (startup), that mutes the app's
    # structured logs — restore the pre-existing root config here.
    if _app_root_handlers:
        _app_root.setLevel(_app_root_level)
        _app_root.handlers[:] = _app_root_handlers

# Target metadata — Alembic compares it with the actual database.
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """
    Offline mode — generates SQL without connecting to the database.
    Useful for generating migration scripts to be applied manually.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    """
    Online mode — connects to the database and applies migrations.
    Uses psycopg v3 in async mode (same driver as the app).
    """
    connectable = create_async_engine(
        _db_url,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())

