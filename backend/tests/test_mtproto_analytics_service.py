"""MTProto analytics service tests.

# FILE: backend/tests/test_mtproto_analytics_service.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify MTProto analytics summaries, top users, per-proxy detail, timeseries, storage budget, and observe-first abuse signals
#   SCOPE: Usage fixtures, summary counters, ranking metrics, assignment drill-down, graph buckets, storage counters, and alert handoff
#   DEPENDS: M-056, M-054, M-060
#   LINKS: V-M-056, V-M-060
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   _create_assignment - Build one user and MTProto assignment
#   test_analytics_summary_usage_top_users_and_abuse_signals - Covers Phase-42 analytics service outputs
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.1.0 - Added Phase-43 timeseries, storage budget, and alert handoff checks
#   LAST_CHANGE: v1.0.0 - Added Phase-42 MTProto analytics service tests
# END_CHANGE_SUMMARY
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.mtproto.analytics_service import MTProtoAnalyticsService
from app.mtproto.admin_alerts import list_admin_alerts
from app.mtproto.models import MTProtoAssignment
from app.mtproto.usage_models import MTProtoUsageEventType
from app.mtproto.usage_repository import MTProtoTelemetryEvent, ingest_telemetry_batch
from app.users.models import User


# START_BLOCK_TEST_HELPERS
async def _create_assignment(
    session: AsyncSession,
    email: str,
    sni: str,
) -> tuple[User, MTProtoAssignment]:
    user = User(email=email, email_verified=True, is_active=True)
    session.add(user)
    await session.flush()
    assignment = MTProtoAssignment(user_id=int(user.id), sni=sni, rotation_marker="v1")
    session.add(assignment)
    await session.flush()
    await session.refresh(assignment)
    return user, assignment
# END_BLOCK_TEST_HELPERS


# START_BLOCK_ANALYTICS_SERVICE_TESTS
@pytest.mark.asyncio
async def test_analytics_summary_usage_top_users_and_abuse_signals(db_session: AsyncSession):
    user_one, assignment_one = await _create_assignment(
        db_session,
        "analytics-one@example.com",
        "u-analytics111.krotpn.xyz",
    )
    _user_two, assignment_two = await _create_assignment(
        db_session,
        "analytics-two@example.com",
        "u-analytics222.krotpn.xyz",
    )
    now = datetime.now(timezone.utc)
    await ingest_telemetry_batch(
        db_session,
        [
            MTProtoTelemetryEvent(
                runtime_event_id="a-1",
                event_type=MTProtoUsageEventType.HANDSHAKE,
                observed_at=now,
                assignment_id=int(assignment_one.id),
                client_ip="198.51.100.1",
                connection_count=3,
            ),
            MTProtoTelemetryEvent(
                runtime_event_id="a-2",
                event_type=MTProtoUsageEventType.BYTES,
                observed_at=now,
                assignment_id=int(assignment_one.id),
                bytes_in=4096,
                bytes_out=8192,
                duration_ms=10000,
            ),
            MTProtoTelemetryEvent(
                runtime_event_id="a-3",
                event_type=MTProtoUsageEventType.ERROR,
                observed_at=now,
                assignment_id=int(assignment_one.id),
                error_code="timeout",
            ),
            MTProtoTelemetryEvent(
                runtime_event_id="a-4",
                event_type=MTProtoUsageEventType.REQ_PQ_PROOF,
                observed_at=now,
                assignment_id=int(assignment_one.id),
            ),
            MTProtoTelemetryEvent(
                runtime_event_id="b-1",
                event_type=MTProtoUsageEventType.BYTES,
                observed_at=now,
                assignment_id=int(assignment_two.id),
                bytes_in=1024,
                bytes_out=1024,
                duration_ms=5000,
            ),
            MTProtoTelemetryEvent(
                runtime_event_id="u-1",
                event_type=MTProtoUsageEventType.UNKNOWN_SNI,
                observed_at=now,
                sni="unknown-analytics.krotpn.xyz",
                reason_code="not_issued",
            ),
        ],
    )

    service = MTProtoAnalyticsService(db_session)
    created_signals = await service.detect_abuse_signals(
        window_days=1,
        ip_threshold=0,
        concurrency_threshold=2,
        traffic_threshold_bytes=1,
        error_threshold=0,
    )
    summary = await service.build_global_summary(window_days=1, runtime_health={"status": "healthy"})
    usage = await service.build_assignment_usage(assignment_id=int(assignment_one.id), window_days=1)
    top_users = await service.build_top_users(metric="traffic", window_days=1, limit=5)
    events = await service.list_events(window_days=1, limit=10)
    timeseries = await service.build_timeseries(bucket="hour", window_days=1)
    search = await service.search_user_proxies(query="analytics-one", limit=10)
    storage_budget = await service.build_storage_budget()
    alerts = await list_admin_alerts(db_session)

    assert summary["issued_total"] == 2
    assert summary["status_counts"]["active"] == 2
    assert summary["unknown_sni_count"] == 1
    assert summary["availability_proof"]["status"] == "fresh"
    assert summary["runtime_health"]["status"] == "healthy"
    assert usage is not None
    assert usage["assignment"]["user_email"] == user_one.email
    assert usage["bytes_out"] >= 8192
    assert usage["error_count"] == 1
    assert top_users[0]["user_id"] == user_one.id
    assert len(created_signals) >= 1
    assert all(signal["observe_only"] is True for signal in created_signals)
    assert alerts["open_count"] >= 1
    assert events["total"] >= 6
    assert timeseries["items"]
    assert search["items"][0]["assignment_id"] == assignment_one.id
    assert storage_budget["retention"]["raw_events_days"] == 30
    assert storage_budget["counts"]["raw_events"] >= 6
    assert "unknown-analytics.krotpn.xyz" not in str(events)
# END_BLOCK_ANALYTICS_SERVICE_TESTS
