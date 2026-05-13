"""MTProto provisioning service public entry point.

# FILE: backend/app/mtproto/service.py
# VERSION: 1.0.0
# ROLE: BARREL
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Expose the MTProto provisioning service from a stable module path
#   SCOPE: Re-export provisioning error types, helpers, and MTProtoProvisioningService
#   DEPENDS: M-043 (provisioning core)
#   LINKS: M-043, V-M-043
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MTProtoProvisioningErrorCode - Stable safe failure codes
#   MTProtoProvisioningError - Typed provisioning exception
#   MTProtoProvisioningService - Idempotent issue/reissue service
#   build_tg_link - Telegram tg://proxy link assembly helper
#   derive_fake_tls_secret - KPprotoN-compatible fake-TLS secret derivation helper
#   generate_sni - Deterministic wildcard-safe SNI generation helper
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-29 stable service re-export module
# END_CHANGE_SUMMARY
"""

from app.mtproto.provisioning import (
    MTProtoProvisioningError,
    MTProtoProvisioningErrorCode,
    MTProtoProvisioningService,
    build_tg_link,
    derive_fake_tls_secret,
    generate_sni,
)

__all__ = [
    "MTProtoProvisioningError",
    "MTProtoProvisioningErrorCode",
    "MTProtoProvisioningService",
    "build_tg_link",
    "derive_fake_tls_secret",
    "generate_sni",
]
