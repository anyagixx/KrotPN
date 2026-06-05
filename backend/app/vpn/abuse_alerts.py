"""VPN device abuse alert inbox.

# FILE: backend/app/vpn/abuse_alerts.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Maintain a durable admin inbox for confirmed VPN device anti-sharing signals
#   SCOPE: Alert persistence, dedupe, safe serialization, explicit resolve/rotate/block admin actions, and redaction guards
#   DEPENDS: M-001 (database), M-020 (device registry), M-021 (device policy), M-025 (device audit), M-031 (anti-abuse decisions), M-081 (alert inbox)
#   LINKS: M-081, V-M-081
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   VPNDeviceAbuseAlertStatus - Operator review lifecycle for VPN device abuse alerts
#   VPNDeviceAbuseAlert - Durable alert row linked to one user, one device, and one source audit event
#   create_device_abuse_alert - Create or dedupe one open alert from a confirmed device security event
#   list_device_abuse_alerts - Return paginated open or resolved alerts for the admin panel
#   get_device_abuse_alert - Return one serialized alert detail
#   resolve_device_abuse_alert - Archive one alert without mutating VPN access
#   rotate_device_for_alert - Explicitly rotate only the alert device config after confirmation
#   block_device_for_alert - Explicitly block only the alert device after confirmation
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-78 VPN Device Abuse Alert Inbox service and model.
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from enum import Enum
from typing import Any

from loguru import logger
from sqlalchemy import Column, DateTime, Index, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Field, SQLModel

from app.devices.models import DeviceSecurityEvent, DeviceSecurityEventType, UserDevice
from app.devices.service import DeviceAccessPolicyService
from app.users.models import User
from app.vpn.service import VPNService


ALERT_SOURCE_EVENT_TYPES = {
    DeviceSecurityEventType.PING_PONG_ABUSE_DETECTED,
    DeviceSecurityEventType.MULTI_NETWORK_ABUSE_DETECTED,
}
FORBIDDEN_ALERT_MARKERS = (
    "private_key",
    "preshared_key",
    "private_key_enc",
    "preshared_key_enc",
    "[Interface]",
    "Address =",
    "secret=",
    "Bearer ",
)


# START_BLOCK_ALERT_STATUS
class VPNDeviceAbuseAlertStatus(str, Enum):
    """Operator review lifecycle for VPN device abuse alerts."""

    OPEN = "open"
    RESOLVED = "resolved"
# END_BLOCK_ALERT_STATUS


# START_BLOCK_ALERT_MODEL
class VPNDeviceAbuseAlert(SQLModel, table=True):
    """Durable admin alert for confirmed VPN device anti-sharing signals."""

    __tablename__ = "vpn_device_abuse_alerts"

    id: int | None = Field(default=None, primary_key=True)
    dedupe_key: str = Field(index=True, max_length=180)
    source_event_id: int | None = Field(default=None, foreign_key="device_security_events.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    device_id: int = Field(foreign_key="user_devices.id", index=True)
    signal_type: str = Field(index=True, max_length=80)
    severity: str = Field(default="warning", index=True, max_length=20)
    status: VPNDeviceAbuseAlertStatus = Field(default=VPNDeviceAbuseAlertStatus.OPEN, index=True, max_length=30)
    title: str = Field(max_length=180)
    reason_code: str = Field(default="confirmed_anti_sharing_signal", max_length=100)
    user_email_snapshot: str | None = Field(default=None, max_length=255)
    device_name_snapshot: str | None = Field(default=None, max_length=120)
    device_status_snapshot: str | None = Field(default=None, max_length=30)
    config_version: int = Field(default=1, ge=1)
    last_endpoint: str | None = Field(default=None, max_length=255)
    last_handshake_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    first_seen_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), index=True),
    )
    last_seen_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), index=True),
    )
    occurrence_count: int = Field(default=1, ge=1)
    resolved_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    resolved_by_admin_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    action_taken: str | None = Field(default=None, max_length=80)
    action_result: str | None = Field(default=None, max_length=160)
    metadata_json: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), index=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )

    __table_args__ = (
        Index("ix_vpn_device_abuse_alerts_status_seen", "status", "last_seen_at"),
        Index("ix_vpn_device_abuse_alerts_device_status", "device_id", "status"),
        Index("ix_vpn_device_abuse_alerts_user_status", "user_id", "status"),
        Index("ix_vpn_device_abuse_alerts_open_dedupe", "dedupe_key", "status"),
    )
# END_BLOCK_ALERT_MODEL


# START_BLOCK_ALERT_HELPERS
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _event_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _coerce_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _safe_metadata(**values: Any) -> str:
    safe: dict[str, Any] = {}
    for key, value in values.items():
        if value is None or isinstance(value, (int, float, bool)):
            safe[key] = value
        else:
            safe[key] = str(value)[:160]
    payload = json.dumps(safe, sort_keys=True)
    _assert_alert_payload_redacted({"metadata_json": payload})
    return payload


def _dedupe_key(event: DeviceSecurityEvent, device: UserDevice) -> str:
    return f"{event.user_id}:{event.device_id}:{_event_value(event.event_type)}:v{device.config_version}"


def _title(signal_type: str) -> str:
    if signal_type == DeviceSecurityEventType.PING_PONG_ABUSE_DETECTED.value:
        return "VPN config likely shared across alternating endpoints"
    if signal_type == DeviceSecurityEventType.MULTI_NETWORK_ABUSE_DETECTED.value:
        return "VPN config likely shared across too many networks"
    return "VPN device abuse signal"


def _assert_alert_payload_redacted(payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    payload_text = str(payload)
    leaked = next((marker for marker in FORBIDDEN_ALERT_MARKERS if marker in payload_text), None)
    if leaked:
        logger.error("[M-081][vpn_device_abuse_alert][REDACTION_GUARD] leaked_marker=blocked")
        raise ValueError("VPN device abuse alert payload redaction failed")
    logger.info("[M-081][vpn_device_abuse_alert][REDACTION_GUARD] payload=safe")
# END_BLOCK_ALERT_HELPERS


# START_CONTRACT: create_device_abuse_alert
#   PURPOSE: Create or update one open admin alert from a confirmed anti-abuse device event
#   INPUTS: session; event
#   OUTPUTS: VPNDeviceAbuseAlert | None
#   SIDE_EFFECTS: Inserts/updates alert row and emits ALERT_CREATED/ALERT_DEDUPED markers
#   LINKS: M-081, M-025, M-031, V-M-081
# END_CONTRACT: create_device_abuse_alert
# START_BLOCK_CREATE_DEVICE_ABUSE_ALERT
async def create_device_abuse_alert(
    session: AsyncSession,
    event: DeviceSecurityEvent,
) -> VPNDeviceAbuseAlert | None:
    """Create or dedupe a durable admin alert only for confirmed abuse events."""
    signal_type = _event_value(event.event_type)
    if signal_type not in {source.value for source in ALERT_SOURCE_EVENT_TYPES}:
        return None

    device = await session.get(UserDevice, int(event.device_id))
    if device is None:
        return None
    user = await session.get(User, int(event.user_id))
    now = _utcnow()
    dedupe_key = _dedupe_key(event, device)
    result = await session.execute(
        select(VPNDeviceAbuseAlert).where(
            VPNDeviceAbuseAlert.dedupe_key == dedupe_key,
            VPNDeviceAbuseAlert.status == VPNDeviceAbuseAlertStatus.OPEN,
        )
    )
    alert = result.scalar_one_or_none()
    if alert is not None:
        alert.source_event_id = event.id
        alert.severity = _event_value(event.severity)
        alert.last_seen_at = now
        alert.occurrence_count += 1
        alert.updated_at = now
        alert.last_endpoint = device.last_endpoint
        alert.last_handshake_at = _coerce_aware(device.last_handshake_at)
        alert.device_status_snapshot = _event_value(device.status)
        await session.flush()
        logger.info(
            "[M-081][create_device_abuse_alert][ALERT_DEDUPED] "
            f"alert_id={alert.id} user_id={alert.user_id} device_id={alert.device_id} occurrences={alert.occurrence_count}"
        )
        return alert

    alert = VPNDeviceAbuseAlert(
        dedupe_key=dedupe_key,
        source_event_id=event.id,
        user_id=int(event.user_id),
        device_id=int(event.device_id),
        signal_type=signal_type,
        severity=_event_value(event.severity),
        status=VPNDeviceAbuseAlertStatus.OPEN,
        title=_title(signal_type),
        user_email_snapshot=user.email if user else None,
        device_name_snapshot=device.name,
        device_status_snapshot=_event_value(device.status),
        config_version=int(device.config_version),
        last_endpoint=device.last_endpoint,
        last_handshake_at=_coerce_aware(device.last_handshake_at),
        first_seen_at=now,
        last_seen_at=now,
        metadata_json=_safe_metadata(
            source="device_security_event",
            source_event_id=event.id,
            source_created_at=_iso(_coerce_aware(event.created_at)),
        ),
    )
    session.add(alert)
    await session.flush()
    logger.info(
        "[M-081][create_device_abuse_alert][ALERT_CREATED] "
        f"alert_id={alert.id} user_id={alert.user_id} device_id={alert.device_id} signal_type={signal_type}"
    )
    return alert
# END_BLOCK_CREATE_DEVICE_ABUSE_ALERT


# START_BLOCK_SERIALIZE_ALERT
async def serialize_device_abuse_alert(session: AsyncSession, alert: VPNDeviceAbuseAlert) -> dict[str, Any]:
    """Return a safe admin payload without peer secrets or raw configs."""
    user = await session.get(User, int(alert.user_id))
    device = await session.get(UserDevice, int(alert.device_id))
    payload = {
        "id": alert.id,
        "user_id": alert.user_id,
        "user_email": user.email if user else alert.user_email_snapshot,
        "user_display_name": user.display_name if user else None,
        "device_id": alert.device_id,
        "device_name": device.name if device else alert.device_name_snapshot,
        "device_status": _event_value(device.status) if device else alert.device_status_snapshot,
        "source_event_id": alert.source_event_id,
        "signal_type": alert.signal_type,
        "severity": alert.severity,
        "status": _event_value(alert.status),
        "title": alert.title,
        "reason_code": alert.reason_code,
        "config_version": alert.config_version,
        "last_endpoint": alert.last_endpoint,
        "last_handshake_at": _iso(_coerce_aware(alert.last_handshake_at)),
        "first_seen_at": _iso(_coerce_aware(alert.first_seen_at)),
        "last_seen_at": _iso(_coerce_aware(alert.last_seen_at)),
        "occurrence_count": alert.occurrence_count,
        "resolved_at": _iso(_coerce_aware(alert.resolved_at)),
        "resolved_by_admin_id": alert.resolved_by_admin_id,
        "action_taken": alert.action_taken,
        "action_result": alert.action_result,
    }
    _assert_alert_payload_redacted(payload)
    return payload
# END_BLOCK_SERIALIZE_ALERT


# START_CONTRACT: list_device_abuse_alerts
#   PURPOSE: Return paginated VPN device abuse alerts by review status
#   INPUTS: session; status_filter; offset; limit
#   OUTPUTS: dict with items, total, open_count, resolved_count, offset, limit
#   SIDE_EFFECTS: database reads and ALERT_LIST marker
#   LINKS: M-081, V-M-081
# END_CONTRACT: list_device_abuse_alerts
# START_BLOCK_LIST_DEVICE_ABUSE_ALERTS
async def list_device_abuse_alerts(
    session: AsyncSession,
    *,
    status_filter: VPNDeviceAbuseAlertStatus | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Return admin alert rows ordered by newest signal."""
    conditions = []
    if status_filter is not None:
        conditions.append(VPNDeviceAbuseAlert.status == status_filter)
    safe_offset = max(offset, 0)
    safe_limit = min(max(limit, 1), 200)
    total = int(
        (await session.execute(select(func.count(VPNDeviceAbuseAlert.id)).where(*conditions))).scalar()
        or 0
    )
    result = await session.execute(
        select(VPNDeviceAbuseAlert)
        .where(*conditions)
        .order_by(VPNDeviceAbuseAlert.last_seen_at.desc(), VPNDeviceAbuseAlert.id.desc())
        .offset(safe_offset)
        .limit(safe_limit)
    )
    alerts = list(result.scalars().all())
    items = [await serialize_device_abuse_alert(session, alert) for alert in alerts]
    open_count = int(
        (
            await session.execute(
                select(func.count(VPNDeviceAbuseAlert.id)).where(
                    VPNDeviceAbuseAlert.status == VPNDeviceAbuseAlertStatus.OPEN
                )
            )
        ).scalar()
        or 0
    )
    resolved_count = int(
        (
            await session.execute(
                select(func.count(VPNDeviceAbuseAlert.id)).where(
                    VPNDeviceAbuseAlert.status == VPNDeviceAbuseAlertStatus.RESOLVED
                )
            )
        ).scalar()
        or 0
    )
    logger.info(
        "[M-081][list_device_abuse_alerts][ALERT_LIST] "
        f"returned={len(items)} total={total} open={open_count} resolved={resolved_count}"
    )
    return {
        "items": items,
        "total": total,
        "open_count": open_count,
        "resolved_count": resolved_count,
        "offset": safe_offset,
        "limit": safe_limit,
    }
