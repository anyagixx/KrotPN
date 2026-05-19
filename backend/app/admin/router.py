# FILE: backend/app/admin/router.py
# VERSION: 3.5.0
# ROLE: ENTRY_POINT
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: Expose privileged admin analytics, system endpoints, and operator recovery controls over current backend state
#   SCOPE: Dashboard statistics, revenue analytics, user analytics, system health, device control, MTProto assignment operations, usage analytics, and promotion tag control
#   DEPENDS: M-001 (core database/auth), M-002 (user models), M-003 (vpn topology), M-004 (billing), M-005 (referrals), M-006 (admin-api graph surface), M-016 (route-policy observability), M-042/M-043/M-044 (MTProto assignment/provisioning/runtime bridge), M-056/M-057/M-059 (MTProto analytics/tag control)
#   LINKS: M-006 (admin-api), M-016 (route-decision-api), M-047 (mtproto-admin-ops), M-044, M-056, M-057, M-059, V-M-006, V-M-047, V-M-044, V-M-057, V-M-059
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   get_admin_stats - Aggregates dashboard metrics across users, subscriptions, revenue, VPN, and routing
#   get_revenue_analytics - Grouped payment revenue analytics over a bounded date range
#   get_users_analytics - Grouped user registration analytics over a bounded date range
#   list_admin_devices - Device registry rows with live slot/security context and recent anti-abuse events
#   block_admin_device - Block one device peer without freeing the consumed slot
#   unblock_admin_device - Clear the blocked state for one device
#   rotate_admin_device - Reprovision one device config keeping logical device identity
#   revoke_admin_device - Revoke one device and free the slot
#   list_admin_mtproto_assignments - Redacted MTProto assignment list with search/status/time filters
#   get_admin_mtproto_assignment - Redacted MTProto assignment detail
#   get_admin_mtproto_health - Secret-free KPprotoN runtime bridge health summary
#   get_admin_mtproto_analytics_summary - Secret-free global MTProto usage analytics
#   get_admin_mtproto_assignment_usage - Per-assignment MTProto usage drill-down
#   list_admin_mtproto_events - Paginated MTProto usage event list
#   list_admin_mtproto_top_users - Top users by traffic, duration, connections, or errors
#   list_admin_mtproto_abuse_signals - Observe-only MTProto abuse signals
#   get_admin_mtproto_promotion_tag - Masked promotion tag state
#   update_admin_mtproto_promotion_tag - Explicit audited promotion tag update
#   reissue_admin_mtproto_assignment - Explicit audited MTProto reissue without admin secret disclosure
#   revoke_admin_mtproto_assignment - Explicit audited MTProto assignment disable without VPN/account side effects
#   get_system_health - Coarse host health metrics for privileged operators
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v3.5.0 - Added Phase-42 MTProto analytics and promotion tag admin APIs.
#   LAST_CHANGE: v3.4.0 - Restored MTProto admin runtime actions to the KPprotoN policy bridge.
#   LAST_CHANGE: v3.3.0 - Switched MTProto admin runtime actions to official MTProxy manifest sync.
#   LAST_CHANGE: v3.2.1 - MTProto revoke now removes the runtime SNI policy and returns a safe revoke result
#   LAST_CHANGE: v3.2.0 - Added Phase-33 MTProto admin list/detail/health/reissue/revoke with redacted audit payloads
#   LAST_CHANGE: v3.1.0 - Added recent anti-abuse event context to admin device payloads
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT, MODULE_MAP, BLOCKS per GRACE governance protocol; replaced docstring header with comment-based GRACE header
# END_CHANGE_SUMMARY
#
# <!-- GRACE: module="M-006" api-group="Admin API" -->

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlmodel import col

from app.core import CurrentAdmin, CurrentSuperuser, DBSession
from app.admin.audit import log_admin_action
from app.billing.models import Payment, PaymentStatus, Plan, Subscription
from app.devices.models import DeviceSecurityEvent, DeviceSecurityEventType, UserDevice
from app.devices.service import DeviceAccessPolicyService
from app.mtproto.health import build_runtime_health_summary
from app.mtproto.analytics_service import MTProtoAnalyticsService
from app.mtproto.models import MTProtoAssignment, MTProtoAssignmentStatus
from app.mtproto.promotion_tag import (
    MTProtoPromotionTagError,
    get_promotion_tag_state,
    safe_promotion_tag_state,
    update_promotion_tag,
)
from app.mtproto.provisioning import (
    MTProtoProvisioningError,
    MTProtoProvisioningErrorCode,
    MTProtoProvisioningService,
)
from app.mtproto.runtime_bridge import MTProtoRuntimeBridge
from app.mtproto.usage_models import MTProtoUsageEventType
from app.referrals.models import Referral, ReferralCode
# NOTE: routing models/observer removed in Phase-17 (Full Tunnel)
from app.users.models import User, UserRole
from app.vpn.models import VPNClient, VPNNode, VPNRoute, VPNServer
from app.vpn.service import VPNService

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

