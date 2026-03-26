"""
MODULE_CONTRACT
- PURPOSE: Verify legacy vpn_clients rows are backfilled into deterministic primary devices with audit records.
- SCOPE: Compatibility migration helpers for device_id backfill and migrated primary-device events.
- DEPENDS: M-001 database compatibility migration helpers, M-002 users, M-003 vpn client rows, M-020 device-registry, M-025 device-audit-log.
- LINKS: V-M-020, V-M-025.

MODULE_MAP
- test_backfill_primary_user_devices_creates_deterministic_primary_device: Verifies one legacy vpn_client is linked to a migrated primary device and emits an audit event.

CHANGE_SUMMARY
- 2026-03-27: Added migration tests for deterministic primary-device bootstrap from legacy vpn_clients rows.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.core.database import _backfill_primary_user_devices, import_all_models


@pytest.mark.asyncio
async def test_backfill_primary_user_devices_creates_deterministic_primary_device():
    import_all_models()
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

        await conn.execute(
            text(
                """
                INSERT INTO users (email, email_verified, password_hash, language, role, is_active, created_at, updated_at)
                VALUES ('legacy@example.com', FALSE, 'hash', 'ru', 'user', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            )
        )
        user_row = await conn.execute(text("SELECT id FROM users WHERE email = 'legacy@example.com'"))
        user_id = int(user_row.scalar_one())

        await conn.execute(
            text(
                """
                INSERT INTO vpn_clients (
                    user_id,
                    device_id,
                    public_key,
                    private_key_enc,
                    address,
                    is_active,
                    created_at,
                    updated_at,
                    total_upload_bytes,
                    total_download_bytes,
                    last_handshake_at
                )
                VALUES (
                    :user_id,
                    NULL,
                    'pubkey-1',
                    'enc-1',
                    '10.10.0.2',
                    TRUE,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP,
                    0,
                    0,
                    CURRENT_TIMESTAMP
                )
                """
            ),
            {"user_id": user_id},
        )

        await _backfill_primary_user_devices(conn)

        device_row = await conn.execute(
            text(
                """
                SELECT id, user_id, device_key, name, platform, status
                FROM user_devices
                WHERE user_id = :user_id
                """
            ),
            {"user_id": user_id},
        )
        device = device_row.mappings().one()
        assert device["device_key"] == f"legacy-user-{user_id}-primary"
        assert device["name"] == "Primary device"
        assert device["platform"] == "legacy-migrated"
        assert device["status"] == "active"

        client_row = await conn.execute(
            text("SELECT device_id FROM vpn_clients WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        assert int(client_row.scalar_one()) == int(device["id"])

        event_row = await conn.execute(
            text(
                """
                SELECT event_type, severity
                FROM device_security_events
                WHERE user_id = :user_id AND device_id = :device_id
                """
            ),
            {"user_id": user_id, "device_id": int(device["id"])},
        )
        event = event_row.mappings().one()
        assert event["event_type"] == "migrated_primary_device"
        assert event["severity"] == "info"

    await engine.dispose()
