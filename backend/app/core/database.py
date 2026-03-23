"""
Database module for connection and session management.
"""
# <!-- GRACE: module="M-001" contract="database-connection" -->

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TypeVar

from loguru import logger
from sqlalchemy import bindparam, inspect, text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

from app.core.config import settings

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


def _partition_vpn_client_rows(
    rows: list[RowMapping],
) -> tuple[list[RowMapping], list[RowMapping]]:
    """Keep one VPN client row per user and mark the rest as duplicates."""
    keepers: list[RowMapping] = []
    duplicates: list[RowMapping] = []
    seen_user_ids: set[int] = set()

    for row in rows:
        user_id = int(row["user_id"])
        if user_id in seen_user_ids:
            duplicates.append(row)
            continue

        seen_user_ids.add(user_id)
        keepers.append(row)

    return keepers, duplicates


async def migrate_existing_schema(conn) -> None:
    """Apply lightweight compatibility migrations for already deployed databases."""
    await _deduplicate_vpn_clients(conn)
    await _ensure_unique_vpn_client_user_id(conn)


async def _deduplicate_vpn_clients(conn) -> None:
    """Collapse duplicate VPN client rows to a single record per user."""
    result = await conn.execute(
        text(
            """
            SELECT id, user_id, server_id, public_key, is_active, created_at, updated_at
            FROM vpn_clients
            ORDER BY
                user_id ASC,
                CASE WHEN is_active THEN 0 ELSE 1 END ASC,
                COALESCE(updated_at, created_at) DESC,
                created_at DESC,
                id DESC
            """
        )
    )
    rows = list(result.mappings())
    if not rows:
        return

    _, duplicates = _partition_vpn_client_rows(rows)
    if not duplicates:
        await _sync_vpn_server_client_counts(conn)
        return

    duplicate_ids = [int(row["id"]) for row in duplicates]
    duplicate_keys = [
        row["public_key"]
        for row in duplicates
        if bool(row["is_active"]) and row["public_key"]
    ]

    if duplicate_keys:
        from app.vpn.amneziawg import wg_manager

        for public_key in duplicate_keys:
            removed = await wg_manager.remove_peer(public_key)
            if not removed:
                logger.warning(
                    f"[DB] Failed to remove duplicate VPN peer during migration: {public_key[:20]}..."
                )

    await conn.execute(
        text("DELETE FROM vpn_clients WHERE id IN :duplicate_ids").bindparams(
            bindparam("duplicate_ids", expanding=True)
        )
        ,
        {"duplicate_ids": duplicate_ids},
    )
    await _sync_vpn_server_client_counts(conn)

    logger.warning(
        f"[DB] Removed {len(duplicate_ids)} duplicate vpn_clients rows during schema migration"
    )


async def _sync_vpn_server_client_counts(conn) -> None:
    """Recalculate vpn_servers.current_clients from the remaining active clients."""
    counts_result = await conn.execute(
        text(
            """
            SELECT server_id, COUNT(*) AS current_clients
            FROM vpn_clients
            WHERE is_active = TRUE
            GROUP BY server_id
            """
        )
    )
    server_counts = {int(row["server_id"]): int(row["current_clients"]) for row in counts_result.mappings()}

    await conn.execute(text("UPDATE vpn_servers SET current_clients = 0"))
    for server_id, current_clients in server_counts.items():
        await conn.execute(
            text(
                """
                UPDATE vpn_servers
                SET current_clients = :current_clients
                WHERE id = :server_id
                """
            ),
            {"server_id": server_id, "current_clients": current_clients},
        )


async def _ensure_unique_vpn_client_user_id(conn) -> None:
    """Create a unique index for vpn_clients.user_id on legacy databases."""
    has_unique_index = await conn.run_sync(_has_unique_vpn_client_user_id)
    if has_unique_index:
        return

    await conn.execute(
        text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ix_vpn_clients_user_id_unique
            ON vpn_clients (user_id)
            """
        )
    )
    logger.info("[DB] Ensured unique index for vpn_clients.user_id")


def _has_unique_vpn_client_user_id(sync_conn) -> bool:
    """Check whether vpn_clients.user_id is already uniquely constrained."""
    inspector = inspect(sync_conn)
    if "vpn_clients" not in inspector.get_table_names():
        return False

    for index in inspector.get_indexes("vpn_clients"):
        if index.get("unique") and index.get("column_names") == ["user_id"]:
            return True

    for constraint in inspector.get_unique_constraints("vpn_clients"):
        if constraint.get("column_names") == ["user_id"]:
            return True

    return False


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
