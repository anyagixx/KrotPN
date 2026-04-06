# FILE: backend/app/core/migrations.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Database schema migration entry point and lightweight compatibility helpers
#   SCOPE: Column additions, index creation, uniqueness relaxation, table introspection
#   DEPENDS: M-001 (config, database), M-028 (migrations_legacy for data migration functions)
#   LINKS: M-028 (alembic-migrations), V-M-028
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   migrate_existing_schema - Main entry point: runs all schema compatibility migrations
#   _ensure_vpn_client_topology_columns - Add route/entry/exit columns to vpn_clients
#   _ensure_vpn_client_device_columns - Add device_id column to vpn_clients
#   _ensure_subscription_internal_access_columns - Add complimentary access columns
#   _ensure_plan_device_limit_column - Add device_limit to plans
#   _ensure_unique_vpn_client_device_id - Create unique index on device_id
#   _relax_vpn_client_user_uniqueness - Drop legacy user_id uniqueness constraint
#   _table_exists, _table_has_column - Schema introspection helpers
#   _has_unique_vpn_client_user_id, _has_unique_vpn_client_device_id - Index checks
#   _get_vpn_client_user_uniqueness_descriptors - Find unique constraints/indexes
#   _rebuild_vpn_clients_table_for_device_binding - SQLite table rebuild
#   _legacy_node_role, _country_code_for_location, _legacy_primary_device_key - String helpers
#   _record_device_security_event - Audit event writer
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Split from original migrations.py (1003 lines) into core + legacy per GRACE <1000 line rule
# END_CHANGE_SUMMARY
#
"""
Database migration helpers — schema compatibility layer.

Contains the main migration entry point and lightweight schema helpers.
Legacy data migration functions live in migrations_legacy.py.
"""

from loguru import logger
from sqlalchemy import bindparam, inspect, text
from sqlalchemy.engine import RowMapping

# Import legacy data migration functions
from app.core.migrations_legacy import (
    _migrate_legacy_vpn_servers_to_nodes,
    _migrate_legacy_vpn_clients_to_topology,
    _sync_vpn_topology_client_counts,
    _backfill_primary_user_devices,
)


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
    await _ensure_subscription_internal_access_columns(conn)
    await _ensure_plan_device_limit_column(conn)
    await _ensure_vpn_client_topology_columns(conn)
    await _ensure_vpn_client_device_columns(conn)
    await _migrate_legacy_vpn_servers_to_nodes(conn)
    await _migrate_legacy_vpn_clients_to_topology(conn)
    await _sync_vpn_topology_client_counts(conn)
    await _deduplicate_vpn_clients(conn)
    await _backfill_primary_user_devices(conn)
    await _relax_vpn_client_user_uniqueness(conn)
    await _ensure_unique_vpn_client_device_id(conn)


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
    server_counts = {
        int(row["server_id"]): int(row["current_clients"])
        for row in counts_result.mappings()
        if row["server_id"] is not None
    }

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


async def _relax_vpn_client_user_uniqueness(conn) -> None:
    """Remove legacy uniqueness on vpn_clients.user_id so one user can own multiple device-bound peers."""
    has_vpn_clients = await conn.run_sync(_table_exists, "vpn_clients")
    if not has_vpn_clients:
        return

    has_unique_index = await conn.run_sync(_has_unique_vpn_client_user_id)
    if not has_unique_index:
        return

    if conn.dialect.name == "sqlite":
        await _rebuild_vpn_clients_table_for_device_binding(conn)
        logger.info("[DB] Rebuilt vpn_clients for device-bound uniqueness on SQLite")
        return

    descriptors = await conn.run_sync(_get_vpn_client_user_uniqueness_descriptors)
    for index_name in descriptors["indexes"]:
        await conn.execute(text(f'DROP INDEX IF EXISTS "{index_name}"'))
    for constraint_name in descriptors["constraints"]:
        await conn.execute(
            text(f'ALTER TABLE vpn_clients DROP CONSTRAINT IF EXISTS "{constraint_name}"')
        )
    logger.info("[DB] Relaxed vpn_clients.user_id uniqueness for multi-device support")


