# FILE: backend/app/billing/service.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Owns plans, subscriptions, payment records and webhook side effects.
#   SCOPE: Plan CRUD, subscription lifecycle, payment creation/processing, YooKassa webhook handling, complimentary access, device limits, billing stats.
#   DEPENDS: M-001 (config, database), M-002 (users), M-004 (billing models), M-005 (referrals)
#   LINKS: M-004 (billing)
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   CheckoutPlanRejected - Structured checkout rejection for noncanonical or incompatible device-limit plans
#   BillingService - Main service class for all billing operations
#   get_plans, get_plan, ensure_canonical_tariffs, validate_checkout_plan, create_plan - Plan CRUD and canonical checkout operations
#   get_user_subscription, get_effective_device_limit, get_user_subscription_history - Subscription reads
#   get_active_complimentary_access, ensure_complimentary_access - Complimentary access helpers
#   create_pending_trial, create_trial_subscription, grant_referral_bonus_days, activate_trial_on_first_vpn_handshake, create_subscription, extend_subscription, deactivate_subscription - Subscription lifecycle
#   create_payment, process_payment_webhook, _process_yookassa_webhook, get_user_payments - Payment operations
#   get_subscription_stats - Aggregate billing statistics
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v3.3.0 - Added Phase-69 referral-bonus pending access grants and handshake activation.
#   LAST_CHANGE: v3.2.0 - Added Phase-50 canonical tariff convergence, checkout validation, and payment metadata.
#   LAST_CHANGE: v3.1.0 - Added Phase-45 pending trial lifecycle and first VPN handshake activation.
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT, MODULE_MAP, and BLOCKS per GRACE governance protocol
#   v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""
Billing service for subscription and payment management.

GRACE-lite module contract:
- Owns plans, subscriptions, payment records and webhook side effects.
- `payment succeeded` is the critical business event: it may extend subscriptions,
  provision VPN access and trigger referral bonuses.
- Webhook handling must remain idempotent.
- Billing changes are security-sensitive and money-sensitive even when code diffs look small.

CHANGE_SUMMARY
- 2026-03-26: Added complimentary internal-access helpers so manual non-billable clients can stay inside the subscription model.
- 2026-03-27: Added effective device-limit helpers so device-bound provisioning can enforce per-plan limits before peer creation.
"""
# <!-- GRACE: module="M-004" contract="billing-service" -->

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.billing.models import (
    Payment,
    PaymentProvider,
    PaymentStatus,
    Plan,
    Subscription,
    SubscriptionStatus,
)
from app.billing.catalog import (
    CANONICAL_TARIFF_SLUGS,
    CANONICAL_TARIFFS,
    canonical_tariff_by_slug,
    is_canonical_tariff_slug,
    tariff_features_json,
)
from app.billing.yookassa import yookassa_client
from loguru import logger


REFERRAL_BONUS_ACCESS_LABEL = "referral-bonus"
TRIAL_REFERRAL_BONUS_ACCESS_LABEL = "trial-referral-bonus"


# START_BLOCK: trial_time_helpers
def _as_aware_utc(value: datetime) -> datetime:
    """Normalize DB timestamps that may come back as naive UTC under SQLite."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _trial_duration_days() -> int:
    """Return the configured trial duration with a defensive lower bound."""
    return max(1, int(settings.trial_days))
# END_BLOCK


# START_BLOCK: CheckoutPlanRejected
class CheckoutPlanRejected(ValueError):
    """Raised when a selected plan cannot be used for checkout."""

    def __init__(
        self,
        reason: str,
        detail: str,
        *,
        consumed_slots: int | None = None,
        device_limit: int | None = None,
    ):
        super().__init__(detail)
        self.reason = reason
        self.detail = detail
        self.consumed_slots = consumed_slots
        self.device_limit = device_limit
# END_BLOCK


