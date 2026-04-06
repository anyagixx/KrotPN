# FILE: backend/app/admin/router.py
# VERSION: 1.0.0
# ROLE: ENTRY_POINT
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: Expose privileged admin analytics and system endpoints over current backend state
#   SCOPE: Dashboard statistics, revenue analytics, user analytics, system health, device control (block/unblock/rotate/revoke)
#   DEPENDS: M-001 (core database/auth), M-002 (user models), M-003 (vpn topology), M-004 (billing), M-005 (referrals), M-006 (admin-api graph surface), M-016 (route-policy observability)
#   LINKS: M-006 (admin-api), M-016 (route-decision-api), V-M-006
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   get_admin_stats - Aggregates dashboard metrics across users, subscriptions, revenue, VPN, and routing
#   get_revenue_analytics - Grouped payment revenue analytics over a bounded date range
#   get_users_analytics - Grouped user registration analytics over a bounded date range
#   list_admin_devices - Device registry rows with live slot/security context
#   block_admin_device - Block one device peer without freeing the consumed slot
#   unblock_admin_device - Clear the blocked state for one device
#   rotate_admin_device - Reprovision one device config keeping logical device identity
#   revoke_admin_device - Revoke one device and free the slot
#   get_system_health - Coarse host health metrics for privileged operators
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT, MODULE_MAP, BLOCKS per GRACE governance protocol; replaced docstring header with comment-based GRACE header
# END_CHANGE_SUMMARY
#
# <!-- GRACE: module="M-006" api-group="Admin API" -->

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlmodel import col

from app.core import CurrentAdmin, CurrentSuperuser, DBSession
from app.billing.models import Payment, PaymentStatus, Plan, Subscription
from app.devices.models import DeviceSecurityEvent, UserDevice
from app.devices.service import DeviceAccessPolicyService
from app.referrals.models import Referral, ReferralCode
from app.routing.models import CidrRouteRule, DomainRouteRule
from app.routing.router import policy_dns_observer
from app.users.models import User, UserRole
from app.vpn.models import VPNClient, VPNNode, VPNRoute, VPNServer
from app.vpn.service import VPNService

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


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
    active_domain_rules = (await session.execute(
        select(func.count(DomainRouteRule.id)).where(DomainRouteRule.is_active == True)
    )).scalar() or 0
    active_cidr_rules = (await session.execute(
        select(func.count(CidrRouteRule.id)).where(CidrRouteRule.is_active == True)
    )).scalar() or 0
    active_dns_bindings = len(policy_dns_observer.get_active_bindings())

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
            "domain_rules_active": active_domain_rules,
            "cidr_rules_active": active_cidr_rules,
            "dns_bindings_active": active_dns_bindings,
            "policy_mode": "domain_first_with_ru_fallback",
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
