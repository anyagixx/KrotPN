# FILE: backend/app/core/migrations_legacy.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Legacy data migration functions — mirror old tables, deduplicate, backfill devices
#   SCOPE: vpn_servers→vpn_nodes mirror, vpn_clients dedup/topology backfill, device backfill, route sync
#   DEPENDS: M-001 (config), M-003 (vpn models/manager for peer removal)
#   LINKS: M-028 (alembic-migrations, via migrations.py), V-M-028
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   _migrate_legacy_vpn_servers_to_nodes - Mirror deprecated vpn_servers to vpn_nodes
#   _migrate_legacy_vpn_clients_to_topology - Backfill route/entry/exit columns from legacy records
#   _sync_vpn_topology_client_counts - Recalculate node and route client counters
#   _deduplicate_vpn_clients - Collapse duplicate vpn_clients rows to one per user
#   _backfill_primary_user_devices - Create user_devices records for legacy vpn_clients
#   _ensure_legacy_route - Create compatibility route for legacy single-hop servers
#   _partition_vpn_client_rows - Split vpn_clients into keepers vs duplicates
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Extracted from migrations.py per GRACE <1000 line rule; imported by migrations.py
# END_CHANGE_SUMMARY
#
"""
Legacy data migration functions.

These functions migrate data from deprecated table structures to the new topology.
Imported and called by migrations.py during startup.
"""

from loguru import logger
from sqlalchemy import bindparam, text
from sqlalchemy.engine import RowMapping
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