# END_BLOCK_LIST_DEVICE_ABUSE_ALERTS


# START_CONTRACT: get_device_abuse_alert
#   PURPOSE: Return one VPN device abuse alert detail for admin review
#   INPUTS: session; alert_id
#   OUTPUTS: serialized alert dict | None
#   SIDE_EFFECTS: database read and ALERT_DETAIL marker
#   LINKS: M-081, V-M-081
# END_CONTRACT: get_device_abuse_alert
# START_BLOCK_GET_DEVICE_ABUSE_ALERT
async def get_device_abuse_alert(session: AsyncSession, alert_id: int) -> dict[str, Any] | None:
    """Return one serialized alert by id."""
    alert = await session.get(VPNDeviceAbuseAlert, alert_id)
    if alert is None:
        return None
    payload = await serialize_device_abuse_alert(session, alert)
    logger.info(
        "[M-081][get_device_abuse_alert][ALERT_DETAIL] "
        f"alert_id={alert_id} user_id={alert.user_id} device_id={alert.device_id}"
    )
    return payload
# END_BLOCK_GET_DEVICE_ABUSE_ALERT


# START_CONTRACT: resolve_device_abuse_alert
#   PURPOSE: Archive one alert without changing VPN device runtime state
#   INPUTS: session; alert_id; admin_id; action_taken; action_result
#   OUTPUTS: serialized alert dict | None
#   SIDE_EFFECTS: Updates alert review fields and logs ALERT_RESOLVED
#   LINKS: M-081, V-M-081
# END_CONTRACT: resolve_device_abuse_alert
# START_BLOCK_RESOLVE_DEVICE_ABUSE_ALERT
async def resolve_device_abuse_alert(
    session: AsyncSession,
    *,
    alert_id: int,
    admin_id: int,
    action_taken: str = "reviewed",
    action_result: str = "resolved_by_admin",
) -> dict[str, Any] | None:
    """Resolve one alert after operator review."""
    alert = await session.get(VPNDeviceAbuseAlert, alert_id)
    if alert is None:
        return None
    now = _utcnow()
    alert.status = VPNDeviceAbuseAlertStatus.RESOLVED
    alert.resolved_at = now
    alert.resolved_by_admin_id = admin_id
    alert.action_taken = action_taken[:80]
    alert.action_result = action_result[:160]
    alert.updated_at = now
    await session.flush()
    logger.info(
        "[M-081][resolve_device_abuse_alert][ALERT_RESOLVED] "
        f"alert_id={alert_id} admin_id={admin_id} action={alert.action_taken}"
    )
    return await serialize_device_abuse_alert(session, alert)
