# FILE: backend/app/devices/models.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Device registry models — user devices and security event persistence
#   SCOPE: Device identity, lifecycle state, last-seen metadata, config versioning, security event storage
#   DEPENDS: M-001 (core database), M-002 (users), M-003 (vpn models)
#   LINKS: M-020 (device-registry), M-025 (device-audit-log), V-M-020, V-M-025
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   DeviceStatus - Enum: active, revoked, blocked, replaced
#   DeviceSecurityEventType - Enum: lifecycle events, legacy suspicion events, anti-abuse detection/enforcement events
#   DeviceEventSeverity - Enum: info, warning, critical
#   _default_device_key - Generate opaque stable identifier for logs/API
#   UserDevice - Logical user device tracked separately from VPN peer
#   DeviceSecurityEvent - Durable device audit/anomaly event
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v3.1.0 - Added anti-abuse detection, auto-rotation, cooldown and degraded-mode event types
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""
Device registry models for device-bound access control.

MODULE_CONTRACT
- PURPOSE: Persist logical user devices and durable device lifecycle or anomaly events for future device-bound provisioning and anti-sharing enforcement.
- SCOPE: Device identity, lifecycle state, last-seen metadata, config generation versioning and security event storage.
- DEPENDS: M-001 database metadata registration, M-002 user identities, M-003 VPN clients linked to device-bound peers, M-020 device-registry, M-025 device-audit-log.
- LINKS: M-020 device-registry, M-025 device-audit-log, V-M-020, V-M-025.

MODULE_MAP
- DeviceStatus: Stable lifecycle states for tracked devices.
- DeviceSecurityEventType: Stable event types for lifecycle and anti-sharing records.
- DeviceEventSeverity: Stable severity levels for device security events.
- _default_device_key: Generates an opaque stable identifier for operator logs and API surfaces.
- UserDevice: Logical device registry row for one user-owned device.
- DeviceSecurityEvent: Durable audit or anomaly event linked to a user device.

CHANGE_SUMMARY
- v2.8.0: Added GRACE-lite runtime markup with START_BLOCK/END_BLOCK for each class and enum.
- 2026-03-27: Added first-class device registry and device security event models for plan-bound device limits and anti-sharing observability.
"""
# <!-- GRACE: module="M-020" entity="UserDevice, DeviceSecurityEvent" role="RUNTIME" MAP_MODE="EXPORTS" -->

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.users.models import User
    from app.vpn.models import VPNClient


# <!-- START_BLOCK: DeviceStatus -->
class DeviceStatus(str, Enum):
    """Lifecycle states for tracked devices."""

    ACTIVE = "active"
    REVOKED = "revoked"
    BLOCKED = "blocked"
    REPLACED = "replaced"
# <!-- END_BLOCK: DeviceStatus -->


# <!-- START_BLOCK: DeviceSecurityEventType -->
class DeviceSecurityEventType(str, Enum):
    """Stable device event types for lifecycle and anomaly records."""

    DEVICE_CREATED = "device_created"
    MIGRATED_PRIMARY_DEVICE = "migrated_primary_device"
    CONFIG_ROTATED = "config_rotated"
    DEVICE_REVOKED = "device_revoked"
    DEVICE_BLOCKED = "device_blocked"
    DEVICE_UNBLOCKED = "device_unblocked"
    SUSPICIOUS_ENDPOINT_CHURN = "suspicious_endpoint_churn"
    CONCURRENT_HANDSHAKE_SUSPECTED = "concurrent_handshake_suspected"
    PING_PONG_ABUSE_DETECTED = "ping_pong_abuse_detected"
    MULTI_NETWORK_ABUSE_DETECTED = "multi_network_abuse_detected"
    ANTI_ABUSE_AUTO_ROTATE_STARTED = "anti_abuse_auto_rotate_started"
    ANTI_ABUSE_AUTO_ROTATE_COMPLETED = "anti_abuse_auto_rotate_completed"
    ANTI_ABUSE_COOLDOWN_SKIPPED = "anti_abuse_cooldown_skipped"
    ANTI_ABUSE_REDIS_DEGRADED = "anti_abuse_redis_degraded"
# <!-- END_BLOCK: DeviceSecurityEventType -->


# <!-- START_BLOCK: DeviceEventSeverity -->
class DeviceEventSeverity(str, Enum):
    """Stable severity for device audit and anomaly records."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
# <!-- END_BLOCK: DeviceEventSeverity -->


# <!-- START_BLOCK: _default_device_key -->
def _default_device_key() -> str:
    """Generate an opaque but stable-looking identifier for operator logs and API surfaces."""
    return uuid4().hex
# <!-- END_BLOCK: _default_device_key -->


# <!-- START_BLOCK: UserDevice -->
class UserDevice(SQLModel, table=True):
    """Logical user device tracked separately from low-level VPN peer records."""

    __tablename__ = "user_devices"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    device_key: str = Field(default_factory=_default_device_key, unique=True, index=True, max_length=64)
    name: str = Field(default="New device", max_length=100)
    platform: str | None = Field(default=None, max_length=50)
    status: DeviceStatus = Field(default=DeviceStatus.ACTIVE, max_length=20)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    revoked_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    blocked_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    last_seen_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    last_handshake_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    last_endpoint: str | None = Field(default=None, max_length=255)

    config_version: int = Field(default=1)
    block_reason: str | None = Field(default=None, max_length=255)

    user: "User" = Relationship(back_populates="devices")
    vpn_clients: list["VPNClient"] = Relationship(back_populates="device")
    security_events: list["DeviceSecurityEvent"] = Relationship(back_populates="device")
# <!-- END_BLOCK: UserDevice -->


# <!-- START_BLOCK: DeviceSecurityEvent -->
class DeviceSecurityEvent(SQLModel, table=True):
    """Durable device audit or anomaly event."""

    __tablename__ = "device_security_events"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    device_id: int = Field(foreign_key="user_devices.id", index=True)
    event_type: DeviceSecurityEventType = Field(max_length=50)
    severity: DeviceEventSeverity = Field(default=DeviceEventSeverity.INFO, max_length=20)
    details_json: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))

    device: "UserDevice" = Relationship(back_populates="security_events")
# <!-- END_BLOCK: DeviceSecurityEvent -->
