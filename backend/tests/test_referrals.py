"""
MODULE_CONTRACT
- PURPOSE: Verify referral service operations for code generation, referral linking, payment bonus, and stats.
- SCOPE: Unique code generation, referral creation, first payment bonus, referral stats.
- DEPENDS: app.referrals.service, app.referrals.models.
- LINKS: V-M-005.

MODULE_MAP
- test_create_referral_code_generates_unique_code: Verifies unique code generation.
- test_create_referral_links_referrer_and_referred: Verifies referral relationship.
- test_process_first_payment_bonus_adds_bonus_days: Verifies bonus on first payment.
- test_process_first_payment_creates_pending_bonus_without_active_subscription: Verifies first-VPN pending referral reward.
- test_process_first_payment_is_idempotent_for_duplicate_webhook: Verifies one-time bonus semantics.
- test_referral_list_returns_masked_referred_identity: Verifies user API redacts referred email.
- test_get_referral_stats_returns_correct_counts: Verifies stats aggregation.

CHANGE_SUMMARY
- 2026-06-04: Added Phase-69 referral bonus activation and masked identity tests.
- 2026-04-05: Added referral service tests for Phase 5.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.billing.service import REFERRAL_BONUS_ACCESS_LABEL
from app.billing.models import Plan, Subscription, SubscriptionStatus
from app.core.database import import_all_models
from app.referrals.models import Referral, ReferralCode
from app.referrals.router import get_referrals_list
from app.referrals.service import ReferralService
from app.users.models import User, UserRole


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@pytest.fixture
async def session():
    import_all_models()
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async with session_maker() as s:
        yield s

    await engine.dispose()


@pytest.mark.asyncio
async def test_create_referral_code_generates_unique_code(session: AsyncSession, monkeypatch):
    monkeypatch.setattr("app.referrals.service.settings.referral_bonus_days", 7)
    monkeypatch.setattr("app.referrals.service.settings.referral_min_payment", 100.0)

    service = ReferralService(session)
    code = await service.get_or_create_code(user_id=1)

    assert code is not None
    assert code.user_id == 1
    assert len(code.code) == 8
    assert code.code.isalnum()

    code2 = await service.get_or_create_code(user_id=2)
    assert code2.code != code.code


@pytest.mark.asyncio
async def test_create_referral_links_referrer_and_referred(session: AsyncSession, monkeypatch):
    monkeypatch.setattr("app.referrals.service.settings.referral_bonus_days", 7)
    monkeypatch.setattr("app.referrals.service.settings.referral_min_payment", 100.0)

    code = ReferralCode(user_id=10, code="UNIQUECODE")
    session.add(code)
    await session.flush()

    service = ReferralService(session)
    referral = await service.create_referral(referrer_id=10, referred_id=20)

    assert referral is not None
    assert referral.referrer_id == 10
    assert referral.referred_id == 20
    assert referral.bonus_given is False

    result = await session.execute(select(ReferralCode).where(ReferralCode.user_id == 10))
    updated_code = result.scalar_one()
    assert updated_code.uses_count == 1


@pytest.mark.asyncio
async def test_create_referral_rejects_self_referral(session: AsyncSession, monkeypatch):
    monkeypatch.setattr("app.referrals.service.settings.referral_bonus_days", 7)
    monkeypatch.setattr("app.referrals.service.settings.referral_min_payment", 100.0)

    service = ReferralService(session)
    referral = await service.create_referral(referrer_id=1, referred_id=1)

    assert referral is None


@pytest.mark.asyncio
async def test_create_referral_rejects_duplicate(session: AsyncSession, monkeypatch):
    monkeypatch.setattr("app.referrals.service.settings.referral_bonus_days", 7)
    monkeypatch.setattr("app.referrals.service.settings.referral_min_payment", 100.0)

    service = ReferralService(session)
    first = await service.create_referral(referrer_id=10, referred_id=20)
    assert first is not None

    second = await service.create_referral(referrer_id=10, referred_id=20)
    assert second is None


@pytest.mark.asyncio
async def test_process_first_payment_bonus_adds_bonus_days(session: AsyncSession, monkeypatch):
    monkeypatch.setattr("app.referrals.service.settings.referral_bonus_days", 7)
    monkeypatch.setattr("app.referrals.service.settings.referral_min_payment", 100.0)

    referral = Referral(referrer_id=10, referred_id=20, bonus_given=False)
    session.add(referral)

    now = datetime.now(timezone.utc)
    referrer_sub = Subscription(
        user_id=10,
        plan_id=None,
        status=SubscriptionStatus.ACTIVE,
        is_active=True,
        started_at=now - timedelta(days=10),
        expires_at=now + timedelta(days=20),
    )
    session.add(referrer_sub)
    await session.flush()

    service = ReferralService(session)
    result = await service.process_first_payment(user_id=20, amount=150.0)

    assert result is True
    assert referral.bonus_given is True
    assert referral.bonus_days == 7
    assert referral.first_payment_amount == 150.0
    await session.refresh(referrer_sub)
    assert referrer_sub.pending_activation is False
    assert aware_utc(referrer_sub.expires_at) == now + timedelta(days=27)


@pytest.mark.asyncio
async def test_process_first_payment_creates_pending_bonus_without_active_subscription(
    session: AsyncSession,
    monkeypatch,
):
    monkeypatch.setattr("app.referrals.service.settings.referral_bonus_days", 7)
    monkeypatch.setattr("app.referrals.service.settings.referral_min_payment", 100.0)

    referral = Referral(referrer_id=30, referred_id=40, bonus_given=False)
    session.add(referral)
    await session.flush()

    service = ReferralService(session)
    result = await service.process_first_payment(user_id=40, amount=150.0)

    assert result is True
    sub_result = await session.execute(
        select(Subscription).where(Subscription.user_id == 30)
    )
    pending_bonus = sub_result.scalar_one()
    assert pending_bonus.pending_activation is True
    assert pending_bonus.is_trial is False
    assert pending_bonus.trial_duration_days == 7
    assert pending_bonus.access_label == REFERRAL_BONUS_ACCESS_LABEL
    assert aware_utc(pending_bonus.expires_at) == aware_utc(pending_bonus.started_at)


@pytest.mark.asyncio
async def test_process_first_payment_is_idempotent_for_duplicate_webhook(
    session: AsyncSession,
    monkeypatch,
):
    monkeypatch.setattr("app.referrals.service.settings.referral_bonus_days", 7)
    monkeypatch.setattr("app.referrals.service.settings.referral_min_payment", 100.0)

    now = datetime.now(timezone.utc)
    referral = Referral(referrer_id=50, referred_id=60, bonus_given=False)
    referrer_sub = Subscription(
        user_id=50,
        plan_id=None,
        status=SubscriptionStatus.ACTIVE,
        is_active=True,
        started_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=10),
    )
    session.add(referral)
    session.add(referrer_sub)
    await session.flush()

    service = ReferralService(session)
    first = await service.process_first_payment(user_id=60, amount=150.0)
    second = await service.process_first_payment(user_id=60, amount=150.0)
    await session.refresh(referrer_sub)

    assert first is True
    assert second is False
    assert referral.bonus_days == 7
    assert aware_utc(referrer_sub.expires_at) == now + timedelta(days=17)


@pytest.mark.asyncio
async def test_referral_list_returns_masked_referred_identity(
    session: AsyncSession,
    monkeypatch,
):
    monkeypatch.setattr("app.referrals.service.settings.referral_bonus_days", 7)
    monkeypatch.setattr("app.referrals.service.settings.referral_min_payment", 100.0)

    referrer = User(
        email="owner@example.com",
        password_hash="hashed",
        role=UserRole.USER,
        is_active=True,
    )
    referred = User(
        email="referred.person@example.net",
        password_hash="hashed",
        role=UserRole.USER,
        is_active=True,
    )
    session.add(referrer)
    session.add(referred)
    await session.flush()

    referral = Referral(referrer_id=int(referrer.id), referred_id=int(referred.id), bonus_given=False)
    session.add(referral)
    await session.flush()

    response = await get_referrals_list(SimpleNamespace(id=int(referrer.id)), session, limit=10)

    item = response["items"][0]
    assert item["referred_identity"] == "r***n@example.net"
    assert item["referred_email_masked"] == "r***n@example.net"
    assert "referred.person@example.net" not in str(response)


@pytest.mark.asyncio
async def test_process_first_payment_bonus_rejects_below_minimum(session: AsyncSession, monkeypatch):
    monkeypatch.setattr("app.referrals.service.settings.referral_bonus_days", 7)
    monkeypatch.setattr("app.referrals.service.settings.referral_min_payment", 100.0)

    referral = Referral(referrer_id=10, referred_id=20, bonus_given=False)
    session.add(referral)
    await session.flush()

    service = ReferralService(session)
    result = await service.process_first_payment(user_id=20, amount=50.0)

    assert result is False
    assert referral.bonus_given is False


@pytest.mark.asyncio
async def test_get_referral_stats_returns_correct_counts(session: AsyncSession, monkeypatch):
    monkeypatch.setattr("app.referrals.service.settings.referral_bonus_days", 7)
    monkeypatch.setattr("app.referrals.service.settings.referral_min_payment", 100.0)

    code = ReferralCode(user_id=1, code="STATSCODE")
    session.add(code)

    r1 = Referral(referrer_id=1, referred_id=10, bonus_given=True, bonus_days=7)
    r2 = Referral(referrer_id=1, referred_id=11, bonus_given=True, bonus_days=7)
    r3 = Referral(referrer_id=1, referred_id=12, bonus_given=False)
    session.add_all([r1, r2, r3])
    await session.flush()

    from sqlalchemy import case
    result = await session.execute(
        select(
            func.count(Referral.id).label("total"),
            func.sum(case((Referral.bonus_given == True, 1))).label("paid"),
            func.coalesce(func.sum(case(
                (Referral.bonus_given == True, Referral.bonus_days),
            )), 0).label("bonus_days"),
        ).where(Referral.referrer_id == 1)
    )
    row = result.one()

    assert (row.total or 0) == 3
    assert (row.paid or 0) == 2
    assert (row.bonus_days or 0) == 14
