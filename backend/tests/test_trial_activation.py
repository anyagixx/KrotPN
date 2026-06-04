"""Phase-45 trial activation tests.

# FILE: backend/tests/test_trial_activation.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify pending free-trial creation and first VPN handshake activation semantics
#   SCOPE: BillingService pending trial lifecycle, subscription countdown API, and scheduler activation scan
#   DEPENDS: M-004, M-003, M-008, M-063
#   LINKS: V-M-063
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   FakeSessionMaker - Async context wrapper for scheduler tests
#   test_pending_trial_is_access_bearing_without_running_countdown - Verifies pending trial state
#   test_first_handshake_activates_trial_once - Verifies idempotent four-day activation
#   test_first_handshake_activates_pending_referral_bonus_once - Verifies Phase-69 referral reward activation
#   test_paid_subscription_blocks_pending_trial_activation - Verifies paid access is not overwritten
#   test_subscription_status_exposes_pending_and_countdown_fields - Verifies API response shape
#   test_scheduler_activates_pending_trial_from_client_handshake - Verifies scheduler scan
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.1.0 - Added Phase-69 pending referral-bonus activation regression coverage
#   LAST_CHANGE: v1.0.0 - Added Phase-45 pending trial activation regression coverage
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.models import Plan, Subscription, SubscriptionStatus
from app.billing.router import get_subscription_status
from app.billing.service import BillingService, REFERRAL_BONUS_ACCESS_LABEL
from app.tasks import scheduler as scheduler_mod
from app.vpn.models import VPNClient


# START_BLOCK_PHASE45_TEST_HELPERS
class FakeSessionMaker:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        pass

    def __call__(self):
        return self


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
# END_BLOCK_PHASE45_TEST_HELPERS


# START_BLOCK_PHASE45_TRIAL_ACTIVATION_TESTS
@pytest.mark.asyncio
async def test_pending_trial_is_access_bearing_without_running_countdown(
    db_session: AsyncSession,
    monkeypatch,
):
    monkeypatch.setattr("app.billing.service.settings.trial_days", 4)
    service = BillingService(db_session)

    subscription = await service.create_pending_trial(user_id=1)

    assert subscription.is_active is True
    assert subscription.is_trial is True
    assert subscription.pending_activation is True
    assert subscription.activated_at is None
    assert subscription.trial_duration_days == 4
    assert subscription.expires_at == subscription.started_at
    assert await service.get_user_subscription(1) is not None
    assert await service.get_user_subscription(1, include_pending=False) is None
    assert await service.get_effective_device_limit(1) == 1


@pytest.mark.asyncio
async def test_first_handshake_activates_trial_once(db_session: AsyncSession, monkeypatch):
    monkeypatch.setattr("app.billing.service.settings.trial_days", 4)
    service = BillingService(db_session)
    subscription = await service.create_pending_trial(user_id=2)
    handshake_at = datetime.now(timezone.utc) + timedelta(minutes=3)

    activated = await service.activate_trial_on_first_vpn_handshake(
        user_id=2,
        handshake_at=handshake_at,
        client_id=20,
    )

    assert activated is not None
    assert activated.pending_activation is False
    assert aware_utc(activated.activated_at) == handshake_at
    assert aware_utc(activated.started_at) == handshake_at
    assert aware_utc(activated.expires_at) == handshake_at + timedelta(days=4)

    first_expires_at = activated.expires_at
    second = await service.activate_trial_on_first_vpn_handshake(
        user_id=2,
        handshake_at=handshake_at + timedelta(hours=12),
        client_id=20,
    )
    await db_session.refresh(subscription)

    assert second is None
    assert aware_utc(subscription.expires_at) == aware_utc(first_expires_at)


@pytest.mark.asyncio
async def test_first_handshake_activates_pending_referral_bonus_once(db_session: AsyncSession):
    service = BillingService(db_session)
    subscription = await service.grant_referral_bonus_days(user_id=29, days=7)
    handshake_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    activated = await service.activate_trial_on_first_vpn_handshake(
        user_id=29,
        handshake_at=handshake_at,
        client_id=290,
    )
    second = await service.activate_trial_on_first_vpn_handshake(
        user_id=29,
        handshake_at=handshake_at + timedelta(hours=3),
        client_id=290,
    )
    await db_session.refresh(subscription)

    assert activated is not None
    assert second is None
    assert subscription.is_trial is False
    assert subscription.status == SubscriptionStatus.ACTIVE
    assert subscription.access_label == REFERRAL_BONUS_ACCESS_LABEL
    assert subscription.pending_activation is False
    assert aware_utc(subscription.activated_at) == handshake_at
    assert aware_utc(subscription.expires_at) == handshake_at + timedelta(days=7)


@pytest.mark.asyncio
async def test_paid_subscription_blocks_pending_trial_activation(db_session: AsyncSession):
    now = datetime.now(timezone.utc)
    pending = Subscription(
        user_id=3,
        plan_id=None,
        status=SubscriptionStatus.TRIAL,
        is_active=True,
        is_trial=True,
        pending_activation=True,
        trial_duration_days=4,
        started_at=now,
        expires_at=now,
    )
    paid = Subscription(
        user_id=3,
        plan_id=None,
        status=SubscriptionStatus.ACTIVE,
        is_active=True,
        is_trial=False,
        pending_activation=False,
        started_at=now,
        expires_at=now + timedelta(days=30),
    )
    db_session.add(pending)
    db_session.add(paid)
    await db_session.flush()
    service = BillingService(db_session)

    result = await service.activate_trial_on_first_vpn_handshake(
        user_id=3,
        handshake_at=now + timedelta(minutes=1),
        client_id=30,
    )
    await db_session.refresh(pending)
    await db_session.refresh(paid)

    assert result is None
    assert pending.pending_activation is True
    assert aware_utc(paid.expires_at) == now + timedelta(days=30)


@pytest.mark.asyncio
async def test_subscription_status_exposes_pending_and_countdown_fields(
    db_session: AsyncSession,
    monkeypatch,
):
    monkeypatch.setattr("app.billing.service.settings.trial_days", 4)
    service = BillingService(db_session)
    await service.create_pending_trial(user_id=4)

    pending_response = await get_subscription_status(SimpleNamespace(id=4), db_session)

    assert pending_response.has_subscription is True
    assert pending_response.is_active is False
    assert pending_response.pending_activation is True
    assert pending_response.expires_at is None
    assert pending_response.remaining_seconds == 0

    handshake_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    await service.activate_trial_on_first_vpn_handshake(4, handshake_at, client_id=40)

    active_response = await get_subscription_status(SimpleNamespace(id=4), db_session)

    assert active_response.pending_activation is False
    assert active_response.is_active is True
    assert active_response.remaining_seconds > 0
    assert active_response.remaining_days == 3
    assert active_response.remaining_hours >= 23
    assert active_response.active_from == handshake_at
    assert active_response.active_until == handshake_at + timedelta(days=4)


@pytest.mark.asyncio
async def test_scheduler_activates_pending_trial_from_client_handshake(
    db_session: AsyncSession,
    monkeypatch,
):
    monkeypatch.setattr("app.billing.service.settings.trial_days", 4)
    monkeypatch.setattr(scheduler_mod, "async_session_maker", FakeSessionMaker(db_session))
    service = BillingService(db_session)
    await service.create_pending_trial(user_id=5)
    handshake_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    client = VPNClient(
        user_id=5,
        public_key="phase45-client-pub-key",
        private_key_enc="enc-key",
        address="10.45.0.5",
        is_active=True,
        last_handshake_at=handshake_at,
    )
    db_session.add(client)
    await db_session.flush()

    result = await scheduler_mod.activate_pending_trials()

    assert result["scanned"] == 1
    assert result["activated"] == 1
    subscription = await service.get_user_subscription(5)
    assert subscription is not None
    assert subscription.pending_activation is False
    assert aware_utc(subscription.expires_at) == handshake_at + timedelta(days=4)


@pytest.mark.asyncio
async def test_create_paid_subscription_cancels_pending_trial(db_session: AsyncSession):
    service = BillingService(db_session)
    await service.create_pending_trial(user_id=6)
    plan = Plan(
        name="Monthly",
        price=299.0,
        currency="RUB",
        duration_days=30,
        device_limit=2,
    )
    db_session.add(plan)
    await db_session.flush()

    paid = await service.create_subscription(user_id=6, plan=plan)

    assert paid.is_trial is False
    assert paid.pending_activation is False
    active = await service.get_user_subscription(6, include_pending=False)
    assert active is not None
    assert active.id == paid.id
# END_BLOCK_PHASE45_TRIAL_ACTIVATION_TESTS
