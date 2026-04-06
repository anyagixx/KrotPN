# FILE: backend/app/referrals/service.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Referral program business logic — code generation, referral creation, first-payment bonus, statistics
#   SCOPE: ReferralService class with all referral operations; no HTTP concerns, pure DB + business logic
#   DEPENDS: M-001 (database, settings), M-002 (users), M-004 (billing service for subscription extension)
#   LINKS: M-005 (referral-program), M-004 (billing), V-M-005
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   ReferralService - Service class for referral operations (7 methods)
#   ReferralService._generate_code - Generate random alphanumeric referral code
#   ReferralService.get_or_create_code - Get or create unique referral code for user
#   ReferralService.get_code_by_code - Look up referral code by string value
#   ReferralService.create_referral - Create referral relationship between users
#   ReferralService.process_first_payment - Process referral bonus on first qualifying payment
#   ReferralService.get_referral_stats - Compute aggregated referral statistics for user
#   ReferralService.get_referrals_list - Return paginated list of referrals for user
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""
Referral service for managing referral program.

MODULE_CONTRACT
- PURPOSE: Implement referral program business logic — code generation, referral creation, first-payment bonus processing, and statistics.
- SCOPE: ReferralService class with all referral operations; no HTTP concerns, pure DB + business logic.
- DEPENDS: M-001 DB session lifecycle, M-002 user identities, M-004 billing service (subscription extension), M-001 settings (referral config).
- LINKS: M-005 referral-program, M-004 billing-subscription, V-M-005.

MODULE_MAP
- _generate_code: Generates a random alphanumeric referral code.
- get_or_create_code: Gets or creates a unique referral code for a user.
- get_code_by_code: Looks up a referral code by its string value.
- create_referral: Creates a referral relationship between referrer and referred user.
- process_first_payment: Processes referral bonus on a user's first qualifying payment.
- get_referral_stats: Computes aggregated referral statistics for a user.
- get_referrals_list: Returns a paginated list of referrals for a user.

