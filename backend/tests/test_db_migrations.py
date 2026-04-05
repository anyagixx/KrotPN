from app.core.migrations import _partition_vpn_client_rows


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
