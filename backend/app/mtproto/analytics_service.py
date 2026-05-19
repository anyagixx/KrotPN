"""MTProto admin analytics service.

# FILE: backend/app/mtproto/analytics_service.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Build operator-safe MTProto usage analytics from metadata-only telemetry
#   SCOPE: Global summaries, per-assignment usage, top users, event listings, and observe-only abuse signals
#   DEPENDS: M-001 (DB), M-042 (assignments), M-054 (usage telemetry), M-055 (runtime telemetry)
#   LINKS: M-056, V-M-056
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MTProtoAnalyticsService - Query and aggregate MTProto usage telemetry for admin APIs
#   build_global_summary - Return issued totals, status counts, runtime proof, traffic windows, and abuse counts
#   build_assignment_usage - Return one assignment's usage, sessions, errors, last seen, and abuse signals
#   build_top_users - Rank users by traffic, duration, connection count, or error count
#   detect_abuse_signals - Write observe-only abuse signals from usage windows
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-42 MTProto analytics service
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Literal

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mtproto.models import MTProtoAssignment, MTProtoAssignmentStatus
from app.mtproto.usage_models import (
    MTProtoAbuseSignal,
    MTProtoAbuseSignalType,
    MTProtoUsageEvent,
    MTProtoUsageEventType,
    MTProtoUsageSession,
    MTProtoUsageState,
)
from app.mtproto.usage_repository import mask_sni
from app.users.models import User


TopUserMetric = Literal["traffic", "duration", "connections", "errors"]


# START_BLOCK_ANALYTICS_HELPERS
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _window_start(days: int) -> datetime:
    return _utcnow() - timedelta(days=max(days, 1))


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _traffic_total(event: MTProtoUsageEvent) -> int:
    return int(event.bytes_in or 0) + int(event.bytes_out or 0)


def _event_type_value(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)
# END_BLOCK_ANALYTICS_HELPERS


# START_BLOCK_ANALYTICS_SERVICE
class MTProtoAnalyticsService:
    """Build secret-free MTProto usage analytics."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # START_CONTRACT: build_global_summary
    #   PURPOSE: Return issued totals, status counts, active connections, runtime health, traffic windows, and req_pq proof
    #   INPUTS: window_days: int; runtime_health: dict | None
    #   OUTPUTS: dict
    #   SIDE_EFFECTS: database reads and redacted log marker
    #   LINKS: M-056, M-057, V-M-056
    # END_CONTRACT: build_global_summary
    # START_BLOCK_GLOBAL_SUMMARY
    async def build_global_summary(
        self,
        *,
        window_days: int = 30,
        runtime_health: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Return aggregate MTProto analytics for admin dashboard."""
        total_issued = int((await self.session.execute(select(func.count(MTProtoAssignment.id)))).scalar() or 0)
        status_counts = {
            status.value: int(
                (
                    await self.session.execute(
                        select(func.count(MTProtoAssignment.id)).where(MTProtoAssignment.status == status)
                    )
                ).scalar()
                or 0
            )
            for status in MTProtoAssignmentStatus
        }
        active_connections = int(
            (
                await self.session.execute(select(func.coalesce(func.sum(MTProtoUsageState.active_connections), 0)))
            ).scalar()
            or 0
        )
        latest_seen = (
            await self.session.execute(select(func.max(MTProtoUsageState.last_seen_at)))
        ).scalar()
        latest_req_pq = (
            await self.session.execute(select(func.max(MTProtoUsageState.last_req_pq_at)))
        ).scalar()
        latest_event = (
            await self.session.execute(select(func.max(MTProtoUsageEvent.observed_at)))
        ).scalar()

        start = _window_start(window_days)
        traffic_windows = {
            "day": await self._traffic_window(days=1),
            "week": await self._traffic_window(days=7),
            "month": await self._traffic_window(days=30),
            "selected": await self._traffic_window(days=window_days),
        }
        unknown_sni_count = await self._event_count(MTProtoUsageEventType.UNKNOWN_SNI, start=start)
        rejected_sni_count = await self._event_count(MTProtoUsageEventType.REJECTED_SNI, start=start)
        error_count = await self._event_count(MTProtoUsageEventType.ERROR, start=start)
        abuse_count = int(
            (
                await self.session.execute(
                    select(func.count(MTProtoAbuseSignal.id)).where(MTProtoAbuseSignal.window_start >= start)
                )
            ).scalar()
            or 0
        )
        telemetry_status = self._telemetry_status(latest_event)
        if telemetry_status == "stale":
            logger.warning("[M-056][build_global_summary][STALE_TELEMETRY] status=stale")

        payload = {
            "issued_total": total_issued,
            "status_counts": status_counts,
            "active_connections": active_connections,
            "last_seen_at": _iso(_coerce_aware(latest_seen)),
            "traffic_windows": traffic_windows,
            "error_count": error_count,
            "unknown_sni_count": unknown_sni_count,
            "rejected_sni_count": rejected_sni_count,
            "abuse_signal_count": abuse_count,
            "telemetry_status": telemetry_status,
            "availability_proof": {
                "req_pq_last_at": _iso(_coerce_aware(latest_req_pq)),
                "status": self._proof_status(_coerce_aware(latest_req_pq)),
            },
            "runtime_health": runtime_health or {"status": "unknown"},
        }
        logger.info(
            "[M-056][build_global_summary][SUMMARY] "
            f"issued={total_issued} active_connections={active_connections}"
        )
        return payload
    # END_BLOCK_GLOBAL_SUMMARY

    # START_CONTRACT: build_assignment_usage
    #   PURPOSE: Return usage details for one MTProto assignment
    #   INPUTS: assignment_id: int; window_days: int
    #   OUTPUTS: dict
    #   SIDE_EFFECTS: database reads and redacted log marker
    #   LINKS: M-056, M-057, V-M-056
    # END_CONTRACT: build_assignment_usage
    # START_BLOCK_ASSIGNMENT_USAGE
    async def build_assignment_usage(
        self,
        *,
        assignment_id: int,
        window_days: int = 30,
    ) -> dict[str, object] | None:
        """Return one assignment's usage detail."""
        result = await self.session.execute(
            select(MTProtoAssignment, User)
            .join(User, User.id == MTProtoAssignment.user_id)
            .where(MTProtoAssignment.id == assignment_id)
        )
        row = result.first()
        if row is None:
            return None
        assignment, user = row
        state = (
            await self.session.execute(
                select(MTProtoUsageState).where(MTProtoUsageState.assignment_id == assignment_id)
            )
        ).scalar_one_or_none()
        start = _window_start(window_days)
        events = await self._events_for_assignment(assignment_id=assignment_id, start=start)
        sessions = await self._sessions_for_assignment(assignment_id=assignment_id, start=start)
        abuse_signals = await self.list_abuse_signals(assignment_id=assignment_id, limit=20)
        payload = {
            "assignment": {
                "id": assignment.id,
                "user_id": assignment.user_id,
                "user_email": user.email,
                "user_display_name": user.display_name,
                "sni_masked": mask_sni(assignment.sni),
                "status": assignment.status.value,
                "rotation_marker": assignment.rotation_marker,
            },
            "window_days": window_days,
            "last_seen_at": _iso(state.last_seen_at if state else None),
            "last_req_pq_at": _iso(state.last_req_pq_at if state else None),
            "active_connections": int(state.active_connections if state else 0),
            "connection_count": int(sum(max(event.connection_count, 0) for event in events)),
            "session_count": len(sessions),
            "active_session_count": len([session for session in sessions if session.active]),
            "duration_ms": int(sum(session.duration_ms for session in sessions)),
            "bytes_in": int(sum(event.bytes_in for event in events)),
            "bytes_out": int(sum(event.bytes_out for event in events)),
            "error_count": len([event for event in events if _event_type_value(event.event_type) == MTProtoUsageEventType.ERROR.value]),
            "recent_events": [self._serialize_event(event) for event in events[:50]],
            "abuse_signals": abuse_signals["items"],
        }
        logger.info(
            "[M-056][build_assignment_usage][USAGE_DETAIL] "
            f"assignment_id={assignment_id} events={len(events)}"
        )
        return payload
    # END_BLOCK_ASSIGNMENT_USAGE

    # START_CONTRACT: build_top_users
    #   PURPOSE: Rank users by traffic, duration, connection count, or error count
    #   INPUTS: metric: TopUserMetric; window_days: int; limit: int
    #   OUTPUTS: list[dict]
    #   SIDE_EFFECTS: database reads and redacted log marker
    #   LINKS: M-056, V-M-056
    # END_CONTRACT: build_top_users
    # START_BLOCK_TOP_USERS
    async def build_top_users(
        self,
        *,
        metric: TopUserMetric = "traffic",
        window_days: int = 30,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        """Return stable top users for the selected metric."""
        start = _window_start(window_days)
        result = await self.session.execute(
            select(MTProtoUsageEvent).where(
                MTProtoUsageEvent.user_id.is_not(None),
                MTProtoUsageEvent.observed_at >= start,
            )
        )
        events = list(result.scalars().all())
        aggregates: dict[int, dict[str, int]] = defaultdict(
            lambda: {"traffic": 0, "duration": 0, "connections": 0, "errors": 0}
        )
        for event in events:
            if event.user_id is None:
                continue
            user_id = int(event.user_id)
            aggregates[user_id]["traffic"] += _traffic_total(event)
            aggregates[user_id]["duration"] += int(event.duration_ms or 0)
            aggregates[user_id]["connections"] += int(event.connection_count or 0)
            aggregates[user_id]["errors"] += 1 if _event_type_value(event.event_type) == MTProtoUsageEventType.ERROR.value else 0

        user_ids = list(aggregates)
        users_by_id: dict[int, User] = {}
        if user_ids:
            users_result = await self.session.execute(select(User).where(User.id.in_(user_ids)))
            users_by_id = {int(user.id): user for user in users_result.scalars().all()}

        safe_limit = min(max(limit, 1), 100)
        metric_key = {
            "traffic": "traffic_bytes",
            "duration": "duration_ms",
            "connections": "connection_count",
            "errors": "error_count",
        }[metric]
        items = sorted(
            (
                {
                    "user_id": user_id,
                    "user_email": users_by_id.get(user_id).email if users_by_id.get(user_id) else None,
                    "user_display_name": users_by_id.get(user_id).display_name if users_by_id.get(user_id) else None,
                    "traffic_bytes": values["traffic"],
                    "duration_ms": values["duration"],
                    "connection_count": values["connections"],
                    "error_count": values["errors"],
                }
                for user_id, values in aggregates.items()
            ),
            key=lambda item: (-int(item[metric_key]), int(item["user_id"])),
        )[:safe_limit]
        logger.info(
            "[M-056][build_top_users][TOP_USERS] "
            f"metric={metric} returned={len(items)}"
        )
        return items
    # END_BLOCK_TOP_USERS

    # START_CONTRACT: detect_abuse_signals
    #   PURPOSE: Record observe-only abuse signals from a recent usage window
    #   INPUTS: window_days and thresholds
    #   OUTPUTS: list of created signal dicts
    #   SIDE_EFFECTS: inserts MTProtoAbuseSignal rows, never disables assignments
    #   LINKS: M-056, V-M-056
    # END_CONTRACT: detect_abuse_signals
    # START_BLOCK_DETECT_ABUSE
    async def detect_abuse_signals(
        self,
        *,
        window_days: int = 1,
        ip_threshold: int = 8,
        concurrency_threshold: int = 20,
        traffic_threshold_bytes: int = 5 * 1024 * 1024 * 1024,
        error_threshold: int = 20,
    ) -> list[dict[str, object]]:
        """Create observe-only abuse signals for current telemetry."""
        start = _window_start(window_days)
        end = _utcnow()
        result = await self.session.execute(
            select(MTProtoUsageEvent).where(
                MTProtoUsageEvent.assignment_id.is_not(None),
                MTProtoUsageEvent.observed_at >= start,
            )
        )
        events_by_assignment: dict[int, list[MTProtoUsageEvent]] = defaultdict(list)
        for event in result.scalars().all():
            if event.assignment_id is not None:
                events_by_assignment[int(event.assignment_id)].append(event)

        created: list[dict[str, object]] = []
        for assignment_id, events in events_by_assignment.items():
            user_id = next((event.user_id for event in events if event.user_id is not None), None)
            ip_count = len({event.ip_hash for event in events if event.ip_hash})
            traffic = sum(_traffic_total(event) for event in events)
            errors = len([event for event in events if _event_type_value(event.event_type) == MTProtoUsageEventType.ERROR.value])
            concurrency = max((event.connection_count for event in events), default=0)
            checks = [
                (MTProtoAbuseSignalType.MANY_IP_HASHES, ip_count, ip_threshold),
                (MTProtoAbuseSignalType.HIGH_CONCURRENCY, concurrency, concurrency_threshold),
                (MTProtoAbuseSignalType.TRAFFIC_SPIKE, traffic, traffic_threshold_bytes),
                (MTProtoAbuseSignalType.REPEATED_ERRORS, errors, error_threshold),
            ]
            for signal_type, metric_value, threshold_value in checks:
                if metric_value <= threshold_value:
                    continue
                signal = MTProtoAbuseSignal(
                    assignment_id=assignment_id,
                    user_id=int(user_id) if user_id is not None else None,
                    signal_type=signal_type,
                    severity="medium" if metric_value < threshold_value * 2 else "high",
                    observe_only=True,
                    window_start=start,
                    window_end=end,
                    metric_value=int(metric_value),
                    threshold_value=int(threshold_value),
                )
                self.session.add(signal)
                await self.session.flush()
                created.append(self._serialize_abuse_signal(signal))

        logger.info(
            "[M-056][detect_abuse_signals][OBSERVE_ONLY] "
            f"created={len(created)} window_days={window_days}"
        )
        return created
    # END_BLOCK_DETECT_ABUSE

    # START_BLOCK_EVENT_AND_SIGNAL_LISTS
    async def list_events(
        self,
        *,
        assignment_id: int | None = None,
        event_type: MTProtoUsageEventType | None = None,
        window_days: int = 30,
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, object]:
        start = _window_start(window_days)
        conditions = [MTProtoUsageEvent.observed_at >= start]
        if assignment_id is not None:
            conditions.append(MTProtoUsageEvent.assignment_id == assignment_id)
        if event_type is not None:
            conditions.append(MTProtoUsageEvent.event_type == event_type)
        total = int((await self.session.execute(select(func.count(MTProtoUsageEvent.id)).where(*conditions))).scalar() or 0)
        safe_offset = max(offset, 0)
        safe_limit = min(max(limit, 1), 500)
        result = await self.session.execute(
            select(MTProtoUsageEvent)
            .where(*conditions)
            .order_by(MTProtoUsageEvent.observed_at.desc(), MTProtoUsageEvent.id.desc())
            .offset(safe_offset)
            .limit(safe_limit)
        )
        items = [self._serialize_event(event) for event in result.scalars().all()]
        return {"items": items, "total": total, "offset": safe_offset, "limit": safe_limit}

    async def list_abuse_signals(
        self,
        *,
        assignment_id: int | None = None,
        window_days: int = 30,
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, object]:
        start = _window_start(window_days)
        conditions = [MTProtoAbuseSignal.window_start >= start]
        if assignment_id is not None:
            conditions.append(MTProtoAbuseSignal.assignment_id == assignment_id)
        total = int((await self.session.execute(select(func.count(MTProtoAbuseSignal.id)).where(*conditions))).scalar() or 0)
        safe_offset = max(offset, 0)
        safe_limit = min(max(limit, 1), 500)
        result = await self.session.execute(
            select(MTProtoAbuseSignal)
            .where(*conditions)
            .order_by(MTProtoAbuseSignal.created_at.desc(), MTProtoAbuseSignal.id.desc())
            .offset(safe_offset)
            .limit(safe_limit)
        )
        return {
            "items": [self._serialize_abuse_signal(signal) for signal in result.scalars().all()],
            "total": total,
            "offset": safe_offset,
            "limit": safe_limit,
        }
    # END_BLOCK_EVENT_AND_SIGNAL_LISTS

    # START_BLOCK_PRIVATE_HELPERS
    async def _traffic_window(self, *, days: int) -> dict[str, int]:
        start = _window_start(days)
        result = await self.session.execute(
            select(MTProtoUsageEvent).where(MTProtoUsageEvent.observed_at >= start)
        )
        events = list(result.scalars().all())
        return {
            "bytes_in": int(sum(event.bytes_in for event in events)),
            "bytes_out": int(sum(event.bytes_out for event in events)),
            "traffic_bytes": int(sum(_traffic_total(event) for event in events)),
            "connection_count": int(sum(event.connection_count for event in events)),
            "duration_ms": int(sum(event.duration_ms for event in events)),
            "error_count": len([event for event in events if _event_type_value(event.event_type) == MTProtoUsageEventType.ERROR.value]),
        }

    async def _event_count(
        self,
        event_type: MTProtoUsageEventType,
        *,
        start: datetime,
    ) -> int:
        return int(
            (
                await self.session.execute(
                    select(func.count(MTProtoUsageEvent.id)).where(
                        MTProtoUsageEvent.event_type == event_type,
                        MTProtoUsageEvent.observed_at >= start,
                    )
                )
            ).scalar()
            or 0
        )

    async def _events_for_assignment(
        self,
        *,
        assignment_id: int,
        start: datetime,
    ) -> list[MTProtoUsageEvent]:
        result = await self.session.execute(
            select(MTProtoUsageEvent)
            .where(
                MTProtoUsageEvent.assignment_id == assignment_id,
                MTProtoUsageEvent.observed_at >= start,
            )
            .order_by(MTProtoUsageEvent.observed_at.desc(), MTProtoUsageEvent.id.desc())
        )
        return list(result.scalars().all())

    async def _sessions_for_assignment(
        self,
        *,
        assignment_id: int,
        start: datetime,
    ) -> list[MTProtoUsageSession]:
        result = await self.session.execute(
            select(MTProtoUsageSession)
            .where(
                MTProtoUsageSession.assignment_id == assignment_id,
                MTProtoUsageSession.started_at >= start,
            )
            .order_by(MTProtoUsageSession.started_at.desc(), MTProtoUsageSession.id.desc())
        )
        return list(result.scalars().all())

    def _telemetry_status(self, latest_event: datetime | None) -> str:
        latest = _coerce_aware(latest_event)
        if latest is None:
            return "missing"
        if latest < _utcnow() - timedelta(minutes=10):
            return "stale"
        return "fresh"

    def _proof_status(self, latest_req_pq: datetime | None) -> str:
        if latest_req_pq is None:
            return "missing"
        if latest_req_pq < _utcnow() - timedelta(minutes=10):
            return "stale"
        return "fresh"

    def _serialize_event(self, event: MTProtoUsageEvent) -> dict[str, object]:
        return {
            "id": event.id,
            "assignment_id": event.assignment_id,
            "user_id": event.user_id,
            "event_type": _event_type_value(event.event_type),
            "observed_at": _iso(event.observed_at),
            "sni_masked": event.sni_masked,
            "ip_hash_prefix": event.ip_hash[:12] if event.ip_hash else None,
            "bytes_in": event.bytes_in,
            "bytes_out": event.bytes_out,
            "duration_ms": event.duration_ms,
            "connection_count": event.connection_count,
            "error_code": event.error_code,
            "reason_code": event.reason_code,
        }

    def _serialize_abuse_signal(self, signal: MTProtoAbuseSignal) -> dict[str, object]:
        return {
            "id": signal.id,
            "assignment_id": signal.assignment_id,
            "user_id": signal.user_id,
            "signal_type": _event_type_value(signal.signal_type),
            "severity": signal.severity,
            "observe_only": signal.observe_only,
            "window_start": _iso(signal.window_start),
            "window_end": _iso(signal.window_end),
            "metric_value": signal.metric_value,
            "threshold_value": signal.threshold_value,
            "reason_code": signal.reason_code,
        }
    # END_BLOCK_PRIVATE_HELPERS
# END_BLOCK_ANALYTICS_SERVICE
