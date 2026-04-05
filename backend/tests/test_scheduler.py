"""
MODULE_CONTRACT
- PURPOSE: Verify background scheduler tasks for subscription expiry, cleanup, and anomaly detection.
- SCOPE: Subscription expiry deactivation, server.current_clients decrement, daily cleanup, handshake anomaly detection.
- DEPENDS: app.tasks.scheduler, app.billing.models, app.vpn.models.
- LINKS: V-M-008.

MODULE_MAP
- test_subscription_expiry_deactivates_expired_subscriptions: Verifies expired subs are deactivated.
- test_subscription_expiry_decrements_server_current_clients: Verifies server counter decrement.
- test_daily_cleanup_does_not_crash: Verifies daily cleanup runs without errors.
- test_handshake_anomaly_detection_runs_without_errors: Verifies anomaly detection task runs.

CHANGE_SUMMARY
- 2026-04-05: Added scheduler task tests for Phase 5.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.billing.models import Subscription, SubscriptionStatus
from app.core.database import import_all_models
from app.vpn.models import VPNClient, VPNServer
from app.tasks import scheduler as scheduler_mod


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


class FakeSessionMaker:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        pass

    def __call__(self):
        return self


class FakeSessionMaker:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        pass

    def __call__(self):
        return self


@pytest.mark.asyncio
async def test_subscription_expiry_deactivates_expired_subscriptions(session: AsyncSession, monkeypatch):
    now = datetime.now(timezone.utc)
    expired_sub = Subscription(
        user_id=1,
        plan_id=None,
        status=SubscriptionStatus.ACTIVE,
        is_active=True,
        started_at=now - timedelta(days=60),
        expires_at=now - timedelta(days=1),
    )
    active_sub = Subscription(
        user_id=2,
        plan_id=None,
        status=SubscriptionStatus.ACTIVE,
        is_active=True,
        started_at=now - timedelta(days=10),
        expires_at=now + timedelta(days=20),
    )
    session.add(expired_sub)
    session.add(active_sub)
    await session.commit()

    mock_wg = AsyncMock()
    mock_wg.remove_peer = AsyncMock(return_value=True)
    monkeypatch.setattr(scheduler_mod, "async_session_maker", FakeSessionMaker(session))
    monkeypatch.setattr("app.vpn.amneziawg.wg_manager", mock_wg)

    await scheduler_mod.check_subscription_expiry()

    result = await session.execute(
        select(Subscription).where(Subscription.user_id == 1)
    )
    expired = result.scalar_one()
    assert expired.is_active is False
    assert expired.status == SubscriptionStatus.EXPIRED

    result = await session.execute(
        select(Subscription).where(Subscription.user_id == 2)
    )
    active = result.scalar_one()
    assert active.is_active is True


@pytest.mark.asyncio
async def test_subscription_expiry_decrements_server_current_clients(session: AsyncSession, monkeypatch):
    now = datetime.now(timezone.utc)

    server = VPNServer(
        name="Test Server",
        location="Test",
        endpoint="127.0.0.1",
        public_key="srv-pub-key",
        current_clients=5,
    )
    session.add(server)
    await session.commit()
    server_id = int(server.id)

    expired_sub = Subscription(
        user_id=1,
        plan_id=None,
        status=SubscriptionStatus.ACTIVE,
        is_active=True,
        started_at=now - timedelta(days=60),
        expires_at=now - timedelta(days=1),
    )
    session.add(expired_sub)
    await session.commit()

    client = VPNClient(
        user_id=1,
        public_key="client-pub-key",
        private_key_enc="enc-key",
        address="10.10.0.5",
        is_active=True,
        server_id=server_id,
    )
    session.add(client)
    await session.commit()

    mock_wg = AsyncMock()
    mock_wg.remove_peer = AsyncMock(return_value=True)
    monkeypatch.setattr(scheduler_mod, "async_session_maker", FakeSessionMaker(session))
    monkeypatch.setattr("app.vpn.amneziawg.wg_manager", mock_wg)

    await scheduler_mod.check_subscription_expiry()

    result = await session.execute(
        select(VPNServer).where(VPNServer.id == server_id)
    )
    updated_server = result.scalar_one()
    assert updated_server.current_clients == 4


@pytest.mark.asyncio
async def test_daily_cleanup_does_not_crash(session: AsyncSession, monkeypatch):
    monkeypatch.setattr(scheduler_mod, "async_session_maker", FakeSessionMaker(session))

    await scheduler_mod.daily_cleanup()


@pytest.mark.asyncio
async def test_handshake_anomaly_detection_runs_without_errors(session: AsyncSession, monkeypatch):
    mock_monitor = MagicMock()
    mock_monitor.scan_active_peers = AsyncMock(return_value=0)

    import app.vpn.handshake_monitor as hm_mod
    monkeypatch.setattr(hm_mod, "HandshakeAnomalyMonitor", lambda sess: mock_monitor)
    monkeypatch.setattr(scheduler_mod, "async_session_maker", FakeSessionMaker(session))

    await scheduler_mod.detect_handshake_anomalies()

    mock_monitor.scan_active_peers.assert_called_once()
