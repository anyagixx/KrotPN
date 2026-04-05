"""
MODULE_CONTRACT
- PURPOSE: Verify billing service operations for subscriptions and payments.
- SCOPE: Trial creation, active subscription lookup, expiry, payment webhook processing.
- DEPENDS: app.billing.service, app.billing.models.
- LINKS: V-M-004.

MODULE_MAP
- test_create_trial_subscription_creates_correct_duration: Verifies trial subscription duration.
- test_get_active_subscription_returns_none_when_no_subscription: Verifies empty lookup.
- test_get_active_subscription_returns_active_when_valid: Verifies active subscription lookup.
- test_expire_subscription_marks_inactive: Verifies deactivation.
- test_payment_webhook_succeeded_creates_subscription: Verifies happy-path webhook.

CHANGE_SUMMARY
- 2026-04-05: Added billing service tests for Phase 5.
"""

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
from app.billing.service import BillingService
from app.core.database import import_all_models


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
async def test_create_trial_subscription_creates_correct_duration(billing_session: AsyncSession, monkeypatch):
    monkeypatch.setattr("app.billing.service.yookassa_client", None)

    service = BillingService(billing_session)
    sub = await service.create_trial_subscription(user_id=1)

    assert sub.user_id == 1
    assert sub.is_trial is True
    assert sub.is_active is True
    assert sub.plan_id is None
    assert sub.expires_at > sub.started_at
    delta = sub.expires_at - sub.started_at
    assert delta.days == 3


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
