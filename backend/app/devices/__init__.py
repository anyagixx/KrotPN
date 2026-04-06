# FILE: backend/app/devices/__init__.py
# VERSION: 1.0.0
# ROLE: BARREL
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: Barrel exports for device registry — models, schemas, and service
#   SCOPE: Re-exports public API of the devices module for app-level wiring
#   DEPENDS: M-020 (device-registry models), M-021 (device-access-policy service), M-022 (device-provisioning-api schemas)
#   LINKS: M-020 (device-registry), M-021 (device-access-policy), M-022 (device-provisioning-api)
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   DeviceStatus - Lifecycle states for tracked devices
#   DeviceSecurityEventType - Event types for device lifecycle and anomaly records
#   DeviceEventSeverity - Severity levels for device security events
#   UserDevice - Logical device registry model
#   DeviceSecurityEvent - Device audit/anomaly event model
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""Device registry and anti-sharing persistence surfaces.

MODULE_CONTRACT
- PURPOSE: Barrel exports for device registry — models, schemas, and service.
- SCOPE: Re-exports public API of the devices module for app-level wiring.
- DEPENDS: M-020 device-registry (models).
- LINKS: M-020 device-registry, M-021 device-access-policy, M-022 device-provisioning-api.

MODULE_MAP
- DeviceStatus: Lifecycle states for tracked devices.
- DeviceSecurityEventType: Event types for device lifecycle and anomaly records.
- DeviceEventSeverity: Severity levels for device security events.
- UserDevice: Logical device registry model.
- DeviceSecurityEvent: Device audit/anomaly event model.

CHANGE_SUMMARY
- v2.8.0: Added GRACE-lite barrel markup for devices module.
"""
# <!-- GRACE: role="BARREL" module="M-020" MAP_MODE="SUMMARY" -->

from app.devices.models import (
    DeviceEventSeverity,
    DeviceSecurityEvent,
    DeviceSecurityEventType,
    DeviceStatus,
    UserDevice,
)

# <!-- START_BLOCK: __all__ -->
__all__ = [
    "DeviceEventSeverity",
    "DeviceSecurityEvent",
    "DeviceSecurityEventType",
    "DeviceStatus",
    "UserDevice",
]
# <!-- END_BLOCK: __all__ -->
