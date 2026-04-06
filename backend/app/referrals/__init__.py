# FILE: backend/app/referrals/__init__.py
# VERSION: 1.0.0
# ROLE: BARREL
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: Barrel exports for referral program — models, service, and routers
#   SCOPE: Re-exports public API of the referrals module for app-level wiring
#   DEPENDS: M-005 (referrals models, service, router)
#   LINKS: M-005 (referral-program)
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   ReferralCode - User's referral code model with uses and bonus tracking
#   Referral - Referral relationship model with bonus_given tracking
#   ReferralStats - Response model for aggregated referral statistics
#   ReferralService - Service class for all referral operations
#   referral_router - User-facing referral API router
#   admin_referral_router - Admin-facing referral API router
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""Referrals module exports.

MODULE_CONTRACT
- PURPOSE: Barrel exports for referral program — models, service, and routers.
- SCOPE: Re-exports public API of the referrals module for app-level wiring.
- DEPENDS: M-005 referrals module (models, service, router).
- LINKS: M-005 referral-program.

MODULE_MAP
- ReferralCode: User's referral code model.
- Referral: Referral relationship model.
- ReferralStats: Referral statistics response model.
- ReferralService: Service for referral operations.
- referral_router: User-facing referral API router.
- admin_referral_router: Admin-facing referral API router.

CHANGE_SUMMARY
- v2.8.0: Added GRACE-lite barrel markup for referrals module.
"""
# <!-- GRACE: role="BARREL" module="M-005" MAP_MODE="SUMMARY" -->

from app.referrals.models import ReferralCode, Referral, ReferralStats
from app.referrals.service import ReferralService
from app.referrals.router import router as referral_router
from app.referrals.router import admin_router as admin_referral_router

# <!-- START_BLOCK: __all__ -->
__all__ = [
    # Models
    "ReferralCode",
    "Referral",
    "ReferralStats",
    # Service
    "ReferralService",
    # Routers
    "referral_router",
    "admin_referral_router",
]
# <!-- END_BLOCK: __all__ -->
