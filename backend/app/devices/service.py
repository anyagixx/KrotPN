# FILE: backend/app/devices/service.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Device access policy — enforce device-slot limits from subscriptions, coordinate revoke/rotate/block actions
#   SCOPE: Device-limit resolution, active-slot accounting, device creation guards, lifecycle transitions, audit-event writes
#   DEPENDS: M-001 (database), M-003 (vpn service), M-004 (billing service), M-020 (device-registry models)
#   LINKS: M-021 (device-access-policy), M-025 (device-audit-log), V-M-021
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   DeviceLimitExceededError - Raised when provisioning exceeds effective device limit
#   DeviceAccessPolicyService - Coordinates per-user device slots and lifecycle transitions (15 methods)
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""
Device access policy service.

MODULE_CONTRACT
- PURPOSE: Enforce device-slot policy from subscriptions, and coordinate revoke, rotate and block actions for device-bound access.
- SCOPE: Effective device-limit resolution, active-slot accounting, device creation guards, lifecycle transitions and audit-event writes.
- DEPENDS: M-001 DB session lifecycle, M-003 VPN service peer control, M-004 billing plan and subscription state, M-020 device-registry, M-021 device-access-policy, M-025 device-audit-log.
- LINKS: M-020 device-registry, M-021 device-access-policy, M-025 device-audit-log, V-M-021.

MODULE_MAP
- DeviceLimitExceededError: Raised when provisioning would exceed the effective device limit.
- DeviceAccessPolicyService: Coordinates per-user device slots and device lifecycle transitions.
  - list_user_devices: Returns all devices for one user ordered by creation time.
  - get_user_device: Resolves one owned device for authenticated API flows.
  - ensure_primary_device: Reuses the first active device or creates a compatibility primary device for legacy web flows.
  - get_consumed_device_count: Returns slots consumed by active or blocked devices.
  - get_effective_device_limit: Resolves the current device limit from active billing state.
  - list_device_events: Returns durable audit events for one device ordered newest to oldest.
  - get_recent_event_types: Returns compact recent event-type markers for admin summaries.
  - assert_can_create_device: Rejects provisioning before peer creation if no device slot available.
  - create_device_record: Persists a new active device and records an audit event.
  - revoke_device: Revokes one device, deactivates active peers, frees the slot.
  - rotate_device_config: Increments config version and records a rotation event.
  - block_device: Blocks one device, deactivates active peers, records enforcement action.
  - unblock_device: Removes the blocked state without silently reactivating the old peer.
  - _record_event: Writes one durable audit event for a device policy transition.

