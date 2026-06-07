"""MTProto provisioning service public entry point.

# FILE: backend/app/mtproto/service.py
# VERSION: 1.4.0
# ROLE: BARREL
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Expose MTProto provisioning and manual external delivery services from a stable module path
#   SCOPE: Re-export provisioning error types, CTA SNI helpers, KPprotoN fake-TLS helpers,
#          MTProtoProvisioningService, and Phase-80 manual external proxy pool helpers
#   DEPENDS: M-043 (provisioning core), M-065 (CTA MTProto link generation), M-082 (manual external pool)
#   LINKS: M-043, M-065, M-082, V-M-043, V-M-065, V-M-082
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MTProtoProvisioningErrorCode - Stable safe failure codes
#   MTProtoProvisioningError - Typed provisioning exception
#   MTProtoProvisioningService - Idempotent issue/reissue service
#   MTPROTO_CTA_PREFIXES - Fixed Phase-47 CTA prefix allow-list
#   build_tg_link - Telegram tg://proxy link assembly helper
#   derive_fake_tls_secret - KPprotoN-compatible fake-TLS secret derivation helper
#   generate_cta_sni - Phase-47 CTA SNI generation helper
#   generate_sni - Deterministic wildcard-safe SNI generation helper
#   MTProtoManualProxyPoolError - Safe manual pool exception
#   MTProtoManualProxyPoolService - Admin-managed external proxy pool and delivery selector
#   select_cta_prefix - Phase-47 CTA prefix selector
#   shorten_public_user_id - Phase-47 public user suffix helper
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.4.0 - Re-exported Phase-80 manual external proxy pool service.
#   LAST_CHANGE: v1.3.0 - Re-exported Phase-47 CTA SNI generation helpers.
#   LAST_CHANGE: v1.2.0 - Re-scoped stable exports to KPprotoN fake-TLS provisioning helpers.
#   LAST_CHANGE: v1.1.0 - Re-export official MTProxy secure secret helpers for Phase-40.
#   LAST_CHANGE: v1.0.0 - Added Phase-29 stable service re-export module
# END_CHANGE_SUMMARY
"""

from app.mtproto.provisioning import (
    MTPROTO_CTA_PREFIXES,
    MTProtoProvisioningError,
    MTProtoProvisioningErrorCode,
    MTProtoProvisioningService,
    build_tg_link,
    derive_fake_tls_secret,
    generate_cta_sni,
    generate_sni,
    select_cta_prefix,
    shorten_public_user_id,
)
from app.mtproto.manual_pool import (
    MTProtoManualProxyPoolError,
    MTProtoManualProxyPoolService,
    build_manual_browser_link,
    build_manual_tg_link,
)

__all__ = [
    "MTPROTO_CTA_PREFIXES",
    "MTProtoManualProxyPoolError",
    "MTProtoManualProxyPoolService",
    "MTProtoProvisioningError",
    "MTProtoProvisioningErrorCode",
    "MTProtoProvisioningService",
    "build_manual_browser_link",
    "build_manual_tg_link",
    "build_tg_link",
    "derive_fake_tls_secret",
    "generate_cta_sni",
    "generate_sni",
    "select_cta_prefix",
    "shorten_public_user_id",
]
