# FILE: backend/app/referrals/router.py
# VERSION: 1.0.0
# ROLE: ENTRY_POINT
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: User-facing and admin referral API endpoints — code retrieval, stats, and referral list
#   SCOPE: User endpoints (/api/v1/referrals) and admin endpoints (/api/v1/admin/referrals)
#   DEPENDS: M-001 (auth/session: CurrentUser, CurrentAdmin, DBSession), M-005 (referral service), M-002 (users)
#   LINKS: M-005 (referral-program), V-M-005
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   get_referral_code - GET /api/v1/referrals/code - return user's referral code and link
#   get_referral_stats - GET /api/v1/referrals/stats - return user's referral statistics
#   get_referrals_list - GET /api/v1/referrals/list - return paginated list of user's referrals
#   admin_get_referral_stats - GET /api/v1/admin/referrals/stats - return global referral statistics (admin only)
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""
Referral API router.

MODULE_CONTRACT
- PURPOSE: Expose user-facing and admin referral API endpoints — code retrieval, stats, and referral list.
- SCOPE: User endpoints (/api/v1/referrals) and admin endpoints (/api/v1/admin/referrals).
- DEPENDS: M-001 auth/session (CurrentUser, CurrentAdmin, DBSession), M-005 referral service, M-002 user identities.
- LINKS: M-005 referral-program, V-M-005.

MODULE_MAP
- get_referral_code: Returns user's referral code and registration link.
- get_referral_stats: Returns user's referral statistics.
- get_referrals_list: Returns paginated list of user's referrals.
- admin_get_referral_stats: Returns global referral statistics (admin only).

CHANGE_SUMMARY
- v2.8.0: Added GRACE-lite entry_point markup with START_BLOCK/END_BLOCK for each endpoint.
"""
# <!-- GRACE: module="M-005" api-group="Referral API" role="ENTRY_POINT" MAP_MODE="SUMMARY" -->

from fastapi import APIRouter

from app.core import CurrentUser, CurrentAdmin, DBSession, settings, settings, settings
from app.referrals.models import ReferralStats
from app.referrals.service import ReferralService

router = APIRouter(prefix="/api/v1/referrals", tags=["referrals"])
admin_router = APIRouter(prefix="/api/v1/admin/referrals", tags=["admin"])


# <!-- START_BLOCK: get_referral_code -->
@router.get("/code")
async def get_referral_code(
    current_user: CurrentUser,
    session: DBSession,
):
    """Get user's referral code."""
    service = ReferralService(session)
    code = await service.get_or_create_code(current_user.id)

    return {
        "code": code.code,
        "link": f"{settings.frontend_url}/register?ref={code.code}",
    }
# <!-- END_BLOCK: get_referral_code -->


# <!-- START_BLOCK: get_referral_stats -->
@router.get("/stats", response_model=ReferralStats)
async def get_referral_stats(
    current_user: CurrentUser,
    session: DBSession,
):
    """Get user's referral statistics."""
    service = ReferralService(session)
    return await service.get_referral_stats(current_user.id)
# <!-- END_BLOCK: get_referral_stats -->


# <!-- START_BLOCK: get_referrals_list -->
@router.get("/list")
async def get_referrals_list(
    current_user: CurrentUser,
    session: DBSession,
    limit: int = 50,
):
    """Get list of user's referrals."""
    service = ReferralService(session)
    referrals = await service.get_referrals_list(current_user.id, limit)

    return {
        "items": [
            {
                "id": r.id,
                "bonus_given": r.bonus_given,
                "bonus_days": r.bonus_days,
                "created_at": r.created_at,
                "first_payment_at": r.first_payment_at,
            }
            for r in referrals
        ],
        "total": len(referrals),
    }
# <!-- END_BLOCK: get_referrals_list -->


# ==================== Admin Endpoints ====================

# <!-- START_BLOCK: admin_get_referral_stats -->
@admin_router.get("/stats")
async def admin_get_referral_stats(
    admin: CurrentAdmin,
    session: DBSession,
):
    """Get global referral statistics (admin)."""
    from sqlalchemy import func, select
    from app.referrals.models import Referral, ReferralCode

    # Total codes
    codes_result = await session.execute(select(func.count(ReferralCode.id)))
    total_codes = codes_result.scalar() or 0

    # Total referrals
    referrals_result = await session.execute(select(func.count(Referral.id)))
    total_referrals = referrals_result.scalar() or 0

    # Paid referrals
    paid_result = await session.execute(
        select(func.count(Referral.id)).where(Referral.bonus_given == True)
    )
    paid_referrals = paid_result.scalar() or 0

    # Total bonus days given
    bonus_result = await session.execute(
        select(func.sum(Referral.bonus_days)).where(Referral.bonus_given == True)
    )
    total_bonus_days = bonus_result.scalar() or 0

    return {
        "total_codes": total_codes,
        "total_referrals": total_referrals,
        "paid_referrals": paid_referrals,
        "conversion_rate": round(paid_referrals / total_referrals * 100, 1) if total_referrals > 0 else 0,
        "total_bonus_days_given": total_bonus_days,
    }
# <!-- END_BLOCK: admin_get_referral_stats -->