# END_BLOCK_RESOLVE_DEVICE_ABUSE_ALERT


# START_BLOCK_ADMIN_ALERT_ACTIONS
async def _get_open_alert_and_device(
    session: AsyncSession,
    alert_id: int,
) -> tuple[VPNDeviceAbuseAlert, UserDevice] | None:
    alert = await session.get(VPNDeviceAbuseAlert, alert_id)
    if alert is None:
        return None
    if _event_value(alert.status) != VPNDeviceAbuseAlertStatus.OPEN.value:
        raise ValueError("VPN device abuse alert is already resolved")
    device = await session.get(UserDevice, int(alert.device_id))
    if device is None:
        raise ValueError("Alert device not found")
    return alert, device


async def rotate_device_for_alert(
    session: AsyncSession,
    *,
    alert_id: int,
    admin_id: int,
    confirm: bool = False,
    policy: DeviceAccessPolicyService | None = None,
    vpn: VPNService | None = None,
) -> dict[str, Any] | None:
    """Rotate only the alert device config after explicit confirmation."""
    if not confirm:
        logger.warning(
            "[M-081][rotate_device_for_alert][CONFIRM_ROTATE_DEVICE] "
            f"alert_id={alert_id} confirmed=false"
        )
        raise ValueError("Explicit VPN device rotation confirmation required")
    loaded = await _get_open_alert_and_device(session, alert_id)
    if loaded is None:
        return None
    alert, device = loaded
    policy = policy or DeviceAccessPolicyService(session)
    vpn = vpn or VPNService(session)
    updated = await policy.rotate_device_config(device, reason=f"vpn_abuse_alert:{alert_id}:admin:{admin_id}")
    await vpn.provision_device_client(int(updated.user_id), int(updated.id), reprovision=True)
    payload = await resolve_device_abuse_alert(
        session,
        alert_id=alert_id,
        admin_id=admin_id,
        action_taken="rotate_device",
        action_result=f"device:{updated.id}:config_version:{updated.config_version}",
    )
    logger.info(
        "[M-081][rotate_device_for_alert][CONFIRM_ROTATE_DEVICE] "
        f"alert_id={alert_id} admin_id={admin_id} device_id={updated.id} confirmed=true"
    )
    return payload