ANTI_ABUSE_EVENT_TYPES = {
    DeviceSecurityEventType.PING_PONG_ABUSE_DETECTED,
    DeviceSecurityEventType.MULTI_NETWORK_ABUSE_DETECTED,
    DeviceSecurityEventType.ANTI_ABUSE_AUTO_ROTATE_STARTED,
    DeviceSecurityEventType.ANTI_ABUSE_AUTO_ROTATE_COMPLETED,
    DeviceSecurityEventType.ANTI_ABUSE_COOLDOWN_SKIPPED,
    DeviceSecurityEventType.ANTI_ABUSE_REDIS_DEGRADED,
}

MTPROTO_ADMIN_FORBIDDEN_MARKERS = (
    "tg://proxy",
    "https://t.me/proxy",
    "secret=",
    "MTPROTO_BASE_SECRET_HEX",
    "MTPROTO_SECRET_SALT",
    "MTPROTO_RUNTIME_TOKEN",
    "x-krotpn-mtproto-token",
)


class MTProtoAdminActionRequest(BaseModel):
    """Confirmation body for destructive MTProto admin actions."""

    confirm: bool = False


class MTProtoPromotionTagUpdateRequest(BaseModel):
    """Confirmation body for promotion tag updates."""

    tag: str | None = None
    confirm: bool = False


# START_BLOCK: _serialize_admin_device
async def _serialize_admin_device(
    session: DBSession,
    *,
    device: UserDevice,
    user: User,
) -> dict:
    """Project one device plus current peer context into the admin response shape."""
    active_peer_count = (
        await session.execute(
            select(func.count(VPNClient.id)).where(
                VPNClient.device_id == device.id,
                VPNClient.is_active == True,
            )
        )
    ).scalar() or 0

    recent_events_result = await session.execute(
        select(DeviceSecurityEvent.event_type)
        .where(DeviceSecurityEvent.device_id == device.id)
        .order_by(DeviceSecurityEvent.created_at.desc())
        .limit(3)
    )
    recent_event_types = [event.value for event in recent_events_result.scalars().all()]
    recent_anti_abuse_events_result = await session.execute(
        select(DeviceSecurityEvent.event_type)
        .where(
            DeviceSecurityEvent.device_id == device.id,
            DeviceSecurityEvent.event_type.in_(ANTI_ABUSE_EVENT_TYPES),
        )
        .order_by(DeviceSecurityEvent.created_at.desc())
        .limit(5)
    )
    recent_anti_abuse_event_types = [
        event.value for event in recent_anti_abuse_events_result.scalars().all()
    ]

    return {
        "id": device.id,
        "user_id": device.user_id,
        "user_email": user.email,
        "user_display_name": user.display_name,
        "name": device.name,
        "platform": device.platform,
        "status": device.status.value,
        "config_version": device.config_version,
        "block_reason": device.block_reason,
        "created_at": device.created_at,
        "updated_at": device.updated_at,
        "revoked_at": device.revoked_at,
        "blocked_at": device.blocked_at,
        "last_seen_at": device.last_seen_at,
        "last_handshake_at": device.last_handshake_at,
        "last_endpoint": device.last_endpoint,
        "active_peer_count": int(active_peer_count),
        "recent_event_types": recent_event_types,
        "recent_anti_abuse_event_types": recent_anti_abuse_event_types,
    }
# END_BLOCK: _serialize_admin_device


# START_BLOCK: _list_admin_devices
async def _list_admin_devices(
    session: DBSession,
    *,
    search: str = "",
) -> list[dict]:
    """Return device rows plus user context for the admin table."""
    query = (
        select(UserDevice, User)
        .join(User, User.id == UserDevice.user_id)
        .order_by(UserDevice.created_at.desc(), UserDevice.id.desc())
    )
    if search.strip():
        needle = f"%{search.strip().lower()}%"
        query = query.where(
            func.lower(func.coalesce(User.email, "")).like(needle)
            | func.lower(func.coalesce(User.name, "")).like(needle)
            | func.lower(UserDevice.name).like(needle)
            | func.lower(func.coalesce(UserDevice.platform, "")).like(needle)
        )

    result = await session.execute(query)
    items: list[dict] = []
    for device, user in result.all():
        items.append(await _serialize_admin_device(session, device=device, user=user))
    return items
# END_BLOCK: _list_admin_devices


