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
- UserDevice: Logical device registry row for one user-owned device.
- DeviceSecurityEvent: Durable audit or anomaly event linked to a user device.

CHANGE_SUMMARY
- 2026-03-27: Added first-class device registry and device security event models for plan-bound device limits and anti-sharing observability.
"""
# <!-- GRACE: module="M-020" entity="UserDevice, DeviceSecurityEvent" -->

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.users.models import User
    from app.vpn.models import VPNClient


class DeviceStatus(str, Enum):
    """Lifecycle states for tracked devices."""

    ACTIVE = "active"
    REVOKED = "revoked"
    BLOCKED = "blocked"
    REPLACED = "replaced"


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


class DeviceEventSeverity(str, Enum):
    """Stable severity for device audit and anomaly records."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


def _default_device_key() -> str:
    """Generate an opaque but stable-looking identifier for operator logs and API surfaces."""
    return uuid4().hex


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
    revoked_at: datetime | None = Field(default=None)
    blocked_at: datetime | None = Field(default=None)
    last_seen_at: datetime | None = Field(default=None)
    last_handshake_at: datetime | None = Field(default=None)
    last_endpoint: str | None = Field(default=None, max_length=255)

    config_version: int = Field(default=1)
    block_reason: str | None = Field(default=None, max_length=255)

    user: "User" = Relationship(back_populates="devices")
    vpn_clients: list["VPNClient"] = Relationship(back_populates="device")
    security_events: list["DeviceSecurityEvent"] = Relationship(back_populates="device")


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
