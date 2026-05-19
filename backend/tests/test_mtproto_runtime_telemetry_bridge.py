"""MTProto runtime telemetry bridge tests.

# FILE: backend/tests/test_mtproto_runtime_telemetry_bridge.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify private MTProto runtime telemetry snapshot/drain adapter behavior
#   SCOPE: In-memory telemetry buffer, cursor drain, overflow, HTTP token request shape, and degraded ingestion
#   DEPENDS: M-055, M-054
#   LINKS: V-M-055
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   test_in_memory_runtime_telemetry_snapshot_and_drain_are_cursor_safe - Covers local adapter telemetry
#   test_http_runtime_telemetry_adapter_uses_private_token_and_paths - Covers live adapter request shape
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-42 runtime telemetry bridge tests
# END_CHANGE_SUMMARY
"""

from datetime import datetime, timezone
import json

import httpx
import pytest

from app.mtproto.runtime_bridge import (
    HTTPMTProtoPolicyAdapter,
    InMemoryMTProtoPolicyAdapter,
    MTProtoRuntimeTelemetryEvent,
)


# START_BLOCK_RUNTIME_TELEMETRY_TESTS
@pytest.mark.asyncio
async def test_in_memory_runtime_telemetry_snapshot_and_drain_are_cursor_safe():
    adapter = InMemoryMTProtoPolicyAdapter()
    adapter.emit_telemetry_event(
        MTProtoRuntimeTelemetryEvent(
            runtime_event_id="rt-1",
            event_type="handshake",
            observed_at=datetime.now(timezone.utc),
            assignment_id=10,
            user_id=20,
            connection_count=1,
        )
    )
    adapter.emit_telemetry_event(
        MTProtoRuntimeTelemetryEvent(
            runtime_event_id="rt-2",
            event_type="bytes",
            assignment_id=10,
            user_id=20,
            bytes_in=100,
            bytes_out=200,
        )
    )

    snapshot = await adapter.telemetry_snapshot()
    first = await adapter.telemetry_drain(cursor=0, limit=1)
    second = await adapter.telemetry_drain(cursor=first.next_cursor, limit=10)

    assert snapshot.status.value == "healthy"
    assert snapshot.buffered_events == 2
    assert first.next_cursor == 1
    assert [event.runtime_event_id for event in first.events] == ["rt-1"]
    assert [event.runtime_event_id for event in second.events] == ["rt-2"]
    assert "secret=" not in str(first.to_safe_dict())


@pytest.mark.asyncio
async def test_http_runtime_telemetry_adapter_uses_private_token_and_paths():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["x-krotpn-mtproto-token"] == "runtime-token-with-enough-length"
        if request.url.path.endswith("/telemetry/snapshot"):
            return httpx.Response(200, json={"status": "healthy", "buffered_events": 1, "dropped_events": 0})
        if request.url.path.endswith("/telemetry/drain"):
            return httpx.Response(
                200,
                json={
                    "events": [
                        {
                            "runtime_event_id": "http-1",
                            "event_type": "req_pq_proof",
                            "observed_at": "2026-05-19T20:00:00+00:00",
                            "assignment_id": 7,
                            "user_id": 9,
                        }
                    ],
                    "next_cursor": 6,
                    "dropped_events": 0,
                },
            )
        return httpx.Response(404, json={"status": "not_found"})

    adapter = HTTPMTProtoPolicyAdapter(
        base_url="http://127.0.0.1:18080/krotpn/mtproto/policy",
        token="runtime-token-with-enough-length",
        transport=httpx.MockTransport(handler),
    )

    snapshot = await adapter.telemetry_snapshot()
    batch = await adapter.telemetry_drain(cursor=5, limit=10)

    assert snapshot.buffered_events == 1
    assert batch.next_cursor == 6
    assert batch.events[0].event_type == "req_pq_proof"
    assert [request.url.path for request in requests] == [
        "/krotpn/mtproto/policy/telemetry/snapshot",
        "/krotpn/mtproto/policy/telemetry/drain",
    ]
    assert "runtime-token-with-enough-length" not in json.dumps(batch.to_safe_dict())
# END_BLOCK_RUNTIME_TELEMETRY_TESTS