async def _ensure_unique_vpn_client_device_id(conn) -> None:
    """Ensure vpn_clients.device_id is the stable uniqueness boundary."""
    has_vpn_clients = await conn.run_sync(_table_exists, "vpn_clients")
    if not has_vpn_clients:
        return

    has_unique_index = await conn.run_sync(_has_unique_vpn_client_device_id)
    if has_unique_index:
        return

    await conn.execute(
        text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ix_vpn_clients_device_id_unique
            ON vpn_clients (device_id)
            """
        )
    )
    logger.info("[DB] Ensured unique index for vpn_clients.device_id")


async def _ensure_vpn_client_topology_columns(conn) -> None:
    """Add nullable topology columns to vpn_clients on already deployed databases."""
    has_vpn_clients = await conn.run_sync(_table_exists, "vpn_clients")
    if not has_vpn_clients:
        return

    for column_name in ("route_id", "entry_node_id", "exit_node_id"):
        has_column = await conn.run_sync(_table_has_column, "vpn_clients", column_name)
        if has_column:
            continue

        await conn.execute(
            text(f"ALTER TABLE vpn_clients ADD COLUMN {column_name} INTEGER")
        )
        await conn.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS ix_vpn_clients_{column_name} "
                f"ON vpn_clients ({column_name})"
            )
        )
        logger.info(f"[DB] Added vpn_clients.{column_name} compatibility column")


async def _ensure_vpn_client_device_columns(conn) -> None:
    """Add nullable device linkage columns to vpn_clients on already deployed databases."""
    has_vpn_clients = await conn.run_sync(_table_exists, "vpn_clients")
    if not has_vpn_clients:
        return

    if not await conn.run_sync(_table_has_column, "vpn_clients", "device_id"):
        await conn.execute(text("ALTER TABLE vpn_clients ADD COLUMN device_id INTEGER"))
        logger.info("[DB] Added vpn_clients.device_id compatibility column")

    await conn.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_vpn_clients_device_id
            ON vpn_clients (device_id)
            """
        )
    )


async def _ensure_subscription_internal_access_columns(conn) -> None:
    """Add complimentary-access columns to subscriptions on already deployed databases."""
    has_subscriptions = await conn.run_sync(_table_exists, "subscriptions")
    if not has_subscriptions:
        return

    if not await conn.run_sync(_table_has_column, "subscriptions", "is_complimentary"):
        await conn.execute(
            text("ALTER TABLE subscriptions ADD COLUMN is_complimentary BOOLEAN DEFAULT FALSE")
        )
        logger.info("[DB] Added subscriptions.is_complimentary compatibility column")

    if not await conn.run_sync(_table_has_column, "subscriptions", "access_label"):
        await conn.execute(
            text("ALTER TABLE subscriptions ADD COLUMN access_label VARCHAR(100)")
        )
        logger.info("[DB] Added subscriptions.access_label compatibility column")


async def _ensure_plan_device_limit_column(conn) -> None:
    """Add device_limit to plans on already deployed databases."""
    has_plans = await conn.run_sync(_table_exists, "plans")
    if not has_plans:
        return

    if not await conn.run_sync(_table_has_column, "plans", "device_limit"):
        await conn.execute(
            text("ALTER TABLE plans ADD COLUMN device_limit INTEGER DEFAULT 1")
        )
        logger.info("[DB] Added plans.device_limit compatibility column")



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


def _has_unique_vpn_client_device_id(sync_conn) -> bool:
    """Check whether vpn_clients.device_id is already uniquely constrained."""
    inspector = inspect(sync_conn)
    if "vpn_clients" not in inspector.get_table_names():
        return False

    for index in inspector.get_indexes("vpn_clients"):
        if index.get("unique") and index.get("column_names") == ["device_id"]:
            return True

    for constraint in inspector.get_unique_constraints("vpn_clients"):
        if constraint.get("column_names") == ["device_id"]:
            return True

    return False


def _get_vpn_client_user_uniqueness_descriptors(sync_conn) -> dict[str, list[str]]:
    """Return unique indexes and constraints that enforce vpn_clients.user_id uniqueness."""
    inspector = inspect(sync_conn)
    indexes: list[str] = []
    constraints: list[str] = []
    if "vpn_clients" not in inspector.get_table_names():
        return {"indexes": indexes, "constraints": constraints}

    for index in inspector.get_indexes("vpn_clients"):
        if index.get("unique") and index.get("column_names") == ["user_id"]:
            name = index.get("name")
            if name:
                indexes.append(name)

    for constraint in inspector.get_unique_constraints("vpn_clients"):
        if constraint.get("column_names") == ["user_id"]:
            name = constraint.get("name")
            if name:
                constraints.append(name)

    return {"indexes": indexes, "constraints": constraints}


