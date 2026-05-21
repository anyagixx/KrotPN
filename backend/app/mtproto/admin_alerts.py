"""MTProto admin abuse alerts.

# FILE: backend/app/mtproto/admin_alerts.py
# VERSION: 1.1.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Maintain a durable admin inbox for high/critical MTProto abuse signals and reviewed actions
#   SCOPE: Alert dedupe, listing, acknowledgement, resolution, action outcome tracking,
#          TTL-bound IP block record creation, and alert retention
#   DEPENDS: M-001 (DB/security), M-026 (admin audit caller), M-056 (abuse signals), M-061 (IP evidence)
#   LINKS: M-060, V-M-060
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   create_abuse_alert - Create or update one high/critical deduplicated alert from an abuse signal
#   list_admin_alerts - Return paginated alerts for the admin panel
#   acknowledge_alert - Mark one alert reviewed by admin without enforcement
#   resolve_alert - Resolve one alert after action or dismissal
#   mark_alert_action - Persist action outcome on an alert without raw payloads
#   block_ip_for_alert - Create a TTL-bound IP block record from trusted M-061 evidence and archive the alert
#   apply_alert_retention - Prune old resolved alert history
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.1.0 - Resolve reviewed IP-block alerts so actions leave the open inbox and remain archived.
#   LAST_CHANGE: v1.0.0 - Added Phase-43 MTProto admin abuse alert service
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from loguru import logger
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mtproto.models import MTProtoAssignment
from app.mtproto.usage_models import (
    MTProtoAbuseSignal,
    MTProtoAdminAlert,
    MTProtoAdminAlertStatus,
    MTProtoBlockedIP,
    MTProtoIPBlockStatus,
    MTProtoIPObservation,
)
from app.mtproto.usage_repository import mask_sni
from app.users.models import User


ALERT_RETENTION_DAYS = 180
ALERTING_SEVERITIES = {"high", "critical"}


# START_BLOCK_ALERT_HELPERS
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_aware(value: datetime | None) -> datetime:
    if value is None:
        return _utcnow()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _event_type_value(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _alert_dedupe_key(signal: MTProtoAbuseSignal) -> str:
    assignment_key = signal.assignment_id if signal.assignment_id is not None else "global"
    day_key = _coerce_aware(signal.window_start).strftime("%Y%m%d")
    return f"{assignment_key}:{_event_type_value(signal.signal_type)}:{signal.severity}:{day_key}"


def _alert_title(signal: MTProtoAbuseSignal) -> str:
    return f"{_event_type_value(signal.signal_type)} abuse signal"


def _safe_metadata(**values: object) -> str:
    safe: dict[str, object] = {}
    for key, value in values.items():
        if value is None or isinstance(value, (int, float, bool)):
            safe[key] = value
        else:
            safe[key] = str(value)[:160]
    return json.dumps(safe, sort_keys=True)
# END_BLOCK_ALERT_HELPERS


# START_CONTRACT: create_abuse_alert
#   PURPOSE: Create or update one deduplicated high/critical alert from an abuse signal
#   INPUTS: session; signal
#   OUTPUTS: MTProtoAdminAlert | None
#   SIDE_EFFECTS: Inserts/updates alert row and logs dedupe/create marker
#   LINKS: M-060, M-056, V-M-060
# END_CONTRACT: create_abuse_alert
# START_BLOCK_CREATE_ALERT
async def create_abuse_alert(
    session: AsyncSession,
    signal: MTProtoAbuseSignal,
) -> MTProtoAdminAlert | None:
    """Create or update a durable admin alert for clear abuse signals."""
    severity = str(signal.severity or "low").lower()
    if severity not in ALERTING_SEVERITIES:
        return None

    dedupe_key = _alert_dedupe_key(signal)
    result = await session.execute(
        select(MTProtoAdminAlert).where(MTProtoAdminAlert.dedupe_key == dedupe_key)
    )
    row = result.scalar_one_or_none()
    now = _utcnow()
    if row is None:
        row = MTProtoAdminAlert(
            dedupe_key=dedupe_key,
            abuse_signal_id=signal.id,
            assignment_id=signal.assignment_id,
            user_id=signal.user_id,
            signal_type=_event_type_value(signal.signal_type),
            severity=severity,
            status=MTProtoAdminAlertStatus.OPEN,
            title=_alert_title(signal),
            reason_code=signal.reason_code,
            metric_value=signal.metric_value,
            threshold_value=signal.threshold_value,
            window_start=_coerce_aware(signal.window_start),
            window_end=_coerce_aware(signal.window_end),
            first_seen_at=now,
            last_seen_at=now,
            metadata_json=_safe_metadata(observe_only=signal.observe_only),
        )
        session.add(row)
        await session.flush()
        logger.info(
            "[M-060][create_abuse_alert][ALERT_CREATED] "
            f"alert_id={row.id} assignment_id={signal.assignment_id} severity={severity}"
        )
        return row

    row.abuse_signal_id = signal.id
    row.metric_value = max(row.metric_value, signal.metric_value)
    row.threshold_value = signal.threshold_value
    row.last_seen_at = now
    row.occurrence_count += 1
    row.updated_at = now
    if row.status == MTProtoAdminAlertStatus.RESOLVED:
        row.status = MTProtoAdminAlertStatus.OPEN
        row.resolved_at = None
        row.resolved_by_admin_id = None
    await session.flush()
    logger.info(
        "[M-060][create_abuse_alert][ALERT_DEDUPED] "
        f"alert_id={row.id} assignment_id={signal.assignment_id} occurrences={row.occurrence_count}"
    )
    return row
# END_BLOCK_CREATE_ALERT


# START_BLOCK_SERIALIZE_ALERT
async def _user_assignment_context(
    session: AsyncSession,
    alert: MTProtoAdminAlert,
) -> tuple[User | None, MTProtoAssignment | None]:
    user = await session.get(User, int(alert.user_id)) if alert.user_id is not None else None
    assignment = (
        await session.get(MTProtoAssignment, int(alert.assignment_id))
        if alert.assignment_id is not None
        else None
    )
    return user, assignment


async def serialize_alert(session: AsyncSession, alert: MTProtoAdminAlert) -> dict[str, object]:
    """Return an admin-safe alert payload without raw IP strings."""
    user, assignment = await _user_assignment_context(session, alert)
    return {
        "id": alert.id,
        "assignment_id": alert.assignment_id,
        "user_id": alert.user_id,
        "user_email": user.email if user else None,
        "user_display_name": user.display_name if user else None,
        "sni_masked": mask_sni(assignment.sni) if assignment else None,
        "signal_type": alert.signal_type,
        "severity": alert.severity,
        "status": _event_type_value(alert.status),
        "title": alert.title,
        "reason_code": alert.reason_code,
        "metric_value": alert.metric_value,
        "threshold_value": alert.threshold_value,
        "window_start": _iso(alert.window_start),
        "window_end": _iso(alert.window_end),
        "first_seen_at": _iso(alert.first_seen_at),
        "last_seen_at": _iso(alert.last_seen_at),
        "occurrence_count": alert.occurrence_count,
        "acknowledged_at": _iso(alert.acknowledged_at),
        "resolved_at": _iso(alert.resolved_at),
        "action_taken": alert.action_taken,
        "action_result": alert.action_result,
    }
# END_BLOCK_SERIALIZE_ALERT


# START_CONTRACT: list_admin_alerts
#   PURPOSE: Return paginated durable MTProto alerts for the admin panel
#   INPUTS: session; status_filter; severity; offset; limit
#   OUTPUTS: dict
#   SIDE_EFFECTS: database reads only
#   LINKS: M-060, M-057, V-M-060
# END_CONTRACT: list_admin_alerts
# START_BLOCK_LIST_ALERTS
async def list_admin_alerts(
    session: AsyncSession,
    *,
    status_filter: MTProtoAdminAlertStatus | None = None,
    severity: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> dict[str, object]:
    """Return admin alert rows ordered by most recent signal time."""
    conditions = []
    if status_filter is not None:
        conditions.append(MTProtoAdminAlert.status == status_filter)
    if severity:
        conditions.append(MTProtoAdminAlert.severity == severity.lower())
    safe_offset = max(offset, 0)
    safe_limit = min(max(limit, 1), 500)
    total = int((await session.execute(select(func.count(MTProtoAdminAlert.id)).where(*conditions))).scalar() or 0)
    result = await session.execute(
        select(MTProtoAdminAlert)
        .where(*conditions)
        .order_by(MTProtoAdminAlert.last_seen_at.desc(), MTProtoAdminAlert.id.desc())
        .offset(safe_offset)
        .limit(safe_limit)
    )
    alerts = list(result.scalars().all())
    items = [await serialize_alert(session, alert) for alert in alerts]
    open_count = int(
        (
            await session.execute(
                select(func.count(MTProtoAdminAlert.id)).where(
                    MTProtoAdminAlert.status == MTProtoAdminAlertStatus.OPEN
                )
            )
        ).scalar()
        or 0
    )
    logger.info(
        "[M-060][list_admin_alerts][ALERT_LIST] "
        f"returned={len(items)} total={total} open={open_count}"
    )
    return {"items": items, "total": total, "open_count": open_count, "offset": safe_offset, "limit": safe_limit}
# END_BLOCK_LIST_ALERTS


async def get_alert_or_none(session: AsyncSession, alert_id: int) -> MTProtoAdminAlert | None:
    """Load one alert row by id."""
    return await session.get(MTProtoAdminAlert, alert_id)


# START_CONTRACT: acknowledge_alert
#   PURPOSE: Mark one alert as acknowledged without changing runtime access
#   INPUTS: session; alert_id; admin_id
#   OUTPUTS: serialized alert dict | None
#   SIDE_EFFECTS: updates alert state
#   LINKS: M-060, V-M-060
# END_CONTRACT: acknowledge_alert
# START_BLOCK_ACKNOWLEDGE_ALERT
async def acknowledge_alert(
    session: AsyncSession,
    *,
    alert_id: int,
    admin_id: int,
) -> dict[str, object] | None:
    """Mark one alert as seen by an admin."""
    alert = await session.get(MTProtoAdminAlert, alert_id)
    if alert is None:
        return None
    now = _utcnow()
    alert.status = MTProtoAdminAlertStatus.ACKNOWLEDGED
    alert.acknowledged_at = now
    alert.acknowledged_by_admin_id = admin_id
    alert.updated_at = now
    await session.flush()
    logger.info(
        "[M-060][acknowledge_alert][ALERT_ACKNOWLEDGED] "
        f"alert_id={alert_id} admin_id={admin_id}"
    )
    return await serialize_alert(session, alert)
# END_BLOCK_ACKNOWLEDGE_ALERT


# START_CONTRACT: resolve_alert
#   PURPOSE: Resolve one alert after admin review or action
#   INPUTS: session; alert_id; admin_id; action_taken; action_result
#   OUTPUTS: serialized alert dict | None
#   SIDE_EFFECTS: updates alert state
#   LINKS: M-060, V-M-060
# END_CONTRACT: resolve_alert
# START_BLOCK_RESOLVE_ALERT
async def resolve_alert(
    session: AsyncSession,
    *,
    alert_id: int,
    admin_id: int,
    action_taken: str | None = None,
    action_result: str | None = None,
) -> dict[str, object] | None:
    """Resolve one alert after operator decision."""
    alert = await session.get(MTProtoAdminAlert, alert_id)
    if alert is None:
        return None
    now = _utcnow()
    alert.status = MTProtoAdminAlertStatus.RESOLVED
    alert.resolved_at = now
    alert.resolved_by_admin_id = admin_id
    if action_taken:
        alert.action_taken = action_taken[:80]
    if action_result:
        alert.action_result = action_result[:120]
    alert.updated_at = now
    await session.flush()
    logger.info(
        "[M-060][resolve_alert][ALERT_RESOLVED] "
        f"alert_id={alert_id} admin_id={admin_id} action={alert.action_taken or 'none'}"
    )
    return await serialize_alert(session, alert)
# END_BLOCK_RESOLVE_ALERT


async def mark_alert_action(
    session: AsyncSession,
    *,
    alert_id: int,
    action_taken: str,
    action_result: str,
) -> MTProtoAdminAlert | None:
    """Persist action outcome on an alert without resolving it automatically."""
    alert = await session.get(MTProtoAdminAlert, alert_id)
    if alert is None:
        return None
    alert.action_taken = action_taken[:80]
    alert.action_result = action_result[:120]
    alert.updated_at = _utcnow()
    await session.flush()
    return alert


# START_CONTRACT: block_ip_for_alert
#   PURPOSE: Create a TTL-bound IP block record only from trusted M-061 observation evidence
#   INPUTS: session; alert_id; ip_observation_id; admin_id; ttl_hours; confirm; confirm_risk
#   OUTPUTS: safe block dict | None
#   SIDE_EFFECTS: inserts block record and resolves the reviewed alert with action fields
#   LINKS: M-060, M-061, V-M-060
# END_CONTRACT: block_ip_for_alert
# START_BLOCK_BLOCK_IP
async def block_ip_for_alert(
    session: AsyncSession,
    *,
    alert_id: int,
    ip_observation_id: int,
    admin_id: int,
    ttl_hours: int = 24,
    confirm: bool = False,
    confirm_risk: bool = False,
) -> dict[str, object] | None:
    """Create a reviewed TTL-bound IP block record from retained observation evidence."""
    if not confirm or not confirm_risk:
        raise ValueError("TTL IP block requires explicit confirmation and NAT risk acknowledgement")

    alert = await session.get(MTProtoAdminAlert, alert_id)
    observation = await session.get(MTProtoIPObservation, ip_observation_id)
    if alert is None or observation is None:
        return None
    if alert.assignment_id is not None and observation.assignment_id != alert.assignment_id:
        raise ValueError("IP observation does not belong to alert assignment")
    if _coerce_aware(observation.last_seen_at) < _utcnow() - timedelta(days=90):
        raise ValueError("IP observation is outside the trusted retention window")

    now = _utcnow()
    expires_at = now + timedelta(hours=min(max(ttl_hours, 1), 24 * 30))
    block = MTProtoBlockedIP(
        assignment_id=observation.assignment_id,
        user_id=observation.user_id,
        ip_observation_id=int(observation.id),
        ip_hash=observation.ip_hash,
        ip_prefix=observation.ip_prefix,
        encrypted_ip=observation.encrypted_ip,
        status=MTProtoIPBlockStatus.ACTIVE,
        expires_at=expires_at,
        created_by_admin_id=admin_id,
        metadata_json=_safe_metadata(alert_id=alert_id, reason="admin_reviewed_abuse"),
    )
    session.add(block)
    alert.status = MTProtoAdminAlertStatus.RESOLVED
    alert.resolved_at = now
    alert.resolved_by_admin_id = admin_id
    alert.action_taken = "ip_block"
    alert.action_result = "recorded_pending_runtime_enforcement"
    alert.updated_at = now
    await session.flush()
    logger.info(
        "[M-060][block_ip][CONFIRM_TTL_BLOCK] "
        f"alert_id={alert_id} observation_id={ip_observation_id} admin_id={admin_id} ttl_hours={ttl_hours}"
    )
    return {
        "id": block.id,
        "alert_id": alert_id,
        "assignment_id": block.assignment_id,
        "user_id": block.user_id,
        "ip_observation_id": block.ip_observation_id,
        "ip_hash_prefix": block.ip_hash[:12],
        "ip_prefix": block.ip_prefix,
        "status": _event_type_value(block.status),
        "expires_at": _iso(block.expires_at),
        "enforcement_status": "recorded_pending_runtime_enforcement",
    }
# END_BLOCK_BLOCK_IP


# START_BLOCK_ALERT_RETENTION
async def apply_alert_retention(
    session: AsyncSession,
    *,
    retention_days: int = ALERT_RETENTION_DAYS,
    now: datetime | None = None,
) -> int:
    """Prune old alert history after the configured retention window."""
    cutoff = _coerce_aware(now) - timedelta(days=max(retention_days, 1))
    result = await session.execute(
        delete(MTProtoAdminAlert)
        .where(MTProtoAdminAlert.created_at < cutoff)
        .execution_options(synchronize_session=False)
    )
    deleted_count = int(result.rowcount or 0)
    logger.info(
        "[M-060][apply_alert_retention][RETENTION_PRUNE] "
        f"deleted={deleted_count} retention_days={retention_days}"
    )
    return deleted_count
# END_BLOCK_ALERT_RETENTION