async def block_device_for_alert(
    session: AsyncSession,
    *,
    alert_id: int,
    admin_id: int,
    confirm: bool = False,
    policy: DeviceAccessPolicyService | None = None,
) -> dict[str, Any] | None:
    """Block only the alert device after explicit confirmation."""
    if not confirm:
        logger.warning(
            "[M-081][block_device_for_alert][CONFIRM_BLOCK_DEVICE] "
            f"alert_id={alert_id} confirmed=false"
        )
        raise ValueError("Explicit VPN device block confirmation required")
    loaded = await _get_open_alert_and_device(session, alert_id)
    if loaded is None:
        return None
    alert, device = loaded
    policy = policy or DeviceAccessPolicyService(session)
    updated = await policy.block_device(device, reason=f"vpn_abuse_alert:{alert_id}:admin:{admin_id}")
    payload = await resolve_device_abuse_alert(
        session,
        alert_id=alert_id,
        admin_id=admin_id,
        action_taken="block_device",
        action_result=f"device:{updated.id}:status:{_event_value(updated.status)}",
    )
    logger.info(
        "[M-081][block_device_for_alert][CONFIRM_BLOCK_DEVICE] "
        f"alert_id={alert_id} admin_id={admin_id} device_id={updated.id} confirmed=true"
    )
    return payload
# END_BLOCK_ADMIN_ALERT_ACTIONS
