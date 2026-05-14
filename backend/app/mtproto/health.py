"""MTProto runtime health helpers.

# FILE: backend/app/mtproto/health.py
# VERSION: 1.0.0
# ROLE: TYPES
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Build secret-free MTProto runtime health summaries
#   SCOPE: Convert runtime bridge health objects into user-safe/admin-safe payloads
#   DEPENDS: M-044 (runtime bridge)
#   LINKS: M-044, V-M-044
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   build_runtime_health_summary - Convert MTProtoRuntimeHealth into a safe dict
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-30 runtime health summary helper
# END_CHANGE_SUMMARY
"""

from app.mtproto.runtime_bridge import MTProtoRuntimeHealth


# START_CONTRACT: build_runtime_health_summary
#   PURPOSE: Return a secret-free health payload for operator or future API use
#   INPUTS: health: MTProtoRuntimeHealth
#   OUTPUTS: dict[str, object]
#   SIDE_EFFECTS: none
#   LINKS: M-044, V-M-044
# END_CONTRACT: build_runtime_health_summary
# START_BLOCK_BUILD_HEALTH_SUMMARY
def build_runtime_health_summary(health: MTProtoRuntimeHealth) -> dict[str, object]:
    """Return aggregate health data without proxy credentials."""
    return health.to_safe_dict()
# END_BLOCK_BUILD_HEALTH_SUMMARY
