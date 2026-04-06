# FILE: backend/app/core/database.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Async database engine/session lifecycle and compatibility migrations
#   SCOPE: Engine creation, session factory, init_db (schema sync), get_db dependency
#   DEPENDS: M-001 (config), SQLModel, SQLAlchemy async
#   LINKS: M-001 (backend-core), all modules using DB, V-M-001
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   engine - AsyncEngine instance with NullPool for async compatibility
#   async_session_factory - Session factory for request-scoped sessions
#   init_db - SQLModel.create_all + compatibility migrations + admin/user bootstrap
#   get_db - FastAPI async_generator dependency for DB session with auto-commit
#   get_session - AsyncSession context manager for non-request scopes
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""
Database module for connection and session management.

GRACE-lite module contract:
- Owns engine/session creation and lightweight compatibility migrations on startup.
- `init_db()` is not a pure bootstrap helper: it can mutate existing schemas/data.
- `get_session()` auto-commits on successful request completion; service code usually flushes, not commits.
- The current project does not rely on a disciplined Alembic migration workflow yet.
"""
# <!-- GRACE: module="M-001" contract="database-connection" -->

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TypeVar

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

from app.core.config import settings
from app.core.migrations import migrate_existing_schema

ModelType = TypeVar("ModelType", bound=SQLModel)

# START_BLOCK_ENGINE_SESSION
# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    # Use NullPool for SQLite to avoid connection issues
    poolclass=NullPool if "sqlite" in settings.database_url else None,
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)
# END_BLOCK_ENGINE_SESSION


# START_BLOCK_IMPORT_MODELS
def import_all_models() -> None:
    """Import all SQLModel models so relationship targets are registered."""
    import app.billing.models  # noqa: F401
    import app.devices.models  # noqa: F401
    import app.referrals.models  # noqa: F401
    import app.routing.models  # noqa: F401
    import app.users.models  # noqa: F401
    import app.vpn.models  # noqa: F401
# END_BLOCK_IMPORT_MODELS


# START_BLOCK_INIT_DB
async def init_db() -> None:
    """Initialize database tables and convert timestamp columns to timestamptz."""
    import_all_models()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        # Convert all timestamp without time zone to timestamptz for PostgreSQL
        # Needed because P2-001 changed datetime.utcnow() → datetime.now(timezone.utc)
        if "postgresql" in settings.database_url:
            await conn.execute(text(
                "DO $d$ DECLARE r RECORD; "
                "BEGIN "
                "FOR r IN SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND data_type = 'timestamp without time zone' "
                "LOOP "
                "EXECUTE format('ALTER TABLE %I ALTER COLUMN %I TYPE timestamptz USING %I AT TIME ZONE ''UTC''', "
                "r.table_name, r.column_name, r.column_name); "
                "END LOOP; "
                "END $d$;"
            ))
        await migrate_existing_schema(conn)
# END_BLOCK_INIT_DB


# START_BLOCK_SESSION_HELPERS
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions (for use outside FastAPI)."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
# END_BLOCK_SESSION_HELPERS


# START_BLOCK_GET_BY_ID
async def get_by_id(session: AsyncSession, model: type[ModelType], id: int) -> ModelType | None:
    """Get a model instance by ID."""
    return await session.get(model, id)
# END_BLOCK_GET_BY_ID