# START_BLOCK: BillingService class
class BillingService:
    """Service for billing operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.yookassa = yookassa_client

    # ==================== Plans ====================

    # START_BLOCK: get_plans
    async def get_plans(
        self,
        active_only: bool = True,
        *,
        canonical_only: bool = False,
    ) -> list[Plan]:
        """Get all subscription plans."""
        query = select(Plan)

        if active_only:
            query = query.where(Plan.is_active == True)
        if canonical_only:
            query = query.where(Plan.slug.in_(CANONICAL_TARIFF_SLUGS))

        query = query.order_by(Plan.sort_order, Plan.price)

        result = await self.session.execute(query)
        return list(result.scalars().all())
    # END_BLOCK

    async def get_plan(self, plan_id: int) -> Plan | None:
        """Get plan by ID."""
        return await self.session.get(Plan, plan_id)

    # START_BLOCK: ensure_canonical_tariffs
    async def ensure_canonical_tariffs(self) -> list[Plan]:
        """Create or update the approved Phase-50 paid tariff rows."""
        plans: list[Plan] = []
        now = datetime.now(timezone.utc)

        for tariff in CANONICAL_TARIFFS:
            result = await self.session.execute(
                select(Plan)
                .where(Plan.slug == tariff.slug)
                .order_by(Plan.id.asc())
            )
            matches = list(result.scalars().all())
            plan = matches[0] if matches else None
            action = "updated" if plan is not None else "created"

            if plan is None:
                plan = Plan(slug=tariff.slug, name=tariff.name, price=tariff.price)
                self.session.add(plan)

            plan.slug = tariff.slug
            plan.name = tariff.name
            plan.description = tariff.description
            plan.price = tariff.price
            plan.currency = tariff.currency
            plan.duration_days = tariff.duration_days
            plan.device_limit = tariff.device_limit
            plan.features = tariff_features_json(tariff)
            plan.is_active = True
            plan.is_canonical = True
            plan.is_popular = tariff.is_popular
            plan.sort_order = tariff.sort_order
            plan.updated_at = now

            for duplicate in matches[1:]:
                duplicate.is_active = False
                duplicate.is_canonical = False
                duplicate.updated_at = now

            plans.append(plan)
            logger.info(
                "[M-068][tariff_catalog][TARIFF_CATALOG_UPSERT] "
                f"slug={tariff.slug} action={action} price={tariff.price:.2f} "
                f"device_limit={tariff.device_limit} duplicates_deactivated={len(matches[1:])}"
            )

        await self.session.flush()
        for plan in plans:
            await self.session.refresh(plan)

        return plans
    # END_BLOCK

    # START_BLOCK: validate_checkout_plan
    async def validate_checkout_plan(self, user_id: int, plan_id: int) -> Plan:
        """Validate that one plan can be purchased by one user before payment creation."""
        plan = await self.get_plan(plan_id)
        if (
            plan is None
            or not plan.is_active
            or not getattr(plan, "is_canonical", False)
            or not is_canonical_tariff_slug(plan.slug)
        ):
            logger.warning(
                "[M-068][checkout][TARIFF_CHECKOUT_REJECTED] "
                f"user_id={user_id} plan_id={plan_id} reason=noncanonical_or_inactive"
            )
            raise CheckoutPlanRejected(
                "noncanonical_or_inactive",
                "Тариф недоступен для оплаты.",
            )

        from app.devices.models import DeviceStatus, UserDevice

        result = await self.session.execute(
            select(func.count(UserDevice.id)).where(
                UserDevice.user_id == user_id,
                UserDevice.status.in_([DeviceStatus.ACTIVE, DeviceStatus.BLOCKED]),
            )
        )
        consumed_slots = int(result.scalar() or 0)
        device_limit = max(1, int(plan.device_limit))
        if consumed_slots > device_limit:
            logger.warning(
                "[M-068][checkout][TARIFF_DOWNGRADE_BLOCKED] "
                f"user_id={user_id} plan_slug={plan.slug} consumed_slots={consumed_slots} "
                f"device_limit={device_limit}"
            )
            raise CheckoutPlanRejected(
                "device_limit_exceeded",
                (
                    "Нельзя выбрать этот тариф: сейчас занято "
                    f"{consumed_slots} устройств при лимите {device_limit}. "
                    "Сначала отзовите лишние устройства."
                ),
                consumed_slots=consumed_slots,
                device_limit=device_limit,
            )

        logger.info(
            "[M-068][checkout][TARIFF_CHECKOUT_VALIDATED] "
            f"user_id={user_id} plan_slug={plan.slug} consumed_slots={consumed_slots} "
            f"device_limit={device_limit}"
        )
        return plan
    # END_BLOCK

    # START_BLOCK: create_plan
    async def create_plan(self, data: dict) -> Plan:
        """Create a new plan."""
        plan = Plan(
            name=data["name"],
            description=data.get("description"),
            price=data["price"],
            currency=data.get("currency", "RUB"),
            duration_days=data["duration_days"],
            device_limit=data.get("device_limit", 1),
            features=json.dumps(data.get("features", [])),
            is_canonical=False,
            is_popular=data.get("is_popular", False),
            sort_order=data.get("sort_order", 0),
        )

        self.session.add(plan)
        await self.session.flush()
        await self.session.refresh(plan)

        logger.info(f"[BILLING] Plan created: {plan.name}")
        return plan
    # END_BLOCK

    # ==================== Subscriptions ====================

    # START_BLOCK: get_user_subscription
    async def get_user_subscription(
        self,
        user_id: int,
        *,
        include_pending: bool = True,
    ) -> Subscription | None:
        """Get user's current access-bearing subscription."""
        now = datetime.now(timezone.utc)

        access_predicate = Subscription.expires_at > now
        if include_pending:
            access_predicate = or_(
                Subscription.expires_at > now,
                Subscription.pending_activation == True,
            )

        result = await self.session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.is_active == True,
                access_predicate,
            )
            .order_by(Subscription.pending_activation.asc(), Subscription.expires_at.desc())
        )
        return result.scalar_one_or_none()
    # END_BLOCK

    # START_BLOCK: get_effective_device_limit
    async def get_effective_device_limit(self, user_id: int) -> int:
        """Resolve the device limit for one user from the active subscription context."""
        subscription = await self.get_user_subscription(user_id)
        if subscription is None:
            return 0

        if subscription.pending_activation:
            return 1

        if subscription.is_complimentary:
            return 9999

        if subscription.plan_id is None:
            return 1

        plan = await self.get_plan(subscription.plan_id)
        if plan is None:
            return 1
        return max(1, int(plan.device_limit))
    # END_BLOCK

    # START_BLOCK: get_user_subscription_history
    async def get_user_subscription_history(
        self, user_id: int, limit: int = 10
    ) -> list[Subscription]:
        """Get user's subscription history."""
        result = await self.session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    # END_BLOCK

    # START_BLOCK: get_active_complimentary_access
    async def get_active_complimentary_access(
        self,
        user_id: int,
        access_label: str | None = None,
    ) -> Subscription | None:
        """Return the current complimentary access record for one user."""
        now = datetime.now(timezone.utc)
        query = (
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.is_complimentary == True,
                Subscription.is_active == True,
                Subscription.expires_at > now,
            )
            .order_by(Subscription.expires_at.desc())
        )
        if access_label is not None:
            query = query.where(Subscription.access_label == access_label)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    # END_BLOCK

    # START_BLOCK: create_pending_trial
    async def create_pending_trial(self, user_id: int) -> Subscription:
        """Create an eligible trial whose countdown waits for first VPN handshake."""
        now = datetime.now(timezone.utc)
        duration_days = _trial_duration_days()

        result = await self.session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.is_active == True,
                Subscription.is_trial == True,
                Subscription.pending_activation == True,
            )
            .order_by(Subscription.created_at.desc())
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            logger.info(
                "[BillingService][create_pending_trial][CREATE_PENDING_TRIAL] "
                f"user_id={user_id} subscription_id={existing.id} reused=true"
            )
            return existing

        subscription = Subscription(
            user_id=user_id,
            plan_id=None,  # Trial has no plan
            status=SubscriptionStatus.TRIAL,
            is_active=True,
            is_trial=True,
            pending_activation=True,
            activated_at=None,
            trial_duration_days=duration_days,
            started_at=now,
            expires_at=now,
        )

        self.session.add(subscription)
        await self.session.flush()
        await self.session.refresh(subscription)

        logger.info(
            "[BillingService][create_pending_trial][CREATE_PENDING_TRIAL] "
            f"user_id={user_id} subscription_id={subscription.id} trial_duration_days={duration_days} reused=false"
        )
        return subscription
    # END_BLOCK

    # START_BLOCK: create_trial_subscription
    async def create_trial_subscription(self, user_id: int) -> Subscription:
        """Compatibility wrapper for the Phase-45 pending-trial lifecycle."""
        return await self.create_pending_trial(user_id)
    # END_BLOCK

    # START_BLOCK: grant_referral_bonus_days
    async def grant_referral_bonus_days(
        self,
        user_id: int,
        days: int,
    ) -> Subscription:
        """Grant referral reward days as an active extension or pending first-VPN access."""
        now = datetime.now(timezone.utc)
        bonus_days = max(1, int(days))
        active_subscription = await self.get_user_subscription(user_id, include_pending=False)
        if active_subscription is not None:
            subscription = await self.extend_subscription(active_subscription, bonus_days)
            logger.info(
                "[BillingService][grant_referral_bonus_days][REFERRAL_BONUS_GRANTED] "
                f"user_id={user_id} subscription_id={subscription.id} days={bonus_days} mode=active_extension"
            )
            return subscription

        pending_result = await self.session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.is_active == True,
                Subscription.pending_activation == True,
            )
            .order_by(Subscription.created_at.asc(), Subscription.id.asc())
        )
        pending = pending_result.scalar_one_or_none()
        if pending is not None:
            pending.trial_duration_days = int(pending.trial_duration_days or 0) + bonus_days
            if pending.is_trial:
                pending.access_label = TRIAL_REFERRAL_BONUS_ACCESS_LABEL
            else:
                pending.access_label = REFERRAL_BONUS_ACCESS_LABEL
            pending.updated_at = now
            await self.session.flush()
            await self.session.refresh(pending)
            logger.info(
                "[BillingService][grant_referral_bonus_days][REFERRAL_BONUS_GRANTED] "
                f"user_id={user_id} subscription_id={pending.id} days={bonus_days} mode=pending_extension"
            )
            return pending

        subscription = Subscription(
            user_id=user_id,
            plan_id=None,
            status=SubscriptionStatus.ACTIVE,
            is_active=True,
            is_trial=False,
            pending_activation=True,
            activated_at=None,
            trial_duration_days=bonus_days,
            is_complimentary=False,
            access_label=REFERRAL_BONUS_ACCESS_LABEL,
            started_at=now,
            expires_at=now,
        )

        self.session.add(subscription)
        await self.session.flush()
        await self.session.refresh(subscription)
        logger.info(
            "[BillingService][grant_referral_bonus_days][REFERRAL_BONUS_GRANTED] "
            f"user_id={user_id} subscription_id={subscription.id} days={bonus_days} mode=pending_create"
        )
        return subscription
    # END_BLOCK

    # START_BLOCK: ensure_complimentary_access
    async def ensure_complimentary_access(
        self,
        user_id: int,
        *,
        access_label: str = "internal-unlimited",
        duration_days: int = 36500,
    ) -> Subscription:
        """Create or reuse explicit complimentary access for internal users."""
        existing = await self.get_active_complimentary_access(
            user_id,
            access_label=access_label,
        )
        if existing is not None:
            logger.info(
                "[Billing][internal][VPN_INTERNAL_ACCESS_GRANTED] "
                f"user_id={user_id} subscription_id={existing.id} "
                f"complimentary=true access_label={access_label} reused=true"
            )
            return existing

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=duration_days)

        result = await self.session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.is_complimentary == True,
            )
            .order_by(Subscription.created_at.desc())
        )
        subscription = result.scalar_one_or_none()

        if subscription is None:
            subscription = Subscription(
                user_id=user_id,
                plan_id=None,
                status=SubscriptionStatus.ACTIVE,
                is_active=True,
                started_at=now,
                expires_at=expires_at,
                is_trial=False,
                pending_activation=False,
                activated_at=now,
                is_complimentary=True,
                access_label=access_label,
            )
            self.session.add(subscription)
        else:
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.is_active = True
            subscription.is_trial = False
            subscription.pending_activation = False
            subscription.activated_at = subscription.activated_at or now
            subscription.is_complimentary = True
            subscription.access_label = access_label
            subscription.started_at = subscription.started_at or now
            subscription.expires_at = expires_at
            subscription.updated_at = now

        await self.session.flush()
        await self.session.refresh(subscription)
        logger.info(
            "[Billing][internal][VPN_INTERNAL_ACCESS_GRANTED] "
            f"user_id={user_id} subscription_id={subscription.id} "
            f"complimentary=true access_label={access_label} reused=false"
        )
        return subscription
    # END_BLOCK

    # START_BLOCK: activate_trial_on_first_vpn_handshake
    async def activate_trial_on_first_vpn_handshake(
        self,
        user_id: int,
        handshake_at: datetime,
        *,
        client_id: int | None = None,
    ) -> Subscription | None:
        """Start pending trial or referral-bonus access once from the first observed VPN handshake."""
        observed_at = _as_aware_utc(handshake_at)
        now = datetime.now(timezone.utc)

        active_subscription = await self.get_user_subscription(user_id, include_pending=False)
        if active_subscription is not None:
            logger.info(
                "[BillingService][activate_trial_on_first_vpn_handshake][ACTIVATE_PENDING_TRIAL] "
                f"user_id={user_id} client_id={client_id} skipped=already_active "
                f"subscription_id={active_subscription.id}"
            )
            return None

        result = await self.session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.is_active == True,
                Subscription.pending_activation == True,
            )
            .order_by(Subscription.created_at.asc(), Subscription.id.asc())
        )
        subscription = result.scalar_one_or_none()
        if subscription is None:
            logger.info(
                "[BillingService][activate_trial_on_first_vpn_handshake][ACTIVATE_PENDING_TRIAL] "
                f"user_id={user_id} client_id={client_id} skipped=no_pending_access"
            )
            return None

        duration_days = int(subscription.trial_duration_days or _trial_duration_days())
        subscription.pending_activation = False
        subscription.activated_at = observed_at
        subscription.started_at = observed_at
        subscription.expires_at = observed_at + timedelta(days=duration_days)
        subscription.status = (
            SubscriptionStatus.TRIAL
            if subscription.is_trial and subscription.access_label != REFERRAL_BONUS_ACCESS_LABEL
            else SubscriptionStatus.ACTIVE
        )
        subscription.is_active = True
        subscription.updated_at = now

        await self.session.flush()
        await self.session.refresh(subscription)
        logger.info(
            "[BillingService][activate_trial_on_first_vpn_handshake][ACTIVATE_PENDING_TRIAL] "
            f"user_id={user_id} client_id={client_id} subscription_id={subscription.id} "
            f"access_label={subscription.access_label} activated_at={observed_at.isoformat()} "
            f"expires_at={subscription.expires_at.isoformat()}"
        )
        return subscription
    # END_BLOCK

    # START_BLOCK: cancel_pending_trials
    async def cancel_pending_trials(self, user_id: int, *, reason: str = "replaced") -> int:
        """Deactivate pending trials when paid or manual access supersedes them."""
        result = await self.session.execute(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.is_active == True,
                Subscription.is_trial == True,
                Subscription.pending_activation == True,
            )
        )
        pending_trials = list(result.scalars().all())
        now = datetime.now(timezone.utc)
        for pending in pending_trials:
            pending.is_active = False
            pending.status = SubscriptionStatus.CANCELED
            pending.updated_at = now
        if pending_trials:
            await self.session.flush()
            logger.info(
                "[BillingService][cancel_pending_trials][PENDING_TRIAL_CANCELLED] "
                f"user_id={user_id} count={len(pending_trials)} reason={reason}"
            )
        return len(pending_trials)
    # END_BLOCK

    # START_BLOCK: consume_pending_referral_bonus_days
    async def consume_pending_referral_bonus_days(self, user_id: int) -> int:
        """Move pending referral reward days into a paid subscription flow."""
        result = await self.session.execute(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.is_active == True,
                Subscription.pending_activation == True,
                Subscription.access_label.in_(
                    [REFERRAL_BONUS_ACCESS_LABEL, TRIAL_REFERRAL_BONUS_ACCESS_LABEL]
                ),
            )
        )
        pending_rewards = list(result.scalars().all())
        if not pending_rewards:
            return 0

        now = datetime.now(timezone.utc)
        total_days = 0
        for pending in pending_rewards:
            duration_days = int(pending.trial_duration_days or 0)
            if pending.access_label == TRIAL_REFERRAL_BONUS_ACCESS_LABEL:
                duration_days = max(0, duration_days - _trial_duration_days())
            total_days += max(0, duration_days)
            pending.is_active = False
            pending.status = SubscriptionStatus.CANCELED
            pending.updated_at = now

        await self.session.flush()
        logger.info(
            "[BillingService][consume_pending_referral_bonus_days][REFERRAL_BONUS_CONSUMED] "
            f"user_id={user_id} pending_count={len(pending_rewards)} days={total_days}"
        )
        return total_days
    # END_BLOCK

    # START_BLOCK: create_subscription
    async def create_subscription(
        self,
        user_id: int,
        plan: Plan,
        payment: Payment | None = None,
    ) -> Subscription:
        """Create a subscription from a plan."""
        now = datetime.now(timezone.utc)

        # Check for existing active subscription. Pending trial rows are not
        # billable time and must not be used as the extension base.
        pending_referral_bonus_days = await self.consume_pending_referral_bonus_days(user_id)
        existing = await self.get_user_subscription(user_id, include_pending=False)
        await self.cancel_pending_trials(user_id, reason="paid_subscription")

        if existing:
            # Extend existing subscription
            new_expires = _as_aware_utc(existing.expires_at) + timedelta(days=plan.duration_days)
            existing.expires_at = new_expires
            existing.status = SubscriptionStatus.ACTIVE
            existing.is_trial = False
            existing.pending_activation = False
            existing.is_complimentary = False
            existing.access_label = None
            existing.plan_id = plan.id

            if payment:
                existing.is_recurring = bool(
                    payment.payment_metadata
                    and json.loads(payment.payment_metadata).get("save_payment_method")
                )

            await self.session.flush()
            await self.session.refresh(existing)

            logger.info(f"[BILLING] Subscription extended for user {user_id}")
            if pending_referral_bonus_days:
                existing = await self.extend_subscription(existing, pending_referral_bonus_days)
            return existing

        # Create new subscription
        expires_at = now + timedelta(days=plan.duration_days)

        subscription = Subscription(
            user_id=user_id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            is_active=True,
            is_trial=False,
            pending_activation=False,
            activated_at=now,
            is_complimentary=False,
            started_at=now,
            expires_at=expires_at,
        )

        self.session.add(subscription)
        await self.session.flush()
        await self.session.refresh(subscription)

        logger.info(f"[BILLING] Subscription created for user {user_id}")
        if pending_referral_bonus_days:
            subscription = await self.extend_subscription(subscription, pending_referral_bonus_days)
        return subscription
    # END_BLOCK

    # START_BLOCK: extend_subscription
    async def extend_subscription(
        self,
        subscription: Subscription,
        days: int,
    ) -> Subscription:
        """Extend a subscription by given days."""
        now = datetime.now(timezone.utc)

        # If expired, start from now
        base = max(_as_aware_utc(subscription.expires_at), now)
        subscription.expires_at = base + timedelta(days=days)
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.is_active = True
        subscription.pending_activation = False
        subscription.activated_at = subscription.activated_at or now
        subscription.updated_at = now

        await self.session.flush()
        await self.session.refresh(subscription)

        logger.info(f"[BILLING] Subscription {subscription.id} extended by {days} days")
        return subscription
    # END_BLOCK

    async def deactivate_subscription(self, subscription: Subscription) -> None:
        """Deactivate a subscription."""
        subscription.is_active = False
        subscription.status = SubscriptionStatus.CANCELED
        await self.session.flush()

        logger.info(f"[BILLING] Subscription {subscription.id} deactivated")

    # ==================== Payments ====================

    # START_BLOCK: create_payment
    async def create_payment(
        self,
        user_id: int,
        plan: Plan,
        provider: PaymentProvider = PaymentProvider.YOOKASSA,
        return_url: str | None = None,
    ) -> Payment:
        """Create a payment for a plan."""
        if plan.id is None:
            raise CheckoutPlanRejected("missing_plan_id", "Тариф недоступен для оплаты.")

        plan = await self.validate_checkout_plan(user_id, int(plan.id))
        tariff = canonical_tariff_by_slug(plan.slug or "")
        payment_metadata = {
            "user_id": user_id,
            "plan_id": plan.id,
            "plan_slug": plan.slug,
            "device_limit": plan.device_limit,
            "duration_days": plan.duration_days,
        }
        if tariff is not None:
            payment_metadata["canonical_name"] = tariff.name

        # Create payment record
        payment = Payment(
            user_id=user_id,
            plan_id=plan.id,
            amount=plan.price,
            currency=plan.currency,
            provider=provider,
            status=PaymentStatus.PENDING,
            description=f"Подписка: {plan.name}",
            payment_metadata=json.dumps(payment_metadata, ensure_ascii=False),
        )

        self.session.add(payment)
        await self.session.flush()
        payment_metadata_with_id = {**payment_metadata, "payment_id": payment.id}
        payment.payment_metadata = json.dumps(payment_metadata_with_id, ensure_ascii=False)

        # Create payment in provider
        if provider == PaymentProvider.YOOKASSA:
            try:
                yookassa_payment = await self.yookassa.create_payment(
                    amount=plan.price,
                    currency=plan.currency,
                    description=f"KrotPN - {plan.name}",
                    return_url=return_url,
                    metadata=payment_metadata_with_id,
                )

                payment.external_id = yookassa_payment["id"]
                payment.payment_url = yookassa_payment["confirmation"].get("url")

                logger.info(
                    "[BillingService][create_payment][BILLING_PAYMENT_CREATED] "
                    f"user_id={user_id} payment_id={payment.id} plan_slug={plan.slug} "
                    f"amount={plan.price:.2f} currency={plan.currency} provider={provider.value}"
                )

            except Exception as e:
                logger.error(f"[BILLING] YooKassa error: {e}")
                payment.status = PaymentStatus.FAILED
                payment.description = str(e)

        await self.session.flush()
        await self.session.refresh(payment)

        return payment
    # END_BLOCK

    async def process_payment_webhook(
        self,
        provider: PaymentProvider,
        data: dict[str, Any],
    ) -> Payment | None:
        """Process payment webhook from provider."""
        if provider == PaymentProvider.YOOKASSA:
            return await self._process_yookassa_webhook(data)

        return None

    # START_BLOCK: _process_yookassa_webhook
    async def _process_yookassa_webhook(self, data: dict) -> Payment | None:
        """Process YooKassa webhook."""
        # Keep this path idempotent. Providers can resend the same event,
        # and duplicate subscription/referral effects would be a production bug.
        event = data.get("event")
        payment_object = data.get("object", {})

        if event not in ("payment.succeeded", "payment.canceled", "payment.waiting_for_capture"):
            logger.debug(f"[BILLING] Ignoring YooKassa event: {event}")
            return None

        external_id = payment_object.get("id")
        status = payment_object.get("status")

        # Find payment by external ID
        result = await self.session.execute(
            select(Payment).where(Payment.external_id == external_id)
        )
        payment = result.scalar_one_or_none()

        if not payment:
            logger.warning(f"[BILLING] Payment not found for external_id: {external_id}")
            return None

        # Update payment status
        if status == "succeeded":
            if payment.status == PaymentStatus.SUCCEEDED:
                logger.info(f"[BILLING] Duplicate succeeded webhook ignored for payment {payment.id}")
                return payment

            payment.status = PaymentStatus.SUCCEEDED
            payment.paid_at = datetime.now(timezone.utc)

            # Create subscription
            plan = await self.get_plan(payment.plan_id)
            if plan:
                subscription = await self.create_subscription(payment.user_id, plan, payment)
                logger.info(
                    "[BillingService][process_payment_webhook][BILLING_SUBSCRIPTION_UPDATED] "
                    f"user_id={payment.user_id} payment_id={payment.id} "
                    f"subscription_id={subscription.id} plan_slug={plan.slug} "
                    f"device_limit={plan.device_limit}"
                )

                # Create VPN client if not exists
                from app.vpn.service import VPNService
                vpn_service = VPNService(self.session)
                existing_client = await vpn_service.get_user_client(payment.user_id)
                if not existing_client:
                    await vpn_service.create_client(payment.user_id)

                from app.referrals.service import ReferralService
                referral_service = ReferralService(self.session)
                await referral_service.process_first_payment(
                    payment.user_id,
                    payment.amount,
                )

            logger.info(f"[BILLING] Payment {payment.id} succeeded")

        elif status == "canceled":
            if payment.status == PaymentStatus.CANCELED:
                logger.info(f"[BILLING] Duplicate canceled webhook ignored for payment {payment.id}")
                return payment

            payment.status = PaymentStatus.CANCELED
            logger.info(f"[BILLING] Payment {payment.id} canceled")

        payment.updated_at = datetime.now(timezone.utc)
        await self.session.flush()

        return payment
    # END_BLOCK

    # START_BLOCK: get_user_payments
    async def get_user_payments(
        self, user_id: int, limit: int = 20
    ) -> list[Payment]:
        """Get user's payment history."""
        result = await self.session.execute(
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    # END_BLOCK

    # ==================== Stats ====================

    # START_BLOCK: get_subscription_stats
    async def get_subscription_stats(self) -> dict[str, Any]:
        """Get subscription statistics."""
        now = datetime.now(timezone.utc)

        # Active subscriptions
        active_result = await self.session.execute(
            select(func.count(Subscription.id)).where(
                Subscription.is_active == True,
                Subscription.is_complimentary == False,
                Subscription.pending_activation == False,
                Subscription.expires_at > now,
            )
        )
        active_count = active_result.scalar() or 0

        # Trial subscriptions
        trial_result = await self.session.execute(
            select(func.count(Subscription.id)).where(
                Subscription.is_trial == True,
                Subscription.is_active == True,
                Subscription.is_complimentary == False,
                Subscription.pending_activation == False,
                Subscription.expires_at > now,
            )
        )
        trial_count = trial_result.scalar() or 0

        # Expired this month
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        expired_result = await self.session.execute(
            select(func.count(Subscription.id)).where(
                Subscription.expires_at >= month_start,
                Subscription.expires_at < now,
            )
        )
        expired_count = expired_result.scalar() or 0

        # Revenue this month
        revenue_result = await self.session.execute(
            select(func.sum(Payment.amount)).where(
                Payment.status == PaymentStatus.SUCCEEDED,
                Payment.paid_at >= month_start,
            )
        )
        revenue = revenue_result.scalar() or 0

        return {
            "active_subscriptions": active_count,
            "trial_subscriptions": trial_count,
            "expired_this_month": expired_count,
            "revenue_this_month": revenue,
        }
    # END_BLOCK
# END_BLOCK
