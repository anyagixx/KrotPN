"""
MODULE_CONTRACT
- PURPOSE: Verify observe-only handshake anomaly detection for device-bound peers.
- SCOPE: Device metadata updates, endpoint change tracking and durable anomaly-event creation.
- DEPENDS: M-001 database models, M-003 vpn clients, M-020 device-registry, M-023 handshake-anomaly-detector, M-025 device-audit-log.
- LINKS: V-M-023, V-M-025.

MODULE_MAP
- test_observe_peer_stats_updates_device_presence_metadata: Verifies live handshake observation refreshes endpoint and seen timestamps.
- test_observe_peer_stats_records_endpoint_churn_and_concurrency_signals: Verifies quick endpoint changes emit warning-level anomaly events without blocking the peer.

CHANGE_SUMMARY
- 2026-03-27: Added tests for endpoint churn and concurrent-handshake suspicion in observe-only mode.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.core.database import import_all_models
from app.devices.models import DeviceSecurityEvent, DeviceSecurityEventType, DeviceStatus, UserDevice
from app.users.models import User, UserRole
from app.vpn.handshake_monitor import HandshakeAnomalyMonitor
from app.vpn.models import VPNClient


@pytest.fixture
async def device_monitor_session():
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


async def _seed_device_bound_client(session: AsyncSession) -> tuple[UserDevice, VPNClient]:
    user = User(
        email="device@example.com",
        password_hash="hash",
        role=UserRole.USER,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    device = UserDevice(
        user_id=int(user.id),
        device_key="device-1",
        name="iPhone",
        platform="ios",
        status=DeviceStatus.ACTIVE,
    )
    session.add(device)
    await session.flush()

    client = VPNClient(
        user_id=int(user.id),
        device_id=int(device.id),
        public_key="peer-public-key",
        private_key_enc="enc",
        address="10.10.0.2",
        is_active=True,
    )
    session.add(client)
    await session.flush()
    return device, client


@pytest.mark.asyncio
async def test_observe_peer_stats_updates_device_presence_metadata(device_monitor_session: AsyncSession):
    device, client = await _seed_device_bound_client(device_monitor_session)
    monitor = HandshakeAnomalyMonitor(device_monitor_session)
    observed_at = datetime.now(timezone.utc)

    processed = await monitor.observe_peer_stats(
        {
            client.public_key: {
                "last_handshake": observed_at,
                "endpoint": "198.51.100.7:51820",
                "upload": 1024,
                "download": 2048,
            }
        }
    )
    await device_monitor_session.refresh(device)

    assert processed == 1
    assert device.last_endpoint == "198.51.100.7:51820"
    assert device.last_seen_at is not None
    assert device.last_handshake_at is not None
    assert device.last_seen_at.tzinfo is None
    assert device.last_handshake_at.tzinfo is None


@pytest.mark.asyncio
async def test_observe_peer_stats_records_endpoint_churn_and_concurrency_signals(device_monitor_session: AsyncSession):
    device, client = await _seed_device_bound_client(device_monitor_session)
    previous_handshake = datetime.now(timezone.utc) - timedelta(seconds=45)
    device.last_endpoint = "203.0.113.1:51820"
    device.last_seen_at = previous_handshake
    device.last_handshake_at = previous_handshake
    await device_monitor_session.flush()

    monitor = HandshakeAnomalyMonitor(device_monitor_session)
    await monitor.observe_peer_stats(
        {
            client.public_key: {
                "last_handshake": datetime.now(timezone.utc),
                "endpoint": "198.51.100.7:51820",
                "upload": 2048,
                "download": 4096,
            }
        }
    )

    result = await device_monitor_session.execute(
        select(DeviceSecurityEvent.event_type).where(DeviceSecurityEvent.device_id == device.id)
    )
    event_types = list(result.scalars().all())

    assert DeviceSecurityEventType.SUSPICIOUS_ENDPOINT_CHURN in event_types
    assert DeviceSecurityEventType.CONCURRENT_HANDSHAKE_SUSPECTED in event_types
