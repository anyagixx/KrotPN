"""
MODULE_CONTRACT
- PURPOSE: Verify observe-only handshake anomaly detection for device-bound peers.
- SCOPE: Device metadata updates, endpoint roaming tolerance and durable anti-ping-pong event creation.
- DEPENDS: M-001 database models, M-003 vpn clients, M-020 device-registry, M-023 handshake-anomaly-detector, M-025 device-audit-log, M-031 anti-ping-pong-abuse.
- LINKS: V-M-023, V-M-025, V-M-031.

MODULE_MAP
- test_observe_peer_stats_updates_device_presence_metadata: Verifies live handshake observation refreshes endpoint and seen timestamps.
- test_observe_peer_stats_treats_single_endpoint_change_as_roaming: Verifies one IP transition does not emit abuse events.
- test_observe_peer_stats_records_ping_pong_signal: Verifies A-B-A-B endpoint alternation emits anti-abuse evidence.

CHANGE_SUMMARY
- 2026-04-20: Replaced naive endpoint-churn assertions with anti-ping-pong observe-mode coverage.
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
from app.vpn.anti_abuse import (
    AntiAbuseAnalyzer,
    AntiAbuseConfig,
    AntiAbuseMode,
    InMemoryEndpointHistoryStore,
)
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


def _build_observe_monitor(session: AsyncSession) -> HandshakeAnomalyMonitor:
    analyzer = AntiAbuseAnalyzer(
        store=InMemoryEndpointHistoryStore(),
        config=AntiAbuseConfig(
            mode=AntiAbuseMode.OBSERVE,
            history_window_seconds=300,
            history_ttl_seconds=900,
            pingpong_window_seconds=180,
            pingpong_min_alternations=4,
            unique_ip_threshold=4,
            enforcement_cooldown_seconds=900,
        ),
    )
    return HandshakeAnomalyMonitor(session, analyzer=analyzer)


async def _observe_endpoint(
    monitor: HandshakeAnomalyMonitor,
    client: VPNClient,
    *,
    endpoint: str,
    observed_at: datetime,
) -> int:
    return await monitor.observe_peer_stats(
        {
            client.public_key: {
                "last_handshake": observed_at,
                "endpoint": endpoint,
                "upload": 2048,
                "download": 4096,
            }
        }
    )


@pytest.mark.asyncio
async def test_observe_peer_stats_updates_device_presence_metadata(device_monitor_session: AsyncSession):
    device, client = await _seed_device_bound_client(device_monitor_session)
    monitor = _build_observe_monitor(device_monitor_session)
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
async def test_observe_peer_stats_treats_single_endpoint_change_as_roaming(device_monitor_session: AsyncSession):
    device, client = await _seed_device_bound_client(device_monitor_session)
    monitor = _build_observe_monitor(device_monitor_session)
    observed_at = datetime.now(timezone.utc)

    await _observe_endpoint(
        monitor,
        client,
        endpoint="203.0.113.1:51820",
        observed_at=observed_at,
    )
    await _observe_endpoint(
        monitor,
        client,
        endpoint="198.51.100.7:51820",
        observed_at=observed_at + timedelta(seconds=45),
    )

    result = await device_monitor_session.execute(
        select(DeviceSecurityEvent.event_type).where(DeviceSecurityEvent.device_id == device.id)
    )
    event_types = list(result.scalars().all())

    assert DeviceSecurityEventType.PING_PONG_ABUSE_DETECTED not in event_types
    assert DeviceSecurityEventType.MULTI_NETWORK_ABUSE_DETECTED not in event_types
    assert DeviceSecurityEventType.SUSPICIOUS_ENDPOINT_CHURN not in event_types
    assert DeviceSecurityEventType.CONCURRENT_HANDSHAKE_SUSPECTED not in event_types


@pytest.mark.asyncio
async def test_observe_peer_stats_records_ping_pong_signal(device_monitor_session: AsyncSession):
    device, client = await _seed_device_bound_client(device_monitor_session)
    monitor = _build_observe_monitor(device_monitor_session)
    observed_at = datetime.now(timezone.utc)

    for index, endpoint in enumerate(
        [
            "203.0.113.1:51820",
            "198.51.100.7:51820",
            "203.0.113.1:51820",
            "198.51.100.7:51820",
        ]
    ):
        await _observe_endpoint(
            monitor,
            client,
            endpoint=endpoint,
            observed_at=observed_at + timedelta(seconds=index * 30),
        )

    result = await device_monitor_session.execute(
        select(DeviceSecurityEvent.event_type).where(DeviceSecurityEvent.device_id == device.id)
    )
    event_types = list(result.scalars().all())

    assert DeviceSecurityEventType.PING_PONG_ABUSE_DETECTED in event_types