async def _rebuild_vpn_clients_table_for_device_binding(conn) -> None:
    """Rebuild vpn_clients on SQLite without user uniqueness and with device uniqueness."""
    await conn.execute(text("DROP TABLE IF EXISTS vpn_clients__new"))
    await conn.execute(
        text(
            """
            CREATE TABLE vpn_clients__new (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                device_id INTEGER,
                server_id INTEGER,
                route_id INTEGER,
                entry_node_id INTEGER,
                exit_node_id INTEGER,
                public_key VARCHAR(100) NOT NULL UNIQUE,
                private_key_enc VARCHAR(500) NOT NULL,
                address VARCHAR(20) NOT NULL UNIQUE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                total_upload_bytes INTEGER NOT NULL DEFAULT 0,
                total_download_bytes INTEGER NOT NULL DEFAULT 0,
                last_handshake_at DATETIME,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users (id),
                FOREIGN KEY(device_id) REFERENCES user_devices (id),
                FOREIGN KEY(server_id) REFERENCES vpn_servers (id),
                FOREIGN KEY(route_id) REFERENCES vpn_routes (id),
                FOREIGN KEY(entry_node_id) REFERENCES vpn_nodes (id),
                FOREIGN KEY(exit_node_id) REFERENCES vpn_nodes (id)
            )
            """
        )
    )
    await conn.execute(
        text(
            """
            INSERT INTO vpn_clients__new (
                id,
                user_id,
                device_id,
                server_id,
                route_id,
                entry_node_id,
                exit_node_id,
                public_key,
                private_key_enc,
                address,
                is_active,
                total_upload_bytes,
                total_download_bytes,
                last_handshake_at,
                created_at,
                updated_at
            )
            SELECT
                id,
                user_id,
                device_id,
                server_id,
                route_id,
                entry_node_id,
                exit_node_id,
                public_key,
                private_key_enc,
                address,
                is_active,
                total_upload_bytes,
                total_download_bytes,
                last_handshake_at,
                created_at,
                updated_at
            FROM vpn_clients
            """
        )
    )
    await conn.execute(text("DROP TABLE vpn_clients"))
    await conn.execute(text("ALTER TABLE vpn_clients__new RENAME TO vpn_clients"))
    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_vpn_clients_user_id ON vpn_clients (user_id)"))
    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_vpn_clients_device_id ON vpn_clients (device_id)"))
    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_vpn_clients_server_id ON vpn_clients (server_id)"))
    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_vpn_clients_route_id ON vpn_clients (route_id)"))
    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_vpn_clients_entry_node_id ON vpn_clients (entry_node_id)"))
    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_vpn_clients_exit_node_id ON vpn_clients (exit_node_id)"))
    await conn.execute(
        text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ix_vpn_clients_device_id_unique
            ON vpn_clients (device_id)
            """
        )
    )


def _table_exists(sync_conn, table_name: str) -> bool:
    """Check whether a table already exists."""
    inspector = inspect(sync_conn)
    return table_name in inspector.get_table_names()


def _table_has_column(sync_conn, table_name: str, column_name: str) -> bool:
    """Check whether a table contains the requested column."""
    inspector = inspect(sync_conn)
    if table_name not in inspector.get_table_names():
        return False

    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def _legacy_node_role(is_entry_node: bool, is_exit_node: bool) -> str:
    """Convert legacy booleans to the new stable node role string."""
    if is_entry_node and is_exit_node:
        return "combined"
    if is_exit_node:
        return "exit"
    return "entry"


def _country_code_for_location(location: str) -> str:
    """Best-effort country code inference for legacy location strings."""
    normalized = location.strip().lower()
    mapping = {
        "russia": "RU",
        "russian": "RU",
        "germany": "DE",
        "deutschland": "DE",
        "netherlands": "NL",
        "holland": "NL",
        "finland": "FI",
        "france": "FR",
        "poland": "PL",
    }
    for needle, country_code in mapping.items():
        if needle in normalized:
            return country_code
    return "ZZ"


def _legacy_primary_device_key(user_id: int) -> str:
    """Build a deterministic device key for migrated legacy users."""
    return f"legacy-user-{user_id}-primary"


async def _record_device_security_event(
    conn,
    *,
    user_id: int,
    device_id: int,
    event_type: str,
    severity: str,
    details_json: str,
) -> None:
    """Insert a durable device security event during compatibility migration."""
    await conn.execute(
        text(
            """
            INSERT INTO device_security_events (
                user_id,
                device_id,
                event_type,
                severity,
                details_json,
                created_at
            )
            VALUES (
                :user_id,
                :device_id,
                :event_type,
                :severity,
                :details_json,
                CURRENT_TIMESTAMP
            )
            """
        ),
        {
            "user_id": user_id,
            "device_id": device_id,
            "event_type": event_type,
            "severity": severity,
            "details_json": details_json,
        },
    )