async def _get_admin_device_or_none(session: DBSession, device_id: int) -> UserDevice | None:
    """Load one device row for admin mutation endpoints."""
    return await session.get(UserDevice, device_id)


# START_CONTRACT: _serialize_mtproto_admin_assignment
#   PURPOSE: Project one MTProto assignment into an admin-safe response shape
#   INPUTS: assignment: MTProtoAssignment; user: User
#   OUTPUTS: dict
#   SIDE_EFFECTS: raises 500 if secret-bearing fields appear in the response
#   LINKS: M-047, V-M-047
# END_CONTRACT: _serialize_mtproto_admin_assignment
# START_BLOCK: _serialize_mtproto_admin_assignment
def _serialize_mtproto_admin_assignment(
    *,
    assignment: MTProtoAssignment,
    user: User,
) -> dict:
    """Return MTProto assignment data that is useful to admins and safe to log."""
    payload = {
        "id": assignment.id,
        "assignment_id": assignment.id,
        "user_id": assignment.user_id,
        "user_email": user.email,
        "user_display_name": user.display_name,
        "sni": assignment.sni,
        "credential_mode": assignment.credential_mode.value,
        "status": assignment.status.value,
        "rotation_marker": assignment.rotation_marker,
        "reissue_required": assignment.status == MTProtoAssignmentStatus.REISSUE_REQUIRED,
        "issued_at": assignment.issued_at,
        "created_at": assignment.created_at,
        "updated_at": assignment.updated_at,
        "superseded_at": assignment.superseded_at,
    }
    _assert_mtproto_admin_payload_redacted(payload)
    return payload
# END_BLOCK: _serialize_mtproto_admin_assignment


# START_BLOCK: _mtproto_admin_helpers
def _assert_mtproto_admin_payload_redacted(payload: dict | list[dict]) -> None:
    """Fail closed if a future schema change accidentally includes owner secrets."""
    payload_text = str(payload)
    leaked_marker = next(
        (marker for marker in MTPROTO_ADMIN_FORBIDDEN_MARKERS if marker in payload_text),
        None,
    )
    if leaked_marker:
        logger.error("[M-047][admin_list_mtproto][REDACT_PAYLOAD] leaked_marker=blocked")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MTProto admin payload redaction failed",
        )


def _parse_mtproto_status_filter(value: str | None) -> MTProtoAssignmentStatus | None:
    if not value:
        return None
    try:
        return MTProtoAssignmentStatus(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MTProto assignment status",
        ) from exc


def _parse_mtproto_event_type_filter(value: str | None) -> MTProtoUsageEventType | None:
    if not value:
        return None
    try:
        return MTProtoUsageEventType(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MTProto usage event type",
        ) from exc


def _parse_mtproto_top_user_metric(value: str) -> str:
    if value not in {"traffic", "duration", "connections", "errors"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MTProto top-user metric",
        )
    return value


def _safe_mtproto_audit_details(
    *,
    action: str,
    assignment: MTProtoAssignment,
    result_status: str,
    failure_code: str | None = None,
) -> str:
    """Build a compact audit payload without request bodies or credentials."""
    details = json.dumps(
        {
            "action": action,
            "assignment_id": assignment.id,
            "user_id": assignment.user_id,
            "result_status": result_status,
            "failure_code": failure_code,
            "rotation_marker": assignment.rotation_marker,
        },
        sort_keys=True,
    )
    _assert_mtproto_admin_payload_redacted({"details": details})
    return details


async def _get_mtproto_assignment_and_user(
    session: DBSession,
    assignment_id: int,
) -> tuple[MTProtoAssignment, User]:
    result = await session.execute(
        select(MTProtoAssignment, User)
        .join(User, User.id == MTProtoAssignment.user_id)
        .where(MTProtoAssignment.id == assignment_id)
    )
    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MTProto assignment not found",
        )
    assignment, user = row
    return assignment, user
# END_BLOCK: _mtproto_admin_helpers


