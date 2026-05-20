"""MTProto admin analytics service.

# FILE: backend/app/mtproto/analytics_service.py
# VERSION: 1.1.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Build operator-safe MTProto usage analytics from metadata-only telemetry
#   SCOPE: Global summaries, per-assignment usage, top users, timeseries, user investigation details,
#          storage budget, event listings, and observe-first abuse signals with admin alert handoff
#   DEPENDS: M-001 (DB), M-042 (assignments), M-054 (usage telemetry), M-055 (runtime telemetry), M-060 (alerts), M-061 (IP observability)
#   LINKS: M-056, M-060, M-061, V-M-056, V-M-060, V-M-061
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MTProtoAnalyticsService - Query and aggregate MTProto usage telemetry for admin APIs
#   build_global_summary - Return issued totals, status counts, runtime proof, traffic windows, and abuse counts
#   build_assignment_usage - Return one assignment's usage, sessions, errors, last seen, and abuse signals
#   build_top_users - Rank users by traffic, duration, connection count, or error count
#   build_timeseries - Build graph-ready traffic/connection/duration/error buckets
#   search_user_proxies - Search issued proxies by user, email, SNI, status, or id
#   build_user_investigation - Explicit admin-only user/proxy usage detail with IP evidence
#   build_storage_budget - Return retention windows and storage-growth counters
#   detect_abuse_signals - Write observe-only abuse signals from usage windows
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.1.0 - Added Phase-43 timeseries, user investigation, storage budget, and alert handoff.
#   LAST_CHANGE: v1.0.0 - Added Phase-42 MTProto analytics service
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Literal

from loguru import logger
from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mtproto.models import MTProtoAssignment, MTProtoAssignmentStatus
from app.mtproto.usage_models import (
    MTProtoAbuseSignal,
    MTProtoAbuseSignalType,
    MTProtoAdminAlert,
    MTProtoAdminAlertStatus,
    MTProtoBlockedIP,
    MTProtoIPObservation,
    MTProtoUsageEvent,
    MTProtoUsageEventType,
    MTProtoUsageRollup,
    MTProtoUsageSession,
    MTProtoUsageState,
)
from app.mtproto.ip_observability import (
    current_ip_summary,
    ip_observation_count,
    list_user_ip_observations,
)
from app.mtproto.usage_repository import mask_sni
from app.users.models import User


TopUserMetric = Literal["traffic", "duration", "connections", "errors"]
TimeseriesBucket = Literal["hour", "day"]


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


def _bucket_start(value: datetime, bucket: TimeseriesBucket) -> datetime:
    value = _coerce_aware(value) or _utcnow()
    if bucket == "hour":
        return value.replace(minute=0, second=0, microsecond=0)
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


def _severity_for(metric_value: int, threshold_value: int) -> str:
    if threshold_value <= 0:
        return "critical" if metric_value > 0 else "low"
    if metric_value >= threshold_value * 3:
        return "critical"
    if metric_value >= threshold_value * 2:
        return "high"
    return "medium"
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
        open_alert_count = int(
            (
                await self.session.execute(
                    select(func.count(MTProtoAdminAlert.id)).where(
                        MTProtoAdminAlert.status == MTProtoAdminAlertStatus.OPEN
                    )
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
            "open_alert_count": open_alert_count,
            "alert_counts": {
                "open": open_alert_count,
                "high_critical": open_alert_count,
            },
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
                severity = _severity_for(int(metric_value), int(threshold_value))
                signal = MTProtoAbuseSignal(
                    assignment_id=assignment_id,
                    user_id=int(user_id) if user_id is not None else None,
                    signal_type=signal_type,
                    severity=severity,
                    observe_only=True,
                    window_start=start,
                    window_end=end,
                    metric_value=int(metric_value),
                    threshold_value=int(threshold_value),
                )
                self.session.add(signal)
                await self.session.flush()
                if severity in {"high", "critical"}:
                    from app.mtproto.admin_alerts import create_abuse_alert

                    await create_abuse_alert(self.session, signal)
                    logger.info(
                        "[M-056][detect_abuse_signals][ALERT_HANDOFF] "
                        f"assignment_id={assignment_id} signal_type={signal_type.value} severity={severity}"
                    )
                created.append(self._serialize_abuse_signal(signal))

        logger.info(
            "[M-056][detect_abuse_signals][OBSERVE_ONLY] "
            f"created={len(created)} window_days={window_days}"
        )
        return created
    # END_BLOCK_DETECT_ABUSE

    # START_CONTRACT: build_timeseries
    #   PURPOSE: Return graph-ready buckets for MTProto usage metrics
    #   INPUTS: bucket; window_days; assignment_id
    #   OUTPUTS: dict with ordered bucket rows
    #   SIDE_EFFECTS: database reads and redacted log marker
    #   LINKS: M-056, M-057, V-M-056
    # END_CONTRACT: build_timeseries
    # START_BLOCK_TIMESERIES
    async def build_timeseries(
        self,
        *,
        bucket: TimeseriesBucket = "day",
        window_days: int = 30,
        assignment_id: int | None = None,
    ) -> dict[str, object]:
        """Return graph-ready usage buckets for the admin UI."""
        safe_bucket: TimeseriesBucket = "hour" if bucket == "hour" else "day"
        safe_days = min(max(window_days, 1), 365)
        start = _window_start(safe_days)
        conditions = [MTProtoUsageEvent.observed_at >= start]
        if assignment_id is not None:
            conditions.append(MTProtoUsageEvent.assignment_id == assignment_id)
        result = await self.session.execute(select(MTProtoUsageEvent).where(*conditions))
        buckets: dict[datetime, dict[str, int | str]] = {}
        for event in result.scalars().all():
            key = _bucket_start(event.observed_at, safe_bucket)
            item = buckets.setdefault(
                key,
                {
                    "bucket_start": key.isoformat(),
                    "bytes_in": 0,
                    "bytes_out": 0,
                    "traffic_bytes": 0,
                    "connection_count": 0,
                    "active_connections": 0,
                    "duration_ms": 0,
                    "error_count": 0,
                    "event_count": 0,
                },
            )
            item["bytes_in"] = int(item["bytes_in"]) + int(event.bytes_in or 0)
            item["bytes_out"] = int(item["bytes_out"]) + int(event.bytes_out or 0)
            item["traffic_bytes"] = int(item["traffic_bytes"]) + _traffic_total(event)
            item["connection_count"] = int(item["connection_count"]) + int(event.connection_count or 0)
            item["duration_ms"] = int(item["duration_ms"]) + int(event.duration_ms or 0)
            item["event_count"] = int(item["event_count"]) + 1
            if _event_type_value(event.event_type) == MTProtoUsageEventType.ACTIVE_CONNECTION.value:
                item["active_connections"] = max(int(item["active_connections"]), int(event.connection_count or 0))
            if _event_type_value(event.event_type) == MTProtoUsageEventType.ERROR.value:
                item["error_count"] = int(item["error_count"]) + 1
        items = [buckets[key] for key in sorted(buckets)]
        logger.info(
            "[M-056][build_timeseries][TIMESERIES] "
            f"bucket={safe_bucket} days={safe_days} assignment_id={assignment_id or 'global'} buckets={len(items)}"
        )
        return {
            "bucket": safe_bucket,
            "days": safe_days,
            "assignment_id": assignment_id,
            "items": items,
        }
    # END_BLOCK_TIMESERIES

    # START_CONTRACT: search_user_proxies
    #   PURPOSE: Search issued MTProto proxies by user, email, SNI, status, or id
    #   INPUTS: query; offset; limit
    #   OUTPUTS: paginated redacted assignment rows with last seen context
    #   SIDE_EFFECTS: database reads and redacted log marker
    #   LINKS: M-057, M-058, V-M-057
    # END_CONTRACT: search_user_proxies
    # START_BLOCK_USER_SEARCH
    async def search_user_proxies(
        self,
        *,
        query: str = "",
        offset: int = 0,
        limit: int = 25,
    ) -> dict[str, object]:
        """Search MTProto assignments with compact user context."""
        conditions = []
        search_value = query.strip()
        if search_value:
            needle = f"%{search_value.lower()}%"
            clauses = [
                func.lower(func.coalesce(User.email, "")).like(needle),
                func.lower(func.coalesce(User.name, "")).like(needle),
                func.lower(MTProtoAssignment.sni).like(needle),
                func.lower(cast(MTProtoAssignment.status, String)).like(needle),
            ]
            if search_value.isdigit():
                numeric_value = int(search_value)
                clauses.extend(
                    [
                        MTProtoAssignment.id == numeric_value,
                        MTProtoAssignment.user_id == numeric_value,
                    ]
                )
            from sqlalchemy import or_

            conditions.append(or_(*clauses))
        safe_offset = max(offset, 0)
        safe_limit = min(max(limit, 1), 100)
        total = int(
            (
                await self.session.execute(
                    select(func.count(MTProtoAssignment.id))
                    .join(User, User.id == MTProtoAssignment.user_id)
                    .where(*conditions)
                )
            ).scalar()
            or 0
        )
        result = await self.session.execute(
            select(MTProtoAssignment, User, MTProtoUsageState)
            .join(User, User.id == MTProtoAssignment.user_id)
            .outerjoin(MTProtoUsageState, MTProtoUsageState.assignment_id == MTProtoAssignment.id)
            .where(*conditions)
            .order_by(MTProtoAssignment.issued_at.desc(), MTProtoAssignment.id.desc())
            .offset(safe_offset)
            .limit(safe_limit)
        )
        items = []
        for assignment, user, state in result.all():
            items.append(
                {
                    "assignment_id": assignment.id,
                    "user_id": assignment.user_id,
                    "user_email": user.email,
                    "user_display_name": user.display_name,
                    "sni_masked": mask_sni(assignment.sni),
                    "status": assignment.status.value,
                    "rotation_marker": assignment.rotation_marker,
                    "issued_at": _iso(assignment.issued_at),
                    "last_seen_at": _iso(state.last_seen_at if state else None),
                    "active_connections": int(state.active_connections if state else 0),
                }
            )
        logger.info(
            "[M-057][admin_mtproto_user_search][USER_SEARCH] "
            f"query={bool(search_value)} returned={len(items)} total={total}"
        )
        return {"items": items, "total": total, "offset": safe_offset, "limit": safe_limit}
    # END_BLOCK_USER_SEARCH

    # START_CONTRACT: build_user_investigation
    #   PURPOSE: Return explicit admin-only user/proxy detail with decrypted IP evidence
    #   INPUTS: assignment_id; window_days; admin_id
    #   OUTPUTS: dict with assignment, usage, sessions, current IPs, last IP, IP observations, and graph buckets
    #   SIDE_EFFECTS: database reads and M-061 admin-only decrypt markers
    #   LINKS: M-057, M-058, M-061, V-M-057, V-M-061
    # END_CONTRACT: build_user_investigation
    # START_BLOCK_USER_INVESTIGATION
    async def build_user_investigation(
        self,
        *,
        assignment_id: int,
        window_days: int = 90,
        admin_id: int | None = None,
    ) -> dict[str, object] | None:
        """Return one assignment's explicit admin investigation payload."""
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
        ip_summary = await current_ip_summary(
            self.session,
            assignment_id=assignment_id,
            user_id=int(assignment.user_id),
            admin_id=admin_id,
        )
        ip_history = await list_user_ip_observations(
            self.session,
            assignment_id=assignment_id,
            user_id=int(assignment.user_id),
            limit=100,
            admin_id=admin_id,
        )
        timeseries = await self.build_timeseries(
            bucket="day",
            window_days=window_days,
            assignment_id=assignment_id,
        )
        payload = {
            "assignment": {
                "id": assignment.id,
                "assignment_id": assignment.id,
                "user_id": assignment.user_id,
                "user_email": user.email,
                "user_display_name": user.display_name,
                "sni_masked": mask_sni(assignment.sni),
                "status": assignment.status.value,
                "rotation_marker": assignment.rotation_marker,
                "issued_at": _iso(assignment.issued_at),
                "created_at": _iso(assignment.created_at),
                "updated_at": _iso(assignment.updated_at),
            },
            "window_days": min(max(window_days, 1), 365),
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
            "current_ips": ip_summary["current_ips"],
            "last_ip": ip_summary["last_ip"],
            "ip_source_status": ip_summary["source_status"],
            "ip_observations": ip_history["items"],
            "sessions": [self._serialize_session(session) for session in sessions[:100]],
            "timeseries": timeseries["items"],
            "abuse_signals": (await self.list_abuse_signals(assignment_id=assignment_id, limit=20))["items"],
        }
        logger.info(
            "[M-057][admin_mtproto_user_usage][IP_INVESTIGATION_SCOPE] "
            f"assignment_id={assignment_id} admin_id={admin_id or 'unknown'}"
        )
        return payload
    # END_BLOCK_USER_INVESTIGATION

    # START_CONTRACT: build_storage_budget
    #   PURPOSE: Report storage counters and retention windows for MTProto analytics data
    #   INPUTS: none
    #   OUTPUTS: dict
    #   SIDE_EFFECTS: database reads and redacted log marker
    #   LINKS: M-056, M-054, M-060, M-061, V-M-056
    # END_CONTRACT: build_storage_budget
    # START_BLOCK_STORAGE_BUDGET
    async def build_storage_budget(self) -> dict[str, object]:
        """Return row counts and retention windows for MTProto analytics storage."""
        raw_events = int((await self.session.execute(select(func.count(MTProtoUsageEvent.id)))).scalar() or 0)
        sessions = int((await self.session.execute(select(func.count(MTProtoUsageSession.id)))).scalar() or 0)
        rollups = int((await self.session.execute(select(func.count(MTProtoUsageRollup.id)))).scalar() or 0)
        signals = int((await self.session.execute(select(func.count(MTProtoAbuseSignal.id)))).scalar() or 0)
        alerts = int((await self.session.execute(select(func.count(MTProtoAdminAlert.id)))).scalar() or 0)
        blocked_ips = int((await self.session.execute(select(func.count(MTProtoBlockedIP.id)))).scalar() or 0)
        ip_rows = await ip_observation_count(self.session)
        estimated_bytes = (
            raw_events * 900
            + sessions * 700
            + rollups * 400
            + signals * 500
            + alerts * 900
            + ip_rows * 650
            + blocked_ips * 600
        )
        payload = {
            "retention": {
                "raw_events_days": 30,
                "sessions_days": 90,
                "ip_observations_days": 90,
                "hourly_rollups_days": 90,
                "daily_rollups_days": 365,
                "monthly_rollups_months": 24,
                "alerts_days": 180,
            },
            "counts": {
                "raw_events": raw_events,
                "sessions": sessions,
                "rollups": rollups,
                "abuse_signals": signals,
                "admin_alerts": alerts,
                "ip_observations": ip_rows,
                "blocked_ips": blocked_ips,
            },
            "estimated_bytes": estimated_bytes,
        }
        logger.info(
            "[M-056][build_storage_budget][RETENTION_BUDGET] "
            f"raw_events={raw_events} ip_observations={ip_rows} estimated_bytes={estimated_bytes}"
        )
        return payload
    # END_BLOCK_STORAGE_BUDGET

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

    def _serialize_session(self, session: MTProtoUsageSession) -> dict[str, object]:
        return {
            "id": session.id,
            "assignment_id": session.assignment_id,
            "user_id": session.user_id,
            "started_at": _iso(session.started_at),
            "ended_at": _iso(session.ended_at),
            "duration_ms": session.duration_ms,
            "bytes_in": session.bytes_in,
            "bytes_out": session.bytes_out,
            "connection_count": session.connection_count,
            "error_count": session.error_count,
            "active": session.active,
            "client_ip_hash_prefix": session.client_ip_hash[:12] if session.client_ip_hash else None,
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
