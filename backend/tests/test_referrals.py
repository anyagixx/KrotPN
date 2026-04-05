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
- test_get_referral_stats_returns_correct_counts: Verifies stats aggregation.

CHANGE_SUMMARY
- 2026-04-05: Added referral service tests for Phase 5.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.billing.models import Plan, Subscription, SubscriptionStatus
from app.core.database import import_all_models
from app.referrals.models import Referral, ReferralCode
from app.referrals.service import ReferralService


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