# START_CONTRACT: _list_mtproto_admin_assignments
#   PURPOSE: Return filtered MTProto assignment rows with user context and no secrets
#   INPUTS: search, status_filter, created_from, created_to, offset, limit
#   OUTPUTS: dict with items and total
#   SIDE_EFFECTS: database read and redaction log markers
#   LINKS: M-047, M-042, V-M-047
# END_CONTRACT: _list_mtproto_admin_assignments
# START_BLOCK: _list_mtproto_admin_assignments
async def _list_mtproto_admin_assignments(
    session: DBSession,
    *,
    search: str = "",
    status_filter: MTProtoAssignmentStatus | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    offset: int = 0,
    limit: int = 100,
) -> dict:
    """Return redacted MTProto assignment rows for operator triage."""
    conditions = []
    search_value = search.strip()
    if search_value:
        needle = f"%{search_value.lower()}%"
        clauses = [
            func.lower(func.coalesce(User.email, "")).like(needle),
            func.lower(func.coalesce(User.name, "")).like(needle),
            func.lower(MTProtoAssignment.sni).like(needle),
        ]
        if search_value.isdigit():
            numeric_value = int(search_value)
            clauses.extend(
                [
                    MTProtoAssignment.id == numeric_value,
                    MTProtoAssignment.user_id == numeric_value,
                ]
            )
        conditions.append(or_(*clauses))

    if status_filter is not None:
        conditions.append(MTProtoAssignment.status == status_filter)
    if created_from is not None:
        conditions.append(MTProtoAssignment.created_at >= created_from)
    if created_to is not None:
        conditions.append(MTProtoAssignment.created_at <= created_to)

    safe_offset = max(offset, 0)
    safe_limit = min(max(limit, 1), 500)
    logger.info(
        "[M-047][admin_list_mtproto][FILTER_ASSIGNMENTS] "
        f"search={bool(search_value)} status={status_filter.value if status_filter else 'all'} "
        f"offset={safe_offset} limit={safe_limit}"
    )

    count_query = (
        select(func.count(MTProtoAssignment.id))
        .join(User, User.id == MTProtoAssignment.user_id)
        .where(*conditions)
    )
    total = int((await session.execute(count_query)).scalar() or 0)

    query = (
        select(MTProtoAssignment, User)
        .join(User, User.id == MTProtoAssignment.user_id)
        .where(*conditions)
        .order_by(MTProtoAssignment.created_at.desc(), MTProtoAssignment.id.desc())
        .offset(safe_offset)
        .limit(safe_limit)
    )
    result = await session.execute(query)
    items = [
        _serialize_mtproto_admin_assignment(assignment=assignment, user=user)
        for assignment, user in result.all()
    ]
    payload = {"items": items, "total": total, "offset": safe_offset, "limit": safe_limit}
    _assert_mtproto_admin_payload_redacted(payload)
    logger.info(
        "[M-047][admin_list_mtproto][REDACT_PAYLOAD] "
        f"returned={len(items)} total={total}"
    )
    return payload
# END_BLOCK: _list_mtproto_admin_assignments


# ==================== Dashboard Stats ====================

# START_BLOCK: get_admin_stats
@router.get("/stats")
async def get_admin_stats(
    admin: CurrentAdmin,
    session: DBSession,
):
    """Get admin dashboard statistics."""
    # Keep in mind that `online_servers` still counts legacy `VPNServer` rows,
    # so this endpoint is not yet a perfect reflection of the newer node/route topology.
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Users count
    total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
    new_users_month = (await session.execute(
        select(func.count(User.id)).where(User.created_at >= month_start)
    )).scalar() or 0

    # Active subscriptions
    active_subs = (await session.execute(
        select(func.count(Subscription.id)).where(
            Subscription.is_active == True,
            Subscription.expires_at > now,
        )
    )).scalar() or 0

    # Trial subscriptions
    trial_subs = (await session.execute(
        select(func.count(Subscription.id)).where(
            Subscription.is_trial == True,
            Subscription.is_active == True,
            Subscription.expires_at > now,
        )
    )).scalar() or 0

    # Revenue this month
    revenue_month = (await session.execute(
        select(func.sum(Payment.amount)).where(
            Payment.status == PaymentStatus.SUCCEEDED,
            Payment.paid_at >= month_start,
        )
    )).scalar() or 0

    # Total revenue
    total_revenue = (await session.execute(
        select(func.sum(Payment.amount)).where(
            Payment.status == PaymentStatus.SUCCEEDED,
        )
    )).scalar() or 0

    # VPN clients
    active_vpn_clients = (await session.execute(
        select(func.count(VPNClient.id)).where(VPNClient.is_active == True)
    )).scalar() or 0

    # Servers
    online_servers = (await session.execute(
        select(func.count(VPNServer.id)).where(VPNServer.is_online == True)
    )).scalar() or 0

    # Route-aware topology summary
    active_nodes = (await session.execute(
        select(func.count(VPNNode.id)).where(VPNNode.is_active == True)
    )).scalar() or 0
    online_nodes = (await session.execute(
        select(func.count(VPNNode.id)).where(
            VPNNode.is_active == True,
            VPNNode.is_online == True,
        )
    )).scalar() or 0
    active_routes = (await session.execute(
        select(func.count(VPNRoute.id)).where(VPNRoute.is_active == True)
    )).scalar() or 0
    default_routes = (await session.execute(
        select(func.count(VPNRoute.id)).where(
            VPNRoute.is_active == True,
            VPNRoute.is_default == True,
        )
    )).scalar() or 0
    # NOTE: routing policy stats removed in Phase-17 (Full Tunnel)
    # active_domain_rules, active_cidr_rules, active_dns_bindings no longer applicable

    return {
        "users": {
            "total": total_users,
            "new_this_month": new_users_month,
        },
        "subscriptions": {
            "active": active_subs,
            "trial": trial_subs,
        },
        "revenue": {
            "this_month": revenue_month,
            "total": total_revenue,
        },
        "vpn": {
            "active_clients": active_vpn_clients,
            "online_servers": online_servers,
            "online_servers_source": "legacy_vpn_server",
            "topology_note": "Legacy VPNServer mirror count; use routing summary for policy-driven topology.",
        },
        "routing": {
            "online_nodes": online_nodes,
            "active_nodes": active_nodes,
            "active_routes": active_routes,
            "default_routes": default_routes,
            "mode": "full_tunnel",
            "note": "Split-tunneling removed in Phase-17. All traffic via DE server.",
        },
    }
