"""
MODULE_CONTRACT
- PURPOSE: Verify billing service operations for subscriptions and payments.
- SCOPE: Trial creation, active subscription lookup, expiry, payment webhook processing.
- DEPENDS: app.billing.service, app.billing.models.
- LINKS: V-M-004.

MODULE_MAP
- test_create_trial_subscription_creates_pending_four_day_trial: Verifies pending trial duration metadata.
- test_get_active_subscription_returns_none_when_no_subscription: Verifies empty lookup.
- test_get_active_subscription_returns_active_when_valid: Verifies active subscription lookup.
- test_expire_subscription_marks_inactive: Verifies deactivation.
- test_payment_webhook_succeeded_creates_subscription: Verifies happy-path webhook.
- test_create_payment_uses_server_derived_canonical_amount_and_metadata: Verifies Phase-50 checkout payload.
- test_validate_checkout_plan_blocks_device_limit_downgrade: Verifies incompatible lower-limit checkout guard.

CHANGE_SUMMARY
- 2026-06-02: Added Phase-50 canonical checkout and YooKassa metadata coverage.
- 2026-06-01: Updated trial creation expectations for Phase-45 pending activation.
- 2026-04-05: Added billing service tests for Phase 5.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.billing.models import (
    Payment,
    PaymentProvider,
    PaymentStatus,
    Plan,
    Subscription,
    SubscriptionStatus,
)
from app.billing.service import BillingService, CheckoutPlanRejected
from app.core.database import import_all_models
from app.devices.models import UserDevice


@pytest.fixture
async def billing_session():
    import_all_models()
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_create_trial_subscription_creates_pending_four_day_trial(billing_session: AsyncSession, monkeypatch):
    monkeypatch.setattr("app.billing.service.yookassa_client", None)
    monkeypatch.setattr("app.billing.service.settings.trial_days", 4)

    service = BillingService(billing_session)
    sub = await service.create_trial_subscription(user_id=1)

    assert sub.user_id == 1
    assert sub.is_trial is True
    assert sub.is_active is True
    assert sub.plan_id is None
    assert sub.pending_activation is True
    assert sub.activated_at is None
    assert sub.trial_duration_days == 4
    assert sub.expires_at == sub.started_at


@pytest.mark.asyncio
async def test_get_active_subscription_returns_none_when_no_subscription(billing_session: AsyncSession, monkeypatch):
    monkeypatch.setattr("app.billing.service.yookassa_client", None)

    service = BillingService(billing_session)
    result = await service.get_user_subscription(user_id=999)
    assert result is None


@pytest.mark.asyncio
async def test_get_active_subscription_returns_active_when_valid(billing_session: AsyncSession, monkeypatch):
    monkeypatch.setattr("app.billing.service.yookassa_client", None)

    now = datetime.now(timezone.utc)
    sub = Subscription(
        user_id=1,
        plan_id=None,
        status=SubscriptionStatus.ACTIVE,
        is_active=True,
        is_trial=False,
        started_at=now,
        expires_at=now + timedelta(days=30),
    )
    billing_session.add(sub)
    await billing_session.flush()

    service = BillingService(billing_session)
    result = await service.get_user_subscription(user_id=1)

    assert result is not None
    assert result.is_active is True
    assert result.user_id == 1


@pytest.mark.asyncio
async def test_expire_subscription_marks_inactive(billing_session: AsyncSession, monkeypatch):
    monkeypatch.setattr("app.billing.service.yookassa_client", None)

    now = datetime.now(timezone.utc)
    sub = Subscription(
        user_id=1,
        plan_id=None,
        status=SubscriptionStatus.ACTIVE,
        is_active=True,
        is_trial=False,
        started_at=now - timedelta(days=10),
        expires_at=now - timedelta(days=1),
    )
    billing_session.add(sub)
    await billing_session.flush()

    service = BillingService(billing_session)
    await service.deactivate_subscription(sub)

    assert sub.is_active is False
    assert sub.status == SubscriptionStatus.CANCELED


@pytest.mark.asyncio
async def test_payment_webhook_succeeded_creates_subscription(billing_session: AsyncSession, monkeypatch):
    monkeypatch.setattr("app.billing.service.yookassa_client", None)

    plan = Plan(
        name="Monthly",
        price=299.0,
        currency="RUB",
        duration_days=30,
        device_limit=2,
    )
    billing_session.add(plan)
    await billing_session.flush()

    payment = Payment(
        user_id=1,
        plan_id=int(plan.id),
        amount=plan.price,
        currency=plan.currency,
        provider=PaymentProvider.YOOKASSA,
        status=PaymentStatus.PENDING,
        external_id="ext-123",
    )
    billing_session.add(payment)
    await billing_session.flush()

    service = BillingService(billing_session)

    async def fake_get_user_client(user_id):
        return None

    async def fake_create_client(user_id):
        return None

    import app.vpn.service as vpn_mod
    class FakeVPNService:
        def __init__(self, session):
            pass
        async def get_user_client(self, user_id):
            return None
        async def create_client(self, user_id):
            return None
    monkeypatch.setattr(vpn_mod, "VPNService", FakeVPNService)

    webhook_data = {
        "event": "payment.succeeded",
        "object": {
            "id": "ext-123",
            "status": "succeeded",
        },
    }

    result = await service.process_payment_webhook(PaymentProvider.YOOKASSA, webhook_data)

    assert result is not None
    assert result.status == PaymentStatus.SUCCEEDED

    sub_result = await billing_session.execute(
        __import__("sqlalchemy").select(Subscription).where(Subscription.user_id == 1)
    )
    subs = list(sub_result.scalars().all())
    assert len(subs) >= 1
    assert any(s.is_active for s in subs)


@pytest.mark.asyncio
async def test_create_payment_uses_server_derived_canonical_amount_and_metadata(
    billing_session: AsyncSession,
):
    service = BillingService(billing_session)
    plans = await service.ensure_canonical_tariffs()
    plan = next(plan for plan in plans if plan.slug == "krotpn-6")
    captured: dict = {}

    class FakeYooKassa:
        async def create_payment(self, **kwargs):
            captured.update(kwargs)
            return {
                "id": "yk-phase50",
                "confirmation": {"url": "https://pay.example/phase50"},
            }

    service.yookassa = FakeYooKassa()
    payment = await service.create_payment(user_id=1, plan=plan, return_url="https://krotpn.xyz/subscription")

    assert payment.amount == 693.0
    assert payment.currency == "RUB"
    assert payment.external_id == "yk-phase50"
    assert captured["amount"] == 693.0
    assert captured["currency"] == "RUB"
    assert captured["metadata"]["plan_slug"] == "krotpn-6"
    assert captured["metadata"]["device_limit"] == 6
    assert captured["metadata"]["duration_days"] == 30
    assert "payment_id" in captured["metadata"]
    stored_metadata = json.loads(payment.payment_metadata or "{}")
    assert stored_metadata["payment_id"] == payment.id


@pytest.mark.asyncio
async def test_validate_checkout_plan_blocks_device_limit_downgrade(billing_session: AsyncSession):
    service = BillingService(billing_session)
    plans = await service.ensure_canonical_tariffs()
    one_device = next(plan for plan in plans if plan.slug == "krotpn-1")
    nine_devices = next(plan for plan in plans if plan.slug == "krotpn-9")

    for index in range(6):
        billing_session.add(
            UserDevice(
                user_id=7,
                name=f"device-{index}",
                platform="test",
            )
        )
    await billing_session.flush()

    with pytest.raises(CheckoutPlanRejected) as exc_info:
        await service.validate_checkout_plan(7, int(one_device.id))

    assert exc_info.value.reason == "device_limit_exceeded"
    assert exc_info.value.consumed_slots == 6
    assert exc_info.value.device_limit == 1

    allowed = await service.validate_checkout_plan(7, int(nine_devices.id))
    assert allowed.slug == "krotpn-9"
