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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

from app.core.config import settings
from app.core.migrations import migrate_existing_schema

ModelType = TypeVar("ModelType", bound=SQLModel)

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


def import_all_models() -> None:
    """Import all SQLModel models so relationship targets are registered."""
    import app.billing.models  # noqa: F401
    import app.devices.models  # noqa: F401
    import app.referrals.models  # noqa: F401
    import app.routing.models  # noqa: F401
    import app.users.models  # noqa: F401
    import app.vpn.models  # noqa: F401


async def init_db() -> None:
    """Initialize database tables."""
    import_all_models()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await migrate_existing_schema(conn)


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


async def get_by_id(session: AsyncSession, model: type[ModelType], id: int) -> ModelType | None:
    """Get a model instance by ID."""
    return await session.get(model, id)