# END_BLOCK: get_admin_stats


# START_BLOCK: get_revenue_analytics
@router.get("/analytics/revenue")
async def get_revenue_analytics(
    admin: CurrentAdmin,
    session: DBSession,
    days: int = Query(default=30, ge=1, le=365),
):
    """Get revenue analytics for the last N days."""
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)

    # Daily revenue
    result = await session.execute(
        select(
            func.date(Payment.paid_at).label("date"),
            func.sum(Payment.amount).label("revenue"),
            func.count(Payment.id).label("payments"),
        )
        .where(
            Payment.status == PaymentStatus.SUCCEEDED,
            Payment.paid_at >= start_date,
        )
        .group_by(func.date(Payment.paid_at))
        .order_by(func.date(Payment.paid_at))
    )

    daily_data = [
        {
            "date": str(row.date),
            "revenue": float(row.revenue or 0),
            "payments": row.payments,
        }
        for row in result.all()
    ]

    return {
        "period_days": days,
        "daily": daily_data,
    }
# END_BLOCK: get_revenue_analytics


# START_BLOCK: get_users_analytics
@router.get("/analytics/users")
async def get_users_analytics(
    admin: CurrentAdmin,
    session: DBSession,
    days: int = Query(default=30, ge=1, le=365),
):
    """Get user registration analytics."""
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)

    # Daily registrations
    result = await session.execute(
        select(
            func.date(User.created_at).label("date"),
            func.count(User.id).label("count"),
        )
        .where(User.created_at >= start_date)
        .group_by(func.date(User.created_at))
        .order_by(func.date(User.created_at))
    )

    daily_data = [
        {
            "date": str(row.date),
            "count": row.count,
        }
        for row in result.all()
    ]

    return {
        "period_days": days,
        "daily": daily_data,
    }
# END_BLOCK: get_users_analytics


@router.get("/devices")
async def list_admin_devices(
    admin: CurrentAdmin,
    session: DBSession,
    search: str = Query(default=""),
):
    """Return user devices with recent security context for admin review."""
    items = await _list_admin_devices(session, search=search)
    return {
        "items": items,
        "total": len(items),
    }