CHANGE_SUMMARY
- v2.8.0: Added GRACE-lite runtime markup with START_BLOCK/END_BLOCK for each method.
"""
# <!-- GRACE: module="M-005" contract="referral-service" role="RUNTIME" MAP_MODE="EXPORTS" -->

import random
import string
from datetime import datetime, timezone, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.referrals.models import Referral, ReferralCode, ReferralStats
from loguru import logger


# <!-- START_BLOCK: ReferralService -->
class ReferralService:
    """Service for referral operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # <!-- START_BLOCK: _generate_code -->
    def _generate_code(self, length: int = 8) -> str:
        """Generate a random referral code."""
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choices(chars, k=length))
    # <!-- END_BLOCK: _generate_code -->

    # <!-- START_BLOCK: get_or_create_code -->
    async def get_or_create_code(self, user_id: int) -> ReferralCode:
        """Get or create referral code for user."""
        result = await self.session.execute(
            select(ReferralCode).where(ReferralCode.user_id == user_id)
        )
        code = result.scalar_one_or_none()

        if code:
            return code

        # Generate unique code
        while True:
            new_code = self._generate_code()
            existing = await self.session.execute(
                select(ReferralCode).where(ReferralCode.code == new_code)
            )
            if not existing.scalar_one_or_none():
                break

        code = ReferralCode(
            user_id=user_id,
            code=new_code,
        )

        self.session.add(code)
        await self.session.flush()
        await self.session.refresh(code)

        logger.info(f"[REFERRAL] Created code {new_code} for user {user_id}")
        return code
    # <!-- END_BLOCK: get_or_create_code -->

    # <!-- START_BLOCK: get_code_by_code -->
    async def get_code_by_code(self, code: str) -> ReferralCode | None:
        """Get referral code by code string."""
        result = await self.session.execute(
            select(ReferralCode).where(ReferralCode.code == code.upper())
        )
        return result.scalar_one_or_none()
    # <!-- END_BLOCK: get_code_by_code -->

    # <!-- START_BLOCK: create_referral -->
    async def create_referral(
        self,
        referrer_id: int,
        referred_id: int,
    ) -> Referral | None:
        """Create a referral relationship."""
        # Check if already referred
        result = await self.session.execute(
            select(Referral).where(Referral.referred_id == referred_id)
        )
        if result.scalar_one_or_none():
            return None

        # Don't allow self-referral
        if referrer_id == referred_id:
            return None

        referral = Referral(
            referrer_id=referrer_id,
            referred_id=referred_id,
        )

        self.session.add(referral)

        # Update code uses count
        code_result = await self.session.execute(
            select(ReferralCode).where(ReferralCode.user_id == referrer_id)
        )
        code = code_result.scalar_one_or_none()
        if code:
            code.uses_count += 1

        await self.session.flush()
        await self.session.refresh(referral)

        logger.info(f"[REFERRAL] Created referral: {referrer_id} -> {referred_id}")
        return referral
    # <!-- END_BLOCK: create_referral -->

    # <!-- START_BLOCK: process_first_payment -->
    async def process_first_payment(
        self,
        user_id: int,
        amount: float,
    ) -> bool:
        """
        Process referral bonus on first payment.

        Returns True if bonus was given.
        """
        # Find referral
        result = await self.session.execute(
            select(Referral).where(Referral.referred_id == user_id)
        )
        referral = result.scalar_one_or_none()

        if not referral or referral.bonus_given:
            return False

        # Check minimum payment amount
        if amount < settings.referral_min_payment:
            return False

        # Give bonus to referrer
        referral.bonus_given = True
        referral.bonus_days = settings.referral_bonus_days
        referral.first_payment_at = datetime.now(timezone.utc)
        referral.first_payment_amount = amount

        # Update referrer's code stats
        code_result = await self.session.execute(
            select(ReferralCode).where(ReferralCode.user_id == referral.referrer_id)
        )
        code = code_result.scalar_one_or_none()
        if code:
            code.bonus_earned_days += settings.referral_bonus_days

        # Extend referrer's subscription
        from app.billing.service import BillingService
        billing_service = BillingService(self.session)

        subscription_result = await self.session.execute(
            select(Referral).where(Referral.referred_id == user_id)
        )

        # Get referrer's active subscription
        from app.billing.models import Subscription
        sub_result = await self.session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == referral.referrer_id,
                Subscription.is_active == True,
            )
            .order_by(Subscription.expires_at.desc())
        )
        subscription = sub_result.scalar_one_or_none()

        if subscription:
            await billing_service.extend_subscription(
                subscription, settings.referral_bonus_days
            )

        await self.session.flush()

        logger.info(
            f"[REFERRAL] Bonus given: {settings.referral_bonus_days} days "
            f"to user {referral.referrer_id} for referral {user_id}"
        )

        return True
    # <!-- END_BLOCK: process_first_payment -->

    # <!-- START_BLOCK: get_referral_stats -->
    async def get_referral_stats(self, user_id: int) -> ReferralStats:
        """Get referral statistics for user."""
        # Get code
        code = await self.get_or_create_code(user_id)

        # Get stats
        result = await self.session.execute(
            select(
                func.count(Referral.id).label("total"),
                func.sum(func.case((Referral.bonus_given == True, 1), else_=0)).label("paid"),
                func.coalesce(func.sum(func.case(
                    (Referral.bonus_given == True, Referral.bonus_days),
                    else_=0
                )), 0).label("bonus_days"),
            ).where(Referral.referrer_id == user_id)
        )
        row = result.one()

        return ReferralStats(
            code=code.code,
            link=f"{settings.frontend_url}/register?ref={code.code}",
            total_referrals=row.total or 0,
            paid_referrals=row.paid or 0,
            bonus_days_earned=row.bonus_days or 0,
            bonus_days_available=code.bonus_earned_days,
        )
    # <!-- END_BLOCK: get_referral_stats -->

    # <!-- START_BLOCK: get_referrals_list -->
    async def get_referrals_list(
        self,
        user_id: int,
        limit: int = 50,
    ) -> list[Referral]:
        """Get list of referrals for user."""
        result = await self.session.execute(
            select(Referral)
            .where(Referral.referrer_id == user_id)
            .order_by(Referral.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    # <!-- END_BLOCK: get_referrals_list -->
# <!-- END_BLOCK: ReferralService -->
