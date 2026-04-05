"""
Referral API router.
"""
# <!-- GRACE: module="M-005" api-group="Referral API" -->

from fastapi import APIRouter

from app.core import CurrentAdmin, CurrentUser, DBSession, settings, settings, settings
from app.referrals.models import ReferralStats
from app.referrals.service import ReferralService

router = APIRouter(prefix="/api/v1/referrals", tags=["referrals"])
admin_router = APIRouter(prefix="/api/v1/admin/referrals", tags=["admin"])


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


@router.get("/stats", response_model=ReferralStats)
async def get_referral_stats(
    current_user: CurrentUser,
    session: DBSession,
):
    """Get user's referral statistics."""
    service = ReferralService(session)
    return await service.get_referral_stats(current_user.id)


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


# ==================== Admin Endpoints ====================

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
