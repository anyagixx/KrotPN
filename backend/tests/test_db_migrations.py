"""Database migration helper tests.

# FILE: backend/tests/test_db_migrations.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify database migration helper behavior and migration metadata guardrails
#   SCOPE: VPN client compatibility helpers, Phase-29 MTProto migration evidence, Phase-42 telemetry migration evidence, and Phase-43 analytics migration evidence
#   DEPENDS: M-028, M-042, M-054, M-059, M-060, M-061
#   LINKS: V-M-028, V-M-042, V-M-054, V-M-059, V-M-060, V-M-061
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   test_partition_vpn_client_rows_keeps_active_latest_row_per_user - Covers partitioning
#   test_ensure_vpn_client_preshared_key_column_adds_nullable_column - Covers add path
#   test_ensure_vpn_client_preshared_key_column_is_idempotent - Covers no-op path
#   test_mtproto_assignment_migration_is_registered_after_baseline - Covers MTProto assignment metadata
#   test_mtproto_usage_telemetry_migration_is_registered_after_assignments - Covers Phase-42 analytics metadata
#   test_mtproto_phase43_migration_is_registered_after_usage_telemetry - Covers Phase-43 analytics metadata
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.3.0 - Added Phase-43 MTProto IP observability/admin alert migration metadata guard
#   LAST_CHANGE: v1.2.0 - Added Phase-42 MTProto usage telemetry migration metadata guard
#   LAST_CHANGE: v1.1.0 - Added MyGRACE contract and Phase-29 migration scope
# END_CHANGE_SUMMARY
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.migrations import (
    _ensure_vpn_client_preshared_key_column,
    _partition_vpn_client_rows,
)


def test_partition_vpn_client_rows_keeps_active_latest_row_per_user():
    rows = [
        {
            "id": 5,
            "user_id": 10,
            "server_id": 1,
            "public_key": "new-active",
            "is_active": True,
            "created_at": "2026-03-20T10:00:00",
            "updated_at": "2026-03-20T11:00:00",
        },
        {
            "id": 4,
            "user_id": 10,
            "server_id": 1,
            "public_key": "old-active",
            "is_active": True,
            "created_at": "2026-03-19T10:00:00",
            "updated_at": "2026-03-19T11:00:00",
        },
        {
            "id": 3,
            "user_id": 10,
            "server_id": 1,
            "public_key": "inactive",
            "is_active": False,
            "created_at": "2026-03-18T10:00:00",
            "updated_at": "2026-03-18T11:00:00",
        },
        {
            "id": 2,
            "user_id": 11,
            "server_id": 2,
            "public_key": "user11",
            "is_active": False,
            "created_at": "2026-03-20T08:00:00",
            "updated_at": "2026-03-20T09:00:00",
        },
    ]

    keepers, duplicates = _partition_vpn_client_rows(rows)

    assert [row["id"] for row in keepers] == [5, 2]
    assert [row["id"] for row in duplicates] == [4, 3]


class FakeConnection:
    def __init__(self, *, has_column: bool = False):
        self.dialect = SimpleNamespace(name="sqlite")
        self.has_column = has_column
        self.statements: list[str] = []

    async def run_sync(self, fn, *args):
        if fn.__name__ == "_table_exists":
            return True
        if fn.__name__ == "_table_has_column":
            return self.has_column
        raise AssertionError(f"unexpected run_sync function: {fn.__name__}")

    async def execute(self, statement, *args, **kwargs):
        self.statements.append(str(statement))


@pytest.mark.asyncio
async def test_ensure_vpn_client_preshared_key_column_adds_nullable_column():
    conn = FakeConnection(has_column=False)

    await _ensure_vpn_client_preshared_key_column(conn)

    assert conn.statements == [
        "ALTER TABLE vpn_clients ADD COLUMN preshared_key_enc VARCHAR(500)"
    ]


@pytest.mark.asyncio
async def test_ensure_vpn_client_preshared_key_column_is_idempotent():
    conn = FakeConnection(has_column=True)

    await _ensure_vpn_client_preshared_key_column(conn)

    assert conn.statements == []


def test_mtproto_assignment_migration_is_registered_after_baseline():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "b3f1e0d2c9a4_add_mtproto_assignments.py"
    )
    migration_text = migration_path.read_text(encoding="utf-8")

    assert 'revision: str = "b3f1e0d2c9a4"' in migration_text
    assert 'down_revision: Union[str, Sequence[str], None] = "2699e47c4e1b"' in migration_text
    assert "[M-042][migration][MTPROTO_ASSIGNMENT_SCHEMA]" in migration_text


def test_mtproto_usage_telemetry_migration_is_registered_after_assignments():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "phase42_add_mtproto_usage_telemetry.py"
    )
    migration_text = migration_path.read_text(encoding="utf-8")

    assert 'revision: str = "phase42_mtproto_usage"' in migration_text
    assert 'down_revision: Union[str, Sequence[str], None] = "b3f1e0d2c9a4"' in migration_text
    assert "[M-054][migration][MTPROTO_USAGE_SCHEMA]" in migration_text
    assert "mtproto_promotion_tag_state" in migration_text


def test_mtproto_phase43_migration_is_registered_after_usage_telemetry():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "phase43_add_mtproto_ip_observability.py"
    )
    migration_text = migration_path.read_text(encoding="utf-8")

    assert 'revision: str = "phase43_mtproto_admin_analytics"' in migration_text
    assert 'down_revision: Union[str, Sequence[str], None] = "phase42_mtproto_usage"' in migration_text
    assert "[M-061][migration][MTPROTO_IP_OBSERVABILITY_SCHEMA]" in migration_text
    assert "mtproto_admin_alerts" in migration_text
    assert "mtproto_ip_observations" in migration_text