# START_BLOCK: block_admin_device
@router.post("/devices/{device_id}/block")
async def block_admin_device(
    device_id: int,
    admin: CurrentAdmin,
    session: DBSession,
):
    """Block one device peer while preserving slot consumption."""
    policy = DeviceAccessPolicyService(session)
    device = await _get_admin_device_or_none(session, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    updated = await policy.block_device(device, reason=f"admin:{admin.id}")
    user = await session.get(User, updated.user_id)
    return await _serialize_admin_device(session, device=updated, user=user)
# END_BLOCK: block_admin_device


# START_BLOCK: unblock_admin_device
@router.post("/devices/{device_id}/unblock")
async def unblock_admin_device(
    device_id: int,
    admin: CurrentAdmin,
    session: DBSession,
):
    """Unblock one device without silently restoring the old peer."""
    policy = DeviceAccessPolicyService(session)
    device = await _get_admin_device_or_none(session, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    updated = await policy.unblock_device(device, reason=f"admin:{admin.id}")
    user = await session.get(User, updated.user_id)
    return await _serialize_admin_device(session, device=updated, user=user)
# END_BLOCK: unblock_admin_device


# START_BLOCK: rotate_admin_device
@router.post("/devices/{device_id}/rotate")
async def rotate_admin_device(
    device_id: int,
    admin: CurrentAdmin,
    session: DBSession,
):
    """Rotate one device config and reprovision its peer."""
    policy = DeviceAccessPolicyService(session)
    vpn = VPNService(session)
    device = await _get_admin_device_or_none(session, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    updated = await policy.rotate_device_config(device, reason=f"admin:{admin.id}")
    await vpn.provision_device_client(int(updated.user_id), int(updated.id), reprovision=True)
    user = await session.get(User, updated.user_id)
    return await _serialize_admin_device(session, device=updated, user=user)
# END_BLOCK: rotate_admin_device


# START_BLOCK: revoke_admin_device
@router.delete("/devices/{device_id}")
async def revoke_admin_device(
    device_id: int,
    admin: CurrentAdmin,
    session: DBSession,
):
    """Revoke one device and free its slot."""
    policy = DeviceAccessPolicyService(session)
    device = await _get_admin_device_or_none(session, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    updated = await policy.revoke_device(device, reason=f"admin:{admin.id}")
    user = await session.get(User, updated.user_id)
    return await _serialize_admin_device(session, device=updated, user=user)
# END_BLOCK: revoke_admin_device


# ==================== MTProto Admin Ops ====================

# START_BLOCK: list_admin_mtproto_assignments
@router.get("/mtproto/assignments")
async def list_admin_mtproto_assignments(
    admin: CurrentAdmin,
    session: DBSession,
    search: str = Query(default=""),
    assignment_status: str | None = Query(default=None, alias="status"),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    """Return redacted MTProto assignment rows for admin operators."""
    status_filter = _parse_mtproto_status_filter(assignment_status)
    return await _list_mtproto_admin_assignments(
        session,
        search=search,
        status_filter=status_filter,
        created_from=created_from,
        created_to=created_to,
        offset=offset,
        limit=limit,
    )
# END_BLOCK: list_admin_mtproto_assignments


# START_BLOCK: get_admin_mtproto_assignment
@router.get("/mtproto/assignments/{assignment_id}")
async def get_admin_mtproto_assignment(
    assignment_id: int,
    admin: CurrentAdmin,
    session: DBSession,
):
    """Return one redacted MTProto assignment detail."""
    assignment, user = await _get_mtproto_assignment_and_user(session, assignment_id)
    logger.info(
        "[M-047][admin_get_mtproto][SAFE_DETAIL] "
        f"assignment_id={assignment.id} user_id={assignment.user_id}"
    )
    return _serialize_mtproto_admin_assignment(assignment=assignment, user=user)
# END_BLOCK: get_admin_mtproto_assignment


# START_BLOCK: get_admin_mtproto_health
@router.get("/mtproto/health")
async def get_admin_mtproto_health(
    admin: CurrentAdmin,
    session: DBSession,
):
    """Return secret-free MTProto runtime bridge health."""
    health = await MTProtoRuntimeBridge(session).runtime_health()
    payload = build_runtime_health_summary(health)
    _assert_mtproto_admin_payload_redacted(payload)
    logger.info(
        "[M-047][admin_mtproto_health][RUNTIME_HEALTH] "
        f"status={payload.get('status')} failure_code={payload.get('last_failure_code')}"
    )
    return payload
# END_BLOCK: get_admin_mtproto_health


# START_BLOCK: get_admin_mtproto_analytics_summary
@router.get("/mtproto/analytics/summary")
async def get_admin_mtproto_analytics_summary(
    admin: CurrentAdmin,
    session: DBSession,
    days: int = Query(default=30, ge=1, le=365),
):
    """Return secret-free global MTProto usage analytics."""
    runtime_health = build_runtime_health_summary(await MTProtoRuntimeBridge(session).runtime_health())
    payload = await MTProtoAnalyticsService(session).build_global_summary(
        window_days=days,
        runtime_health=runtime_health,
    )
    _assert_mtproto_admin_payload_redacted(payload)
    logger.info(
        "[M-057][admin_mtproto_analytics][SUMMARY] "
        f"days={days} issued={payload.get('issued_total')}"
    )
    return payload
# END_BLOCK: get_admin_mtproto_analytics_summary


# START_BLOCK: get_admin_mtproto_assignment_usage
@router.get("/mtproto/assignments/{assignment_id}/usage")
async def get_admin_mtproto_assignment_usage(
    assignment_id: int,
    admin: CurrentAdmin,
    session: DBSession,
    days: int = Query(default=30, ge=1, le=365),
):
    """Return one MTProto assignment's usage drill-down."""
    payload = await MTProtoAnalyticsService(session).build_assignment_usage(
        assignment_id=assignment_id,
        window_days=days,
    )
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MTProto assignment not found",
        )
    _assert_mtproto_admin_payload_redacted(payload)
    logger.info(
        "[M-057][admin_mtproto_usage][ASSIGNMENT_DETAIL] "
        f"assignment_id={assignment_id} days={days}"
    )
    return payload
# END_BLOCK: get_admin_mtproto_assignment_usage


# START_BLOCK: list_admin_mtproto_events
@router.get("/mtproto/analytics/events")
async def list_admin_mtproto_events(
    admin: CurrentAdmin,
    session: DBSession,
    assignment_id: int | None = Query(default=None),
    event_type: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    """Return paginated secret-free MTProto usage events."""
    payload = await MTProtoAnalyticsService(session).list_events(
        assignment_id=assignment_id,
        event_type=_parse_mtproto_event_type_filter(event_type),
        window_days=days,
        offset=offset,
        limit=limit,
    )
    _assert_mtproto_admin_payload_redacted(payload)
    logger.info(
        "[M-057][admin_mtproto_events][EVENT_LIST] "
        f"assignment_id={assignment_id} event_type={event_type or 'all'} returned={len(payload.get('items', []))}"
    )
    return payload
# END_BLOCK: list_admin_mtproto_events


# START_BLOCK: list_admin_mtproto_top_users
@router.get("/mtproto/analytics/top-users")
async def list_admin_mtproto_top_users(
    admin: CurrentAdmin,
    session: DBSession,
    metric: str = Query(default="traffic"),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=100),
):
    """Return top MTProto users by selected metadata-only metric."""
    safe_metric = _parse_mtproto_top_user_metric(metric)
    items = await MTProtoAnalyticsService(session).build_top_users(
        metric=safe_metric,
        window_days=days,
        limit=limit,
    )
    payload = {"items": items, "metric": safe_metric, "days": days, "limit": limit}
    _assert_mtproto_admin_payload_redacted(payload)
    logger.info(
        "[M-057][admin_mtproto_top_users][TOP_USERS] "
        f"metric={safe_metric} returned={len(items)}"
    )
    return payload
# END_BLOCK: list_admin_mtproto_top_users


# START_BLOCK: list_admin_mtproto_abuse_signals
@router.get("/mtproto/analytics/abuse-signals")
async def list_admin_mtproto_abuse_signals(
    admin: CurrentAdmin,
    session: DBSession,
    assignment_id: int | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    """Return observe-only MTProto abuse signals."""
    payload = await MTProtoAnalyticsService(session).list_abuse_signals(
        assignment_id=assignment_id,
        window_days=days,
        offset=offset,
        limit=limit,
    )
    _assert_mtproto_admin_payload_redacted(payload)
    return payload
# END_BLOCK: list_admin_mtproto_abuse_signals


# START_BLOCK: get_admin_mtproto_promotion_tag
@router.get("/mtproto/promotion-tag")
async def get_admin_mtproto_promotion_tag(
    admin: CurrentAdmin,
    session: DBSession,
):
    """Return masked MTProxy promotion tag state."""
    row = await get_promotion_tag_state(session)
    payload = safe_promotion_tag_state(row)
    _assert_mtproto_admin_payload_redacted(payload)
    return payload
# END_BLOCK: get_admin_mtproto_promotion_tag


# START_BLOCK: update_admin_mtproto_promotion_tag
@router.put("/mtproto/promotion-tag")
async def update_admin_mtproto_promotion_tag(
    admin: CurrentAdmin,
    session: DBSession,
    request: MTProtoPromotionTagUpdateRequest,
):
    """Update MTProxy promotion tag after explicit admin confirmation."""
    try:
        row = await update_promotion_tag(
            session,
            admin_id=int(admin.id),
            tag_value=request.tag,
            confirm=request.confirm,
        )
    except MTProtoPromotionTagError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    payload = safe_promotion_tag_state(row)
    _assert_mtproto_admin_payload_redacted(payload)
    await log_admin_action(
        session,
        int(admin.id),
        "mtproto.promotion_tag.update",
        resource_type="mtproto_promotion_tag",
        resource_id=1,
        details=json.dumps(
            {
                "action": "promotion_tag.update",
                "masked_tag": payload["masked_tag"],
                "runtime_status": payload["runtime_status"],
                "pending_restart": payload["pending_restart"],
            },
            sort_keys=True,
        ),
    )
    logger.info(
        "[M-059][update_promotion_tag][AUDIT_UPDATE] "
        f"admin_id={admin.id} status={payload.get('runtime_status')}"
    )
    return payload
# END_BLOCK: update_admin_mtproto_promotion_tag


# START_BLOCK: reissue_admin_mtproto_assignment
@router.post("/mtproto/assignments/{assignment_id}/reissue")
async def reissue_admin_mtproto_assignment(
    assignment_id: int,
    admin: CurrentAdmin,
    session: DBSession,
    request: MTProtoAdminActionRequest | None = None,
):
    """Reissue one assignment after explicit confirmation without returning credentials."""
    if request is None or not request.confirm:
        logger.warning(
            "[M-047][admin_reissue_mtproto][CONFIRM_REISSUE] "
            f"assignment_id={assignment_id} confirmed=false"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit MTProto reissue confirmation required",
        )

    assignment, user = await _get_mtproto_assignment_and_user(session, assignment_id)
    logger.info(
        "[M-047][admin_reissue_mtproto][CONFIRM_REISSUE] "
        f"assignment_id={assignment.id} user_id={assignment.user_id} confirmed=true"
    )
    service = MTProtoProvisioningService(session)
    try:
        await service.issue_user_proxy(user, reissue=True)
    except MTProtoProvisioningError as exc:
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if exc.code == MTProtoProvisioningErrorCode.CONFIG_INCOMPLETE
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=status_code, detail=exc.safe_message) from exc

    await session.flush()
    await session.refresh(assignment)
    apply_result = await MTProtoRuntimeBridge(session).apply_domain_policy(assignment)
    await log_admin_action(
        session,
        int(admin.id),
        "mtproto.reissue",
        resource_type="mtproto_assignment",
        resource_id=int(assignment.id),
        details=_safe_mtproto_audit_details(
            action="reissue",
            assignment=assignment,
            result_status=apply_result.status.value,
            failure_code=apply_result.failure_code.value if apply_result.failure_code else None,
        ),
    )
    logger.info(
        "[M-047][admin_reissue_mtproto][AUDIT_REISSUE] "
        f"assignment_id={assignment.id} user_id={assignment.user_id} status={apply_result.status.value}"
    )
    payload = {
        "assignment": _serialize_mtproto_admin_assignment(assignment=assignment, user=user),
        "runtime_apply": apply_result.to_safe_dict(),
    }
    _assert_mtproto_admin_payload_redacted(payload)
    return payload
# END_BLOCK: reissue_admin_mtproto_assignment


# START_BLOCK: revoke_admin_mtproto_assignment
@router.post("/mtproto/assignments/{assignment_id}/revoke")
async def revoke_admin_mtproto_assignment(
    assignment_id: int,
    admin: CurrentAdmin,
    session: DBSession,
    request: MTProtoAdminActionRequest | None = None,
):
    """Disable one MTProto assignment without touching the user's VPN account state."""
    if request is None or not request.confirm:
        logger.warning(
            "[M-047][admin_revoke_mtproto][CONFIRM_REVOKE] "
            f"assignment_id={assignment_id} confirmed=false"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit MTProto revoke confirmation required",
        )

    assignment, user = await _get_mtproto_assignment_and_user(session, assignment_id)
    logger.info(
        "[M-047][admin_revoke_mtproto][CONFIRM_REVOKE] "
        f"assignment_id={assignment.id} user_id={assignment.user_id} confirmed=true"
    )
    now = datetime.now(timezone.utc)
    assignment.status = MTProtoAssignmentStatus.DISABLED
    assignment.updated_at = now
    assignment.superseded_at = now
    await session.flush()
    await session.refresh(assignment)
    revoke_result = await MTProtoRuntimeBridge(session).revoke_domain_policy(assignment)
    await log_admin_action(
        session,
        int(admin.id),
        "mtproto.revoke",
        resource_type="mtproto_assignment",
        resource_id=int(assignment.id),
        details=_safe_mtproto_audit_details(
            action="revoke",
            assignment=assignment,
            result_status=revoke_result.status.value,
            failure_code=revoke_result.failure_code.value if revoke_result.failure_code else None,
        ),
    )
    logger.info(
        "[M-047][admin_revoke_mtproto][AUDIT_REVOKE] "
        f"assignment_id={assignment.id} user_id={assignment.user_id} "
        f"status={assignment.status.value} runtime_status={revoke_result.status.value}"
    )
    payload = {
        "assignment": _serialize_mtproto_admin_assignment(assignment=assignment, user=user),
        "runtime_revoke": revoke_result.to_safe_dict(),
        "revoked": True,
    }
    _assert_mtproto_admin_payload_redacted(payload)
    return payload
# END_BLOCK: revoke_admin_mtproto_assignment


# ==================== System ====================

# START_BLOCK: get_system_health
@router.get("/system/health")
async def get_system_health(
    admin: CurrentAdmin,
    session: DBSession,
):
    """Get system health status."""
    import psutil

    cpu_percent = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    return {
        "cpu_percent": cpu_percent,
        "memory": {
            "total": mem.total,
            "used": mem.used,
            "percent": mem.percent,
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "percent": disk.percent,
        },
    }
# END_BLOCK: get_system_health