async def _migrate_legacy_vpn_servers_to_nodes(conn) -> None:
    """Mirror deprecated vpn_servers rows into vpn_nodes during the migration window."""
    has_vpn_servers = await conn.run_sync(_table_exists, "vpn_servers")
    has_vpn_nodes = await conn.run_sync(_table_exists, "vpn_nodes")
    if not has_vpn_servers or not has_vpn_nodes:
        return

    result = await conn.execute(
        text(
            """
            SELECT
                id,
                name,
                location,
                endpoint,
                port,
                public_key,
                private_key_enc,
                is_active,
                is_entry_node,
                is_exit_node,
                max_clients,
                current_clients,
                last_ping_at,
                is_online,
                created_at,
                updated_at
            FROM vpn_servers
            ORDER BY id ASC
            """
        )
    )
    rows = list(result.mappings())
    if not rows:
        return

    inserted = 0
    for row in rows:
        existing = await conn.execute(
            text("SELECT id FROM vpn_nodes WHERE public_key = :public_key"),
            {"public_key": row["public_key"]},
        )
        if existing.scalar_one_or_none() is not None:
            continue

        await conn.execute(
            text(
                """
                INSERT INTO vpn_nodes (
                    name,
                    role,
                    country_code,
                    location,
                    endpoint,
                    port,
                    public_key,
                    private_key_enc,
                    is_active,
                    is_online,
                    is_entry_node,
                    is_exit_node,
                    max_clients,
                    current_clients,
                    last_ping_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    :name,
                    :role,
                    :country_code,
                    :location,
                    :endpoint,
                    :port,
                    :public_key,
                    :private_key_enc,
                    :is_active,
                    :is_online,
                    :is_entry_node,
                    :is_exit_node,
                    :max_clients,
                    :current_clients,
                    :last_ping_at,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "name": row["name"],
                "role": _legacy_node_role(
                    bool(row["is_entry_node"]),
                    bool(row["is_exit_node"]),
                ),
                "country_code": _country_code_for_location(str(row["location"])),
                "location": row["location"],
                "endpoint": row["endpoint"],
                "port": row["port"],
                "public_key": row["public_key"],
                "private_key_enc": row["private_key_enc"],
                "is_active": row["is_active"],
                "is_online": row["is_online"],
                "is_entry_node": row["is_entry_node"],
                "is_exit_node": row["is_exit_node"],
                "max_clients": row["max_clients"],
                "current_clients": row["current_clients"],
                "last_ping_at": row["last_ping_at"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
        )
        inserted += 1

    if inserted:
        logger.info(f"[DB] Mirrored {inserted} legacy vpn_servers rows into vpn_nodes")


async def _migrate_legacy_vpn_clients_to_topology(conn) -> None:
    """Backfill vpn_clients route, entry, and exit columns from legacy server records."""
    has_vpn_clients = await conn.run_sync(_table_exists, "vpn_clients")
    has_vpn_routes = await conn.run_sync(_table_exists, "vpn_routes")
    if not has_vpn_clients or not has_vpn_routes:
        return

    server_map_result = await conn.execute(
        text(
            """
            SELECT vs.id AS server_id, vn.id AS node_id, vs.name AS server_name, vs.max_clients
            FROM vpn_servers vs
            JOIN vpn_nodes vn ON vn.public_key = vs.public_key
            """
        )
    )
    server_map = {
        int(row["server_id"]): {
            "node_id": int(row["node_id"]),
            "server_name": str(row["server_name"]),
            "max_clients": int(row["max_clients"]),
        }
        for row in server_map_result.mappings()
    }
    if not server_map:
        return

    legacy_route_ids: dict[int, int] = {}
    for server_id, server_data in server_map.items():
        route_id = await _ensure_legacy_route(
            conn,
            entry_node_id=server_data["node_id"],
            server_name=server_data["server_name"],
            max_clients=server_data["max_clients"],
        )
        legacy_route_ids[server_id] = route_id

    clients_result = await conn.execute(
        text(
            """
            SELECT id, server_id, route_id, entry_node_id, exit_node_id
            FROM vpn_clients
            ORDER BY id ASC
            """
        )
    )
    updated = 0
    for row in clients_result.mappings():
        if row["server_id"] is None:
            continue
        server_id = int(row["server_id"])
        server_data = server_map.get(server_id)
        if server_data is None:
            continue

        route_id = int(row["route_id"]) if row["route_id"] is not None else legacy_route_ids[server_id]
        entry_node_id = (
            int(row["entry_node_id"])
            if row["entry_node_id"] is not None
            else server_data["node_id"]
        )
        exit_node_id = int(row["exit_node_id"]) if row["exit_node_id"] is not None else None

        if (
            row["route_id"] == route_id
            and row["entry_node_id"] == entry_node_id
            and row["exit_node_id"] == exit_node_id
        ):
            continue

        await conn.execute(
            text(
                """
                UPDATE vpn_clients
                SET route_id = :route_id,
                    entry_node_id = :entry_node_id,
                    exit_node_id = :exit_node_id
                WHERE id = :client_id
                """
            ),
            {
                "client_id": int(row["id"]),
                "route_id": route_id,
                "entry_node_id": entry_node_id,
                "exit_node_id": exit_node_id,
            },
        )
        updated += 1

    if updated:
        logger.info(f"[DB] Backfilled topology fields for {updated} vpn_clients rows")


async def _sync_vpn_topology_client_counts(conn) -> None:
    """Recalculate vpn_nodes and vpn_routes client counters from vpn_clients."""
    has_vpn_clients = await conn.run_sync(_table_exists, "vpn_clients")
    has_vpn_nodes = await conn.run_sync(_table_exists, "vpn_nodes")
    has_vpn_routes = await conn.run_sync(_table_exists, "vpn_routes")
    if not has_vpn_clients:
        return

    if has_vpn_nodes:
        await conn.execute(text("UPDATE vpn_nodes SET current_clients = 0"))

        entry_counts_result = await conn.execute(
            text(
                """
                SELECT entry_node_id, COUNT(*) AS current_clients
                FROM vpn_clients
                WHERE is_active = TRUE AND entry_node_id IS NOT NULL
                GROUP BY entry_node_id
                """
            )
        )
        for row in entry_counts_result.mappings():
            await conn.execute(
                text(
                    """
                    UPDATE vpn_nodes
                    SET current_clients = current_clients + :current_clients
                    WHERE id = :node_id
                    """
                ),
                {
                    "node_id": int(row["entry_node_id"]),
                    "current_clients": int(row["current_clients"]),
                },
            )

        exit_counts_result = await conn.execute(
            text(
                """
                SELECT exit_node_id, COUNT(*) AS current_clients
                FROM vpn_clients
                WHERE is_active = TRUE AND exit_node_id IS NOT NULL
                GROUP BY exit_node_id
                """
            )
        )
        for row in exit_counts_result.mappings():
            await conn.execute(
                text(
                    """
                    UPDATE vpn_nodes
                    SET current_clients = current_clients + :current_clients
                    WHERE id = :node_id
                    """
                ),
                {
                    "node_id": int(row["exit_node_id"]),
                    "current_clients": int(row["current_clients"]),
                },
            )

    if has_vpn_routes:
        await conn.execute(text("UPDATE vpn_routes SET current_clients = 0"))
        route_counts_result = await conn.execute(
            text(
                """
                SELECT route_id, COUNT(*) AS current_clients
                FROM vpn_clients
                WHERE is_active = TRUE AND route_id IS NOT NULL
                GROUP BY route_id
                """
            )
        )
        for row in route_counts_result.mappings():
            await conn.execute(
                text(
                    """
                    UPDATE vpn_routes
                    SET current_clients = :current_clients
                    WHERE id = :route_id
                    """
                ),
                {
                    "route_id": int(row["route_id"]),
                    "current_clients": int(row["current_clients"]),
                },
            )


async def _backfill_primary_user_devices(conn) -> None:
    """Create deterministic primary devices for legacy vpn_clients rows."""
    has_vpn_clients = await conn.run_sync(_table_exists, "vpn_clients")
    has_user_devices = await conn.run_sync(_table_exists, "user_devices")
    has_device_events = await conn.run_sync(_table_exists, "device_security_events")
    if not has_vpn_clients or not has_user_devices:
        return

    result = await conn.execute(
        text(
            """
            SELECT id, user_id, device_id, is_active, created_at, updated_at, last_handshake_at
            FROM vpn_clients
            ORDER BY user_id ASC, id ASC
            """
        )
    )
    rows = list(result.mappings())
    if not rows:
        return

    created_devices = 0
    linked_clients = 0
    recorded_events = 0

    for row in rows:
        client_id = int(row["id"])
        user_id = int(row["user_id"])
        existing_device_id = row["device_id"]
        if existing_device_id is not None:
            device_exists = await conn.execute(
                text("SELECT id FROM user_devices WHERE id = :device_id"),
                {"device_id": int(existing_device_id)},
            )
            if device_exists.scalar_one_or_none() is not None:
                continue

        device_key = _legacy_primary_device_key(user_id)
        existing_device = await conn.execute(
            text(
                """
                SELECT id
                FROM user_devices
                WHERE device_key = :device_key
                """
            ),
            {"device_key": device_key},
        )
        device_id = existing_device.scalar_one_or_none()

        if device_id is None:
            await conn.execute(
                text(
                    """
                    INSERT INTO user_devices (
                        user_id,
                        device_key,
                        name,
                        platform,
                        status,
                        created_at,
                        updated_at,
                        last_seen_at,
                        last_handshake_at,
                        config_version
                    )
                    VALUES (
                        :user_id,
                        :device_key,
                        :name,
                        :platform,
                        :status,
                        :created_at,
                        :updated_at,
                        :last_seen_at,
                        :last_handshake_at,
                        1
                    )
                    """
                ),
                {
                    "user_id": user_id,
                    "device_key": device_key,
                    "name": "Primary device",
                    "platform": "legacy-migrated",
                    "status": "active" if bool(row["is_active"]) else "revoked",
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "last_seen_at": row["last_handshake_at"],
                    "last_handshake_at": row["last_handshake_at"],
                },
            )
            inserted_device = await conn.execute(
                text("SELECT id FROM user_devices WHERE device_key = :device_key"),
                {"device_key": device_key},
            )
            device_id = inserted_device.scalar_one()
            created_devices += 1
            logger.info(
                "[VPN][device][VPN_DEVICE_CREATED] "
                f"user_id={user_id} device_id={int(device_id)} device_key={device_key} source=legacy_migration"
            )

            if has_device_events:
                await _record_device_security_event(
                    conn,
                    user_id=user_id,
                    device_id=int(device_id),
                    event_type="migrated_primary_device",
                    severity="info",
                    details_json=f'{{"client_id": {client_id}, "source": "legacy_migration"}}',
                )
                recorded_events += 1

        await conn.execute(
            text(
                """
                UPDATE vpn_clients
                SET device_id = :device_id
                WHERE id = :client_id
                """
            ),
            {"client_id": client_id, "device_id": int(device_id)},
        )
        linked_clients += 1

    if created_devices:
        logger.info(
            "[VPN][device][VPN_DEVICE_AUDIT_RECORDED] "
            f"created_devices={created_devices} linked_clients={linked_clients} events={recorded_events} source=legacy_migration"
        )


async def _ensure_legacy_route(
    conn,
    *,
    entry_node_id: int,
    server_name: str,
    max_clients: int,
) -> int:
    """Create a compatibility route for legacy single-hop server records."""
    route_name = f"Legacy: {server_name}"
    existing = await conn.execute(
        text("SELECT id FROM vpn_routes WHERE name = :name"),
        {"name": route_name},
    )
    route_id = existing.scalar_one_or_none()
    if route_id is not None:
        return int(route_id)

    await conn.execute(
        text(
            """
            INSERT INTO vpn_routes (
                name,
                entry_node_id,
                exit_node_id,
                is_active,
                is_default,
                priority,
                max_clients,
                current_clients,
                created_at,
                updated_at
            )
            VALUES (
                :name,
                :entry_node_id,
                NULL,
                TRUE,
                FALSE,
                1000,
                :max_clients,
                0,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            """
        ),
        {
            "name": route_name,
            "entry_node_id": entry_node_id,
            "max_clients": max_clients,
        },
    )
    inserted = await conn.execute(
        text("SELECT id FROM vpn_routes WHERE name = :name"),
        {"name": route_name},
    )
    route_id = inserted.scalar_one()
    return int(route_id)


