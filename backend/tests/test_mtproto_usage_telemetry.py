"""MTProto usage telemetry tests.

# FILE: backend/tests/test_mtproto_usage_telemetry.py
# VERSION: 1.1.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify metadata-only MTProto telemetry persistence, idempotency, rollups, and retention
#   SCOPE: Known assignment events, unknown SNI redaction, session state, last seen, rollup windows, and raw-event pruning
#   DEPENDS: M-054, M-042
#   LINKS: V-M-054
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   _create_assignment - Persist one verified user and MTProto assignment
#   test_ingest_known_assignment_events_updates_state_sessions_and_redacts_ip - Covers known event ingestion
#   test_unknown_sni_rollups_and_retention_are_safe - Covers unknown/rejected SNI, rollups, and retention
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.1.0 - Cover sampler active/close connection_count deltas.
#   LAST_CHANGE: v1.0.0 - Added Phase-42 usage telemetry tests
# END_CHANGE_SUMMARY
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mtproto.models import MTProtoAssignment
from app.mtproto.usage_models import (
    MTProtoUsageEvent,
    MTProtoUsageEventType,
    MTProtoUsageSession,
    MTProtoUsageWindow,
)
from app.mtproto.usage_repository import (
    MTProtoTelemetryEvent,
    apply_retention,
    ingest_telemetry_batch,
    rollup_usage,
    usage_event_count,
    usage_state_for_assignment,
)
from app.users.models import User


# START_BLOCK_TEST_HELPERS
async def _create_assignment(
    session: AsyncSession,
    *,
    email: str = "usage-owner@example.com",
    sni: str = "u-usage111111.krotpn.xyz",
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


# START_BLOCK_USAGE_TELEMETRY_TESTS
@pytest.mark.asyncio
async def test_ingest_known_assignment_events_updates_state_sessions_and_redacts_ip(
    db_session: AsyncSession,
):
    user, assignment = await _create_assignment(db_session)
    now = datetime.now(timezone.utc)

    result = await ingest_telemetry_batch(
        db_session,
        [
            MTProtoTelemetryEvent(
                runtime_event_id="evt-1",
                event_type=MTProtoUsageEventType.HANDSHAKE,
                observed_at=now,
                assignment_id=int(assignment.id),
                client_ip="203.0.113.77",
                connection_count=3,
            ),
            MTProtoTelemetryEvent(
                runtime_event_id="evt-2",
                event_type=MTProtoUsageEventType.ACTIVE_CONNECTION,
                observed_at=now + timedelta(milliseconds=500),
                assignment_id=int(assignment.id),
                connection_count=3,
            ),
            MTProtoTelemetryEvent(
                runtime_event_id="evt-3",
                event_type=MTProtoUsageEventType.REQ_PQ_PROOF,
                observed_at=now + timedelta(seconds=1),
                assignment_id=int(assignment.id),
            ),
            MTProtoTelemetryEvent(
                runtime_event_id="evt-4",
                event_type=MTProtoUsageEventType.BYTES,
                observed_at=now + timedelta(seconds=2),
                assignment_id=int(assignment.id),
                bytes_in=1200,
                bytes_out=2400,
            ),
            MTProtoTelemetryEvent(
                runtime_event_id="evt-5",
                event_type=MTProtoUsageEventType.ERROR,
                observed_at=now + timedelta(seconds=3),
                assignment_id=int(assignment.id),
                error_code="telegram_timeout",
            ),
            MTProtoTelemetryEvent(
                runtime_event_id="evt-6",
                event_type=MTProtoUsageEventType.CLOSE,
                observed_at=now + timedelta(seconds=4),
                assignment_id=int(assignment.id),
                duration_ms=4000,
                connection_count=3,
            ),
            MTProtoTelemetryEvent(
                runtime_event_id="evt-1",
                event_type=MTProtoUsageEventType.HANDSHAKE,
                observed_at=now,
                assignment_id=int(assignment.id),
            ),
        ],
    )

    assert result.received_count == 7
    assert result.written_count == 6
    assert result.skipped_count == 1
    assert await usage_event_count(db_session) == 6

    state = await usage_state_for_assignment(db_session, int(assignment.id))
    assert state is not None
    assert state.user_id == user.id
    assert state.last_seen_at is not None
    assert state.last_req_pq_at is not None
    assert state.total_connections == 3
    assert state.total_bytes_in == 1200
    assert state.total_bytes_out == 2400
    assert state.total_errors == 1
    assert state.active_connections == 0

    session_result = await db_session.execute(select(MTProtoUsageSession))
    usage_session = session_result.scalar_one()
    assert usage_session.active is False
    assert usage_session.duration_ms == 4000

    events_result = await db_session.execute(select(MTProtoUsageEvent).order_by(MTProtoUsageEvent.id))
    events = list(events_result.scalars().all())
    assert events[0].ip_hash
    assert events[0].ip_hash != "203.0.113.77"
    assert all("secret=" not in str(event) for event in events)


@pytest.mark.asyncio
async def test_unknown_sni_rollups_and_retention_are_safe(db_session: AsyncSession):
    now = datetime.now(timezone.utc)
    await ingest_telemetry_batch(
        db_session,
        [
            MTProtoTelemetryEvent(
                runtime_event_id="unknown-1",
                event_type=MTProtoUsageEventType.UNKNOWN_SNI,
                observed_at=now,
                sni="unknown-long-label.krotpn.xyz",
                reason_code="not_issued",
            ),
            MTProtoTelemetryEvent(
                runtime_event_id="old-1",
                event_type=MTProtoUsageEventType.REJECTED_SNI,
                observed_at=now - timedelta(days=120),
                sni="rejected-long-label.krotpn.xyz",
                reason_code="invalid_sni",
            ),
        ],
    )

    event_result = await db_session.execute(
        select(MTProtoUsageEvent).where(MTProtoUsageEvent.runtime_event_id == "unknown-1")
    )
    event = event_result.scalar_one()
    assert event.assignment_id is None
    assert event.sni_masked != "unknown-long-label.krotpn.xyz"
    assert event.reason_code == "not_issued"

    assert await rollup_usage(db_session, window_type=MTProtoUsageWindow.DAY, start_at=now - timedelta(days=1), end_at=now + timedelta(days=1)) >= 1
    assert await rollup_usage(db_session, window_type=MTProtoUsageWindow.WEEK, start_at=now - timedelta(days=1), end_at=now + timedelta(days=1)) >= 1
    assert await rollup_usage(db_session, window_type=MTProtoUsageWindow.MONTH, start_at=now - timedelta(days=1), end_at=now + timedelta(days=1)) >= 1

    deleted = await apply_retention(db_session, raw_event_retention_days=90, now=now)
    assert deleted == 1
    assert await usage_event_count(db_session) == 1
# END_BLOCK_USAGE_TELEMETRY_TESTS