CHANGE_SUMMARY
- v2.8.0: Added GRACE-lite runtime markup with START_BLOCK/END_BLOCK for each class and method.
- 2026-03-27: Added first-pass device access policy for per-plan limits and device lifecycle enforcement.
"""
# <!-- GRACE: module="M-021" contract="device-access-policy" role="RUNTIME" MAP_MODE="EXPORTS" -->

from __future__ import annotations

from datetime import datetime, timezone, timezone

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.service import BillingService
from app.devices.models import (
    DeviceEventSeverity,
    DeviceSecurityEvent,
    DeviceSecurityEventType,
    DeviceStatus,
    UserDevice,
)
from app.vpn.service import VPNService


# <!-- START_BLOCK: DeviceLimitExceededError -->
class DeviceLimitExceededError(ValueError):
    """Raised when a user has exhausted their effective device slots."""
# <!-- END_BLOCK: DeviceLimitExceededError -->


# <!-- START_BLOCK: DeviceAccessPolicyService -->
class DeviceAccessPolicyService:
    """Policy service for device-bound access limits and lifecycle transitions."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.billing = BillingService(session)
        self.vpn = VPNService(session)

    # <!-- START_BLOCK: list_user_devices -->
    async def list_user_devices(self, user_id: int) -> list[UserDevice]:
        """Return all devices for one user ordered by creation time."""
        result = await self.session.execute(
            select(UserDevice)
            .where(UserDevice.user_id == user_id)
            .order_by(UserDevice.created_at.asc(), UserDevice.id.asc())
        )
        return list(result.scalars().all())
    # <!-- END_BLOCK: list_user_devices -->

    # <!-- START_BLOCK: get_user_device -->
    async def get_user_device(self, user_id: int, device_id: int) -> UserDevice | None:
        """Return one device only if it belongs to the requested user."""
        result = await self.session.execute(
            select(UserDevice).where(
                UserDevice.id == device_id,
                UserDevice.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
    # <!-- END_BLOCK: get_user_device -->

    # <!-- START_BLOCK: ensure_primary_device -->
    async def ensure_primary_device(
        self,
        user_id: int,
        *,
        name: str = "Primary device",
        platform: str | None = "web-default",
    ) -> UserDevice:
        """Reuse the first active device or create a compatibility primary device."""
        devices = await self.list_user_devices(user_id)
        for device in devices:
            if device.status is DeviceStatus.ACTIVE:
                return device
        return await self.create_device_record(user_id, name=name, platform=platform)
    # <!-- END_BLOCK: ensure_primary_device -->

    # <!-- START_BLOCK: get_consumed_device_count -->
    async def get_consumed_device_count(self, user_id: int) -> int:
        """Return the number of slots currently consumed by active or blocked devices."""
        result = await self.session.execute(
            select(UserDevice)
            .where(
                UserDevice.user_id == user_id,
                UserDevice.status.in_([DeviceStatus.ACTIVE, DeviceStatus.BLOCKED]),
            )
        )
        return len(list(result.scalars().all()))
    # <!-- END_BLOCK: get_consumed_device_count -->

    # <!-- START_BLOCK: get_effective_device_limit -->
    async def get_effective_device_limit(self, user_id: int) -> int:
        """Resolve the effective device limit from active billing state."""
        return await self.billing.get_effective_device_limit(user_id)
    # <!-- END_BLOCK: get_effective_device_limit -->

    # <!-- START_BLOCK: list_device_events -->
    async def list_device_events(self, device_id: int, *, limit: int = 20) -> list[DeviceSecurityEvent]:
        """Return device audit events ordered from newest to oldest."""
        result = await self.session.execute(
            select(DeviceSecurityEvent)
            .where(DeviceSecurityEvent.device_id == device_id)
            .order_by(DeviceSecurityEvent.created_at.desc(), DeviceSecurityEvent.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    # <!-- END_BLOCK: list_device_events -->

    # <!-- START_BLOCK: get_recent_event_types -->
    async def get_recent_event_types(self, device_id: int, *, limit: int = 3) -> list[str]:
        """Return recent event-type values for compact admin or telemetry summaries."""
        events = await self.list_device_events(device_id, limit=limit)
        return [event.event_type.value for event in events]
    # <!-- END_BLOCK: get_recent_event_types -->

    # <!-- START_BLOCK: assert_can_create_device -->
    async def assert_can_create_device(self, user_id: int) -> None:
        """Reject device creation before any peer provisioning if the limit is exhausted."""
        consumed = await self.get_consumed_device_count(user_id)
        limit = await self.get_effective_device_limit(user_id)
        logger.info(
            "[VPN][device][VPN_DEVICE_CREATE_REQUESTED] "
            f"user_id={user_id} consumed_slots={consumed} device_limit={limit}"
        )
        if limit <= 0 or consumed >= limit:
            logger.warning(
                "[VPN][device][VPN_DEVICE_LIMIT_REJECTED] "
                f"user_id={user_id} consumed_slots={consumed} device_limit={limit}"
            )
            raise DeviceLimitExceededError("Device limit exceeded")
    # <!-- END_BLOCK: assert_can_create_device -->

    # <!-- START_BLOCK: create_device_record -->
    async def create_device_record(
        self,
        user_id: int,
        *,
        name: str,
        platform: str | None = None,
    ) -> UserDevice:
        """Create a new active device after enforcing slot policy."""
        await self.assert_can_create_device(user_id)
        device = UserDevice(
            user_id=user_id,
            name=name.strip() or "New device",
            platform=platform,
            status=DeviceStatus.ACTIVE,
        )
        self.session.add(device)
        await self.session.flush()
        await self._record_event(
            user_id=user_id,
            device_id=int(device.id),
            event_type=DeviceSecurityEventType.DEVICE_CREATED,
            severity=DeviceEventSeverity.INFO,
            details_json='{"source":"device_access_policy"}',
        )
        logger.info(
            "[VPN][device][VPN_DEVICE_CREATED] "
            f"user_id={user_id} device_id={device.id} device_key={device.device_key} status={device.status.value}"
        )
        await self.session.refresh(device)
        return device
    # <!-- END_BLOCK: create_device_record -->

    # <!-- START_BLOCK: revoke_device -->
    async def revoke_device(self, device: UserDevice, *, reason: str = "user_request") -> UserDevice:
        """Revoke one device and deactivate any active peer bound to it."""
        if device.status is not DeviceStatus.REVOKED:
            await self.vpn.deactivate_device_clients(int(device.id))
            now = datetime.now(timezone.utc)
            device.status = DeviceStatus.REVOKED
            device.revoked_at = now
            device.updated_at = now
            device.block_reason = reason
            await self._record_event(
                user_id=int(device.user_id),
                device_id=int(device.id),
                event_type=DeviceSecurityEventType.DEVICE_REVOKED,
                severity=DeviceEventSeverity.INFO,
                details_json=f'{{"reason":"{reason}"}}',
            )
            logger.info(
                "[VPN][device][VPN_DEVICE_REVOKED] "
                f"user_id={device.user_id} device_id={device.id} reason={reason}"
            )
            await self.session.flush()
        return device
    # <!-- END_BLOCK: revoke_device -->

    # <!-- START_BLOCK: rotate_device_config -->
    async def rotate_device_config(self, device: UserDevice, *, reason: str = "user_rotate") -> UserDevice:
        """Mark a device config rotation without changing the logical device identity."""
        device.config_version += 1
        device.updated_at = datetime.now(timezone.utc)
        await self._record_event(
            user_id=int(device.user_id),
            device_id=int(device.id),
            event_type=DeviceSecurityEventType.CONFIG_ROTATED,
            severity=DeviceEventSeverity.INFO,
            details_json=f'{{"reason":"{reason}","config_version":{device.config_version}}}',
        )
        logger.info(
            "[VPN][device][VPN_DEVICE_CONFIG_ROTATED] "
            f"user_id={device.user_id} device_id={device.id} config_version={device.config_version} reason={reason}"
        )
        await self.session.flush()
        return device
    # <!-- END_BLOCK: rotate_device_config -->

    # <!-- START_BLOCK: block_device -->
    async def block_device(self, device: UserDevice, *, reason: str = "admin_block") -> UserDevice:
        """Block one device and deactivate any active peers while preserving slot consumption."""
        if device.status is not DeviceStatus.BLOCKED:
            await self.vpn.deactivate_device_clients(int(device.id))
            now = datetime.now(timezone.utc)
            device.status = DeviceStatus.BLOCKED
            device.blocked_at = now
            device.updated_at = now
            device.block_reason = reason
            await self._record_event(
                user_id=int(device.user_id),
                device_id=int(device.id),
                event_type=DeviceSecurityEventType.DEVICE_BLOCKED,
                severity=DeviceEventSeverity.WARNING,
                details_json=f'{{"reason":"{reason}"}}',
            )
            logger.warning(
                "[VPN][device][VPN_DEVICE_BLOCKED] "
                f"user_id={device.user_id} device_id={device.id} reason={reason}"
            )
            await self.session.flush()
        return device
    # <!-- END_BLOCK: block_device -->

    # <!-- START_BLOCK: unblock_device -->
    async def unblock_device(self, device: UserDevice, *, reason: str = "admin_unblock") -> UserDevice:
        """Remove the blocked state without automatically restoring the old peer."""
        if device.status is DeviceStatus.BLOCKED:
            device.status = DeviceStatus.ACTIVE
            device.updated_at = datetime.now(timezone.utc)
            device.blocked_at = None
            device.block_reason = None
            await self._record_event(
                user_id=int(device.user_id),
                device_id=int(device.id),
                event_type=DeviceSecurityEventType.DEVICE_UNBLOCKED,
                severity=DeviceEventSeverity.INFO,
                details_json=f'{{"reason":"{reason}"}}',
            )
            logger.info(
                "[VPN][device][VPN_DEVICE_UNBLOCKED] "
                f"user_id={device.user_id} device_id={device.id} reason={reason}"
            )
            await self.session.flush()
        return device
    # <!-- END_BLOCK: unblock_device -->

    # <!-- START_BLOCK: _record_event -->
    async def _record_event(
        self,
        *,
        user_id: int,
        device_id: int,
        event_type: DeviceSecurityEventType,
        severity: DeviceEventSeverity,
        details_json: str | None,
    ) -> DeviceSecurityEvent:
        """Write one durable audit event for a device policy transition."""
        event = DeviceSecurityEvent(
            user_id=user_id,
            device_id=device_id,
            event_type=event_type,
            severity=severity,
            details_json=details_json,
        )
        self.session.add(event)
        await self.session.flush()
        logger.info(
            "[VPN][device][VPN_DEVICE_AUDIT_RECORDED] "
            f"user_id={user_id} device_id={device_id} event_type={event_type.value} severity={severity.value}"
        )
        return event
    # <!-- END_BLOCK: _record_event -->
# <!-- END_BLOCK: DeviceAccessPolicyService -->
