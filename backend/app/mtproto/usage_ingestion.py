"""MTProto runtime telemetry ingestion.

# FILE: backend/app/mtproto/usage_ingestion.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Poll the private MTProto runtime telemetry bridge and persist events into usage analytics storage
#   SCOPE: Cursor tracking, degraded-safe runtime drain, event conversion, repository ingestion, and scheduler entry point
#   DEPENDS: M-001 (DB/session), M-054 (usage repository), M-055 (runtime telemetry bridge)
#   LINKS: M-055, M-054, V-M-055, V-M-054
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MTProtoTelemetryIngestionResult - Scheduler-safe ingestion counters
#   ingest_mtproto_runtime_telemetry - Drain runtime telemetry and persist metadata-only rows
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-42 runtime telemetry ingestion job
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from app.core.database import async_session_maker
from app.mtproto.runtime_bridge import (
    MTProtoBridgeUnavailable,
    MTProtoPolicyAdapter,
    MTProtoRuntimeTelemetryEvent,
    build_default_policy_adapter,
)
from app.mtproto.usage_repository import (
    MTProtoTelemetryEvent,
    ingest_telemetry_batch,
    rollup_usage,
)
from app.mtproto.usage_models import MTProtoUsageWindow


_telemetry_cursor = 0


# START_BLOCK_INGESTION_TYPES
@dataclass(frozen=True)
class MTProtoTelemetryIngestionResult:
    """Scheduler-safe runtime telemetry ingestion result."""

    status: str
    received_count: int = 0
    written_count: int = 0
    skipped_count: int = 0
    next_cursor: int = 0
    dropped_events: int = 0
    safe_message: str = ""
# END_BLOCK_INGESTION_TYPES


# START_BLOCK_CONVERSION
def _to_repository_event(event: MTProtoRuntimeTelemetryEvent) -> MTProtoTelemetryEvent:
    return MTProtoTelemetryEvent(
        runtime_event_id=event.runtime_event_id,
        event_type=event.event_type,
        observed_at=event.observed_at,
        assignment_id=event.assignment_id,
        user_id=event.user_id,
        sni=event.sni,
        client_ip=event.client_ip,
        ip_hash=event.ip_hash,
        ip_prefix=event.ip_prefix,
        bytes_in=event.bytes_in,
        bytes_out=event.bytes_out,
        duration_ms=event.duration_ms,
        connection_count=event.connection_count,
        error_code=event.error_code,
        reason_code=event.reason_code,
        metadata=event.metadata,
    )
# END_BLOCK_CONVERSION


# START_CONTRACT: ingest_mtproto_runtime_telemetry
#   PURPOSE: Drain runtime telemetry through the adapter and persist it without impacting MTProto availability
#   INPUTS: adapter: MTProtoPolicyAdapter | None; limit: int
#   OUTPUTS: MTProtoTelemetryIngestionResult
#   SIDE_EFFECTS: DB writes, cursor update, redacted log marker
#   LINKS: M-055, M-054, V-M-055
# END_CONTRACT: ingest_mtproto_runtime_telemetry
# START_BLOCK_TELEMETRY_INGEST
async def ingest_mtproto_runtime_telemetry(
    *,
    adapter: MTProtoPolicyAdapter | None = None,
    limit: int = 500,
) -> MTProtoTelemetryIngestionResult:
    """Drain runtime telemetry and write usage rows; failures degrade analytics only."""
    global _telemetry_cursor
    runtime_adapter = adapter or build_default_policy_adapter()
    safe_limit = min(max(limit, 1), 1000)
    try:
        batch = await runtime_adapter.telemetry_drain(cursor=_telemetry_cursor, limit=safe_limit)
    except (MTProtoBridgeUnavailable, ValueError, TypeError) as exc:
        logger.warning(
            "[M-055][telemetry_ingest][INGEST_SUMMARY] "
            f"status=degraded cursor={_telemetry_cursor}"
        )
        return MTProtoTelemetryIngestionResult(
            status="degraded",
            next_cursor=_telemetry_cursor,
            safe_message="MTProto runtime telemetry is unavailable",
        )

    async with async_session_maker() as session:
        ingest_result = await ingest_telemetry_batch(
            session,
            [_to_repository_event(event) for event in batch.events],
        )
        await rollup_usage(session, window_type=MTProtoUsageWindow.DAY)
        await session.commit()

    _telemetry_cursor = batch.next_cursor
    logger.info(
        "[M-055][telemetry_ingest][INGEST_SUMMARY] "
        f"status=ok received={ingest_result.received_count} written={ingest_result.written_count} "
        f"skipped={ingest_result.skipped_count} next_cursor={_telemetry_cursor} dropped={batch.dropped_events}"
    )
    return MTProtoTelemetryIngestionResult(
        status="ok",
        received_count=ingest_result.received_count,
        written_count=ingest_result.written_count,
        skipped_count=ingest_result.skipped_count,
        next_cursor=_telemetry_cursor,
        dropped_events=batch.dropped_events,
    )
# END_BLOCK_TELEMETRY_INGEST
