"""MTProto usage telemetry repository.

# FILE: backend/app/mtproto/usage_repository.py
# VERSION: 1.4.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Store and query metadata-only MTProto runtime telemetry idempotently
#   SCOPE: Telemetry normalization, SNI masking, IP hashing, trusted proxy-hop filtering, event/session/state writes, encrypted IP handoff, rollups, and retention
#   DEPENDS: M-001 (DB/session), M-042 (assignments), M-054 (usage models), M-061 (IP observability)
#   LINKS: M-054, M-061, V-M-054, V-M-061
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MTProtoTelemetryEvent - Normalized telemetry input contract
#   MTProtoTelemetryIngestResult - Batch ingestion counters
#   mask_sni - Helper: redact SNI labels for unknown/rejected telemetry
#   hash_client_ip - Helper: HMAC client address without raw IP persistence
#   is_trusted_proxy_hop - Helper: detect RU/DE router hop addresses that must not become user evidence
#   ingest_telemetry_batch - Idempotently persist runtime telemetry events
#   update_last_seen - Update per-assignment last successful handshake timestamp
#   rollup_usage - Rebuild aggregate usage windows from raw events
#   apply_retention - Delete old raw events while preserving rollups
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.4.0 - Filter trusted router-hop IPs before telemetry persistence and encrypted IP handoff.
#   LAST_CHANGE: v1.3.0 - Route IP_OBSERVATION runtime samples into encrypted IP state without inflating usage counters.
#   LAST_CHANGE: v1.2.0 - Added Phase-43 encrypted IP observation handoff and 30-day raw-event retention default.
#   LAST_CHANGE: v1.1.0 - Respect connection_count deltas on sampler close events.
#   LAST_CHANGE: v1.0.0 - Added Phase-42 MTProto telemetry ingestion repository
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import ipaddress
import json
import re
from typing import Iterable

from loguru import logger
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.mtproto.ip_observability import record_ip_observation
from app.mtproto.models import MTProtoAssignment
from app.mtproto.usage_models import (
    MTProtoUsageEvent,
    MTProtoUsageEventType,
    MTProtoUsageRollup,
    MTProtoUsageSession,
    MTProtoUsageState,
    MTProtoUsageWindow,
)


SAFE_CODE_RE = re.compile(r"^[a-z0-9_.:-]{1,80}$")
FORBIDDEN_EVENT_MARKERS = (
    "tg://proxy",
    "https://t.me/proxy",
    "secret=",
    "MTPROTO_BASE_SECRET_HEX",
    "MTPROTO_SECRET_SALT",
)


# START_BLOCK_REPOSITORY_TYPES
@dataclass(frozen=True)
class MTProtoTelemetryEvent:
    """Normalized metadata-only telemetry event received from the runtime."""

    runtime_event_id: str
    event_type: MTProtoUsageEventType | str
    observed_at: datetime | None = None
    assignment_id: int | None = None
    user_id: int | None = None
    sni: str | None = None
    client_ip: str | None = None
    ip_hash: str | None = None
    ip_prefix: str | None = None
    bytes_in: int = 0
    bytes_out: int = 0
    duration_ms: int = 0
    connection_count: int = 0
    error_code: str | None = None
    reason_code: str | None = None
    metadata: dict[str, object] | None = None


@dataclass(frozen=True)
class MTProtoTelemetryIngestResult:
    """Batch ingestion counters."""

    received_count: int
    written_count: int
    skipped_count: int
    degraded_count: int = 0
# END_BLOCK_REPOSITORY_TYPES


# START_BLOCK_SAFE_HELPERS
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_aware(value: datetime | None) -> datetime:
    if value is None:
        return _utcnow()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _non_negative(value: int | None) -> int:
    return max(int(value or 0), 0)


def _safe_code(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()[:80]
    if not normalized:
        return None
    if any(marker.lower() in normalized for marker in FORBIDDEN_EVENT_MARKERS):
        return "redacted"
    if SAFE_CODE_RE.fullmatch(normalized):
        return normalized
    return "invalid"


def _safe_metadata(metadata: dict[str, object] | None) -> str | None:
    if not metadata:
        return None
    safe: dict[str, object] = {}
    for key, value in metadata.items():
        safe_key = _safe_code(str(key)) or "field"
        if isinstance(value, (int, float, bool)) or value is None:
            safe[safe_key] = value
        else:
            safe_value = str(value)[:160]
            if any(marker.lower() in safe_value.lower() for marker in FORBIDDEN_EVENT_MARKERS):
                safe_value = "redacted"
            safe[safe_key] = safe_value
    return json.dumps(safe, sort_keys=True)


def mask_sni(sni: str | None) -> str | None:
    """Mask a domain-like SNI while preserving operator context."""
    if not sni:
        return None
    normalized = sni.strip().lower().rstrip(".")
    if any(marker.lower() in normalized for marker in FORBIDDEN_EVENT_MARKERS):
        return "redacted"
    labels = normalized.split(".")
    if len(labels) < 2:
        return "redacted"
    first = labels[0]
    if len(first) <= 4:
        masked_first = f"{first[:1]}..."
    else:
        masked_first = f"{first[:4]}..."
    return ".".join([masked_first, *labels[1:]])


def _normalize_client_ip(client_ip: str | None) -> str | None:
    if not client_ip:
        return None
    try:
        return str(ipaddress.ip_address(client_ip.strip()))
    except ValueError:
        return None


def is_trusted_proxy_hop(client_ip: str | None) -> bool:
    """Return whether a telemetry address is an infrastructure router hop."""
    normalized = _normalize_client_ip(client_ip)
    return normalized is not None and normalized in settings.mtproto_trusted_proxy_ip_set


def hash_client_ip(client_ip: str | None, *, secret: str | None = None) -> str | None:
    """Return stable HMAC for client IP without persisting the raw address."""
    normalized = _normalize_client_ip(client_ip)
    if not normalized:
        return None
    key = (secret or settings.secret_key).encode("utf-8")
    digest = hmac.new(key, normalized.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:40]


def coarse_ip_prefix(client_ip: str | None) -> str | None:
    """Return a coarse client prefix for aggregate distinct-network analytics."""
    normalized = _normalize_client_ip(client_ip)
    if not normalized:
        return None
    address = ipaddress.ip_address(normalized)
    if address.version == 4:
        return str(ipaddress.ip_network(f"{address}/24", strict=False))
    return str(ipaddress.ip_network(f"{address}/48", strict=False))
# END_BLOCK_SAFE_HELPERS


# START_BLOCK_ASSIGNMENT_LOOKUP
async def _resolve_assignment(
    session: AsyncSession,
    event: MTProtoTelemetryEvent,
) -> MTProtoAssignment | None:
    if event.assignment_id is not None:
        assignment = await session.get(MTProtoAssignment, int(event.assignment_id))
        if assignment is not None:
            return assignment
    if event.sni:
        result = await session.execute(
            select(MTProtoAssignment).where(MTProtoAssignment.sni == event.sni.strip().lower())
        )
        return result.scalar_one_or_none()
    return None
# END_BLOCK_ASSIGNMENT_LOOKUP


# START_BLOCK_STATE_SESSION_HELPERS
async def _get_or_create_state(
    session: AsyncSession,
    *,
    assignment_id: int,
    user_id: int,
) -> MTProtoUsageState:
    result = await session.execute(
        select(MTProtoUsageState).where(MTProtoUsageState.assignment_id == assignment_id)
    )
    state = result.scalar_one_or_none()
    if state is None:
        state = MTProtoUsageState(assignment_id=assignment_id, user_id=user_id)
        session.add(state)
        await session.flush()
    return state


async def _get_active_session(
    session: AsyncSession,
    *,
    assignment_id: int,
    ip_hash: str | None,
) -> MTProtoUsageSession | None:
    query = (
        select(MTProtoUsageSession)
        .where(
            MTProtoUsageSession.assignment_id == assignment_id,
            MTProtoUsageSession.active == True,
        )
        .order_by(MTProtoUsageSession.started_at.desc(), MTProtoUsageSession.id.desc())
    )
    if ip_hash:
        query = query.where(MTProtoUsageSession.client_ip_hash == ip_hash)
    result = await session.execute(query.limit(1))
    return result.scalar_one_or_none()


async def update_last_seen(
    session: AsyncSession,
    *,
    assignment_id: int,
    user_id: int,
    observed_at: datetime,
) -> MTProtoUsageState:
    """Update last successful handshake timestamp per assignment."""
    state = await _get_or_create_state(session, assignment_id=assignment_id, user_id=user_id)
    state.last_seen_at = observed_at
    state.updated_at = _utcnow()
    logger.info(
        "[M-054][update_last_seen][LAST_SEEN] "
        f"assignment_id={assignment_id} user_id={user_id}"
    )
    return state
# END_BLOCK_STATE_SESSION_HELPERS


# START_BLOCK_WRITE_EVENT_EFFECTS
async def _apply_known_event_effects(
    session: AsyncSession,
    *,
    event: MTProtoTelemetryEvent,
    event_type: MTProtoUsageEventType,
    assignment: MTProtoAssignment,
    observed_at: datetime,
    ip_hash: str | None,
) -> None:
    assignment_id = int(assignment.id)
    user_id = int(event.user_id or assignment.user_id)
    state = await _get_or_create_state(session, assignment_id=assignment_id, user_id=user_id)
    now = _utcnow()
    if event_type in {
        MTProtoUsageEventType.HANDSHAKE,
        MTProtoUsageEventType.ACTIVE_CONNECTION,
        MTProtoUsageEventType.CLOSE,
        MTProtoUsageEventType.IP_OBSERVATION,
    }:
        await record_ip_observation(
            session,
            assignment_id=assignment_id,
            user_id=user_id,
            client_ip=event.client_ip,
            observed_at=observed_at,
            event_type=event_type.value,
            connection_count=max(_non_negative(event.connection_count), 1 if event_type == MTProtoUsageEventType.HANDSHAKE else 0),
        )
        if event_type == MTProtoUsageEventType.IP_OBSERVATION:
            state.updated_at = now
            return

    if event_type == MTProtoUsageEventType.HANDSHAKE:
        await update_last_seen(
            session,
            assignment_id=assignment_id,
            user_id=user_id,
            observed_at=observed_at,
        )
        state.total_connections += max(_non_negative(event.connection_count), 1)
        state.active_connections = max(state.active_connections, 1)
        active_session = await _get_active_session(session, assignment_id=assignment_id, ip_hash=ip_hash)
        if active_session is None:
            active_session = MTProtoUsageSession(
                assignment_id=assignment_id,
                user_id=user_id,
                started_at=observed_at,
                client_ip_hash=ip_hash,
                connection_count=max(_non_negative(event.connection_count), 1),
            )
            session.add(active_session)
            await session.flush()
        else:
            active_session.connection_count += max(_non_negative(event.connection_count), 1)
            active_session.updated_at = now

    if event_type == MTProtoUsageEventType.REQ_PQ_PROOF:
        state.last_req_pq_at = observed_at

    if event_type == MTProtoUsageEventType.ACTIVE_CONNECTION:
        state.active_connections = _non_negative(event.connection_count)

    if event_type == MTProtoUsageEventType.BYTES:
        state.total_bytes_in += _non_negative(event.bytes_in)
        state.total_bytes_out += _non_negative(event.bytes_out)
        active_session = await _get_active_session(session, assignment_id=assignment_id, ip_hash=ip_hash)
        if active_session is not None:
            active_session.bytes_in += _non_negative(event.bytes_in)
            active_session.bytes_out += _non_negative(event.bytes_out)
            active_session.updated_at = now

    if event_type == MTProtoUsageEventType.ERROR:
        state.total_errors += 1
        active_session = await _get_active_session(session, assignment_id=assignment_id, ip_hash=ip_hash)
        if active_session is not None:
            active_session.error_count += 1
            active_session.updated_at = now

    if event_type == MTProtoUsageEventType.CLOSE:
        close_count = max(_non_negative(event.connection_count), 1)
        active_session = await _get_active_session(session, assignment_id=assignment_id, ip_hash=ip_hash)
        if active_session is not None:
            active_session.active = False
            active_session.ended_at = observed_at
            duration_ms = _non_negative(event.duration_ms)
            if duration_ms == 0 and active_session.started_at:
                started_at = _coerce_aware(active_session.started_at)
                duration_ms = max(int((observed_at - started_at).total_seconds() * 1000), 0)
            active_session.duration_ms = max(active_session.duration_ms, duration_ms)
            active_session.bytes_in += _non_negative(event.bytes_in)
            active_session.bytes_out += _non_negative(event.bytes_out)
            active_session.updated_at = now
        state.active_connections = max(state.active_connections - close_count, 0)

    state.updated_at = now
# END_BLOCK_WRITE_EVENT_EFFECTS


# START_CONTRACT: ingest_telemetry_batch
#   PURPOSE: Idempotently store metadata-only runtime telemetry and update usage state
#   INPUTS: session: AsyncSession; events: iterable MTProtoTelemetryEvent
#   OUTPUTS: MTProtoTelemetryIngestResult
#   SIDE_EFFECTS: Inserts usage rows, updates sessions/state, emits redacted log markers
#   LINKS: M-054, M-055, V-M-054, V-M-055
# END_CONTRACT: ingest_telemetry_batch
# START_BLOCK_INGEST_BATCH
async def ingest_telemetry_batch(
    session: AsyncSession,
    events: Iterable[MTProtoTelemetryEvent],
) -> MTProtoTelemetryIngestResult:
    """Store runtime telemetry idempotently by runtime_event_id."""
    event_list = list(events)
    written_count = 0
    skipped_count = 0
    seen_runtime_ids: set[str] = set()

    for event in event_list:
        runtime_event_id = event.runtime_event_id.strip()
        if not runtime_event_id or runtime_event_id in seen_runtime_ids:
            skipped_count += 1
            logger.info("[M-054][ingest_telemetry_batch][IDEMPOTENT_SKIP] duplicate=batch")
            continue
        seen_runtime_ids.add(runtime_event_id)

        existing = await session.execute(
            select(MTProtoUsageEvent.id).where(MTProtoUsageEvent.runtime_event_id == runtime_event_id)
        )
        if existing.scalar_one_or_none() is not None:
            skipped_count += 1
            logger.info("[M-054][ingest_telemetry_batch][IDEMPOTENT_SKIP] duplicate=db")
            continue

        try:
            event_type = MTProtoUsageEventType(event.event_type)
        except ValueError:
            event_type = MTProtoUsageEventType.ERROR

        observed_at = _coerce_aware(event.observed_at)
        if event_type == MTProtoUsageEventType.IP_OBSERVATION and is_trusted_proxy_hop(event.client_ip):
            skipped_count += 1
            logger.info("[M-054][ingest_telemetry_batch][TRUSTED_PROXY_HOP_SKIP] source=router")
            continue

        event_for_effects = event
        if is_trusted_proxy_hop(event.client_ip):
            event_for_effects = replace(event, client_ip=None, ip_hash=None, ip_prefix=None)

        assignment = await _resolve_assignment(session, event)
        assignment_id = int(assignment.id) if assignment and assignment.id is not None else None
        user_id = int(event.user_id or assignment.user_id) if assignment else event.user_id
        ip_hash = event_for_effects.ip_hash or hash_client_ip(event_for_effects.client_ip)
        ip_prefix = event_for_effects.ip_prefix or coarse_ip_prefix(event_for_effects.client_ip)

        row = MTProtoUsageEvent(
            runtime_event_id=runtime_event_id,
            assignment_id=assignment_id,
            user_id=user_id,
            event_type=event_type,
            observed_at=observed_at,
            sni_masked=mask_sni(event.sni or (assignment.sni if assignment else None)),
            ip_hash=ip_hash,
            ip_prefix=ip_prefix,
            bytes_in=_non_negative(event.bytes_in),
            bytes_out=_non_negative(event.bytes_out),
            duration_ms=_non_negative(event.duration_ms),
            connection_count=_non_negative(event.connection_count),
            error_code=_safe_code(event.error_code),
            reason_code=_safe_code(event.reason_code),
            metadata_json=_safe_metadata(event.metadata),
        )
        session.add(row)
        if assignment is not None:
            await _apply_known_event_effects(
                session,
                event=event_for_effects,
                event_type=event_type,
                assignment=assignment,
                observed_at=observed_at,
                ip_hash=ip_hash,
            )
        written_count += 1

    await session.flush()
    logger.info(
        "[M-054][ingest_telemetry_batch][WRITE_EVENTS] "
        f"received={len(event_list)} written={written_count} skipped={skipped_count}"
    )
    return MTProtoTelemetryIngestResult(
        received_count=len(event_list),
        written_count=written_count,
        skipped_count=skipped_count,
    )
# END_BLOCK_INGEST_BATCH


# START_BLOCK_ROLLUP_USAGE
def _window_start(value: datetime, window: MTProtoUsageWindow) -> datetime:
    value = _coerce_aware(value)
    if window == MTProtoUsageWindow.HOUR:
        return value.replace(minute=0, second=0, microsecond=0)
    if window == MTProtoUsageWindow.DAY:
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    if window == MTProtoUsageWindow.WEEK:
        day_start = value.replace(hour=0, minute=0, second=0, microsecond=0)
        return day_start - timedelta(days=day_start.weekday())
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def _upsert_rollup(
    session: AsyncSession,
    *,
    window_type: MTProtoUsageWindow,
    window_start: datetime,
    assignment_id: int | None,
    user_id: int | None,
    counters: dict[str, int],
) -> MTProtoUsageRollup:
    result = await session.execute(
        select(MTProtoUsageRollup).where(
            MTProtoUsageRollup.window_type == window_type,
            MTProtoUsageRollup.window_start == window_start,
            MTProtoUsageRollup.assignment_id == assignment_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = MTProtoUsageRollup(
            window_type=window_type,
            window_start=window_start,
            assignment_id=assignment_id,
            user_id=user_id,
        )
        session.add(row)
    row.user_id = user_id
    row.bytes_in = counters["bytes_in"]
    row.bytes_out = counters["bytes_out"]
    row.connection_count = counters["connection_count"]
    row.duration_ms = counters["duration_ms"]
    row.error_count = counters["error_count"]
    row.event_count = counters["event_count"]
    row.updated_at = _utcnow()
    return row


async def rollup_usage(
    session: AsyncSession,
    *,
    window_type: MTProtoUsageWindow = MTProtoUsageWindow.DAY,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> int:
    """Rebuild rollups for a bounded raw-event time window."""
    end = _coerce_aware(end_at)
    start = _coerce_aware(start_at) if start_at else end - timedelta(days=1)
    result = await session.execute(
        select(MTProtoUsageEvent).where(
            MTProtoUsageEvent.observed_at >= start,
            MTProtoUsageEvent.observed_at < end,
        )
    )
    events = list(result.scalars().all())
    aggregates: dict[tuple[datetime, int | None], dict[str, int | None]] = {}

    for event in events:
        key = (_window_start(event.observed_at, window_type), event.assignment_id)
        counters = aggregates.setdefault(
            key,
            {
                "user_id": event.user_id,
                "bytes_in": 0,
                "bytes_out": 0,
                "connection_count": 0,
                "duration_ms": 0,
                "error_count": 0,
                "event_count": 0,
            },
        )
        counters["bytes_in"] = int(counters["bytes_in"] or 0) + event.bytes_in
        counters["bytes_out"] = int(counters["bytes_out"] or 0) + event.bytes_out
        counters["connection_count"] = int(counters["connection_count"] or 0) + event.connection_count
        counters["duration_ms"] = int(counters["duration_ms"] or 0) + event.duration_ms
        counters["error_count"] = int(counters["error_count"] or 0) + (
            1 if event.event_type == MTProtoUsageEventType.ERROR else 0
        )
        counters["event_count"] = int(counters["event_count"] or 0) + 1

        global_key = (_window_start(event.observed_at, window_type), None)
        global_counters = aggregates.setdefault(
            global_key,
            {
                "user_id": None,
                "bytes_in": 0,
                "bytes_out": 0,
                "connection_count": 0,
                "duration_ms": 0,
                "error_count": 0,
                "event_count": 0,
            },
        )
        global_counters["bytes_in"] = int(global_counters["bytes_in"] or 0) + event.bytes_in
        global_counters["bytes_out"] = int(global_counters["bytes_out"] or 0) + event.bytes_out
        global_counters["connection_count"] = int(global_counters["connection_count"] or 0) + event.connection_count
        global_counters["duration_ms"] = int(global_counters["duration_ms"] or 0) + event.duration_ms
        global_counters["error_count"] = int(global_counters["error_count"] or 0) + (
            1 if event.event_type == MTProtoUsageEventType.ERROR else 0
        )
        global_counters["event_count"] = int(global_counters["event_count"] or 0) + 1

    for (rollup_start, assignment_id), counters in aggregates.items():
        await _upsert_rollup(
            session,
            window_type=window_type,
            window_start=rollup_start,
            assignment_id=assignment_id,
            user_id=int(counters["user_id"]) if counters["user_id"] is not None else None,
            counters={
                "bytes_in": int(counters["bytes_in"] or 0),
                "bytes_out": int(counters["bytes_out"] or 0),
                "connection_count": int(counters["connection_count"] or 0),
                "duration_ms": int(counters["duration_ms"] or 0),
                "error_count": int(counters["error_count"] or 0),
                "event_count": int(counters["event_count"] or 0),
            },
        )

    await session.flush()
    logger.info(
        "[M-054][rollup_usage][ROLLUP_WINDOW] "
        f"window={window_type.value} events={len(events)} rollups={len(aggregates)}"
    )
    return len(aggregates)
# END_BLOCK_ROLLUP_USAGE


# START_BLOCK_RETENTION
async def apply_retention(
    session: AsyncSession,
    *,
    raw_event_retention_days: int = 30,
    now: datetime | None = None,
) -> int:
    """Delete old raw events while preserving aggregate rollups."""
    cutoff = _coerce_aware(now) - timedelta(days=max(raw_event_retention_days, 1))
    result = await session.execute(
        delete(MTProtoUsageEvent)
        .where(MTProtoUsageEvent.observed_at < cutoff)
        .execution_options(synchronize_session=False)
    )
    deleted_count = int(result.rowcount or 0)
    logger.info(
        "[M-054][apply_retention][RETENTION_PRUNE] "
        f"deleted={deleted_count} retention_days={raw_event_retention_days}"
    )
    logger.info(
        "[M-054][apply_retention][PHASE43_STORAGE_BUDGET] "
        f"raw_event_retention_days={raw_event_retention_days} deleted={deleted_count}"
    )
    return deleted_count
# END_BLOCK_RETENTION


# START_BLOCK_QUERY_HELPERS
async def usage_state_for_assignment(
    session: AsyncSession,
    assignment_id: int,
) -> MTProtoUsageState | None:
    result = await session.execute(
        select(MTProtoUsageState).where(MTProtoUsageState.assignment_id == assignment_id)
    )
    return result.scalar_one_or_none()


async def usage_event_count(session: AsyncSession) -> int:
    return int((await session.execute(select(func.count(MTProtoUsageEvent.id)))).scalar() or 0)
# END_BLOCK_QUERY_HELPERS
