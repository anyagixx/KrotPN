# FILE: backend/alembic/env.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Alembic async migration environment — configure and run online/offline migrations
#   SCOPE: Async engine setup, autogenerate support, migration runner for SQLModel metadata
#   DEPENDS: M-001 (core database import_all_models), M-028 (migrations)
#   LINKS: M-028 (alembic-migrations), V-M-028
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   run_migrations_offline - Run migrations in offline mode (SQL output)
#   run_async_migrations - Run migrations with async engine
#   run_migrations_online - Entry point for online migration execution
#   do_run_migrations - Configure context and run migrations for a connection
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Converted to full GRACE MODULE_CONTRACT/MAP format, removed duplicate contract blocks
# END_CHANGE_SUMMARY
#
import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Add project root to path so app imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so SQLModel metadata is populated
from app.core.database import import_all_models
import_all_models()
from sqlmodel import SQLModel

target_metadata = SQLModel.metadata


# START_BLOCK_OFFLINE
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()
# END_BLOCK_OFFLINE


# START_BLOCK_DO_RUN
def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()
# END_BLOCK_DO_RUN


# START_BLOCK_ASYNC
async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()
# END_BLOCK_ASYNC


# START_BLOCK_ONLINE
def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
# END_BLOCK_ONLINE
