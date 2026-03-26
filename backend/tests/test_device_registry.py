"""
MODULE_CONTRACT
- PURPOSE: Verify the device registry persists user devices and durable device security events with stable lifecycle defaults.
- SCOPE: Model persistence, default values, device linkage and audit event storage.
- DEPENDS: M-001 async SQLModel setup, M-002 user model, M-020 device-registry, M-025 device-audit-log.
- LINKS: V-M-020, V-M-025.

MODULE_MAP
- session: In-memory async DB session fixture for device registry tests.
- test_user_device_defaults_and_relationships: Verifies default device state and event linkage persistence.

CHANGE_SUMMARY
- 2026-03-27: Added device registry tests for first-class device and audit-event persistence.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select

from app.core.database import import_all_models
from app.devices.models import (
    DeviceEventSeverity,
    DeviceSecurityEvent,
    DeviceSecurityEventType,
    DeviceStatus,
    UserDevice,
)
from app.users.models import User


@pytest.fixture
async def session() -> AsyncSession:
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

    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_user_device_defaults_and_relationships(session: AsyncSession):
    user = User(email="device-owner@example.com", password_hash="hash")
    session.add(user)
    await session.flush()

    device = UserDevice(
        user_id=int(user.id),
        name="iPhone",
        platform="ios",
    )
    session.add(device)
    await session.flush()

    event = DeviceSecurityEvent(
        user_id=int(user.id),
        device_id=int(device.id),
        event_type=DeviceSecurityEventType.DEVICE_CREATED,
        severity=DeviceEventSeverity.INFO,
        details_json='{"source":"test"}',
    )
    session.add(event)
    await session.commit()

    stored_device = await session.get(UserDevice, int(device.id))
    assert stored_device is not None
    assert stored_device.status is DeviceStatus.ACTIVE
    assert stored_device.config_version == 1
    assert stored_device.device_key

    stored_events = (
        await session.execute(
            select(DeviceSecurityEvent).where(DeviceSecurityEvent.device_id == int(device.id))
        )
    ).scalars().all()
    assert len(stored_events) == 1
    assert stored_events[0].event_type is DeviceSecurityEventType.DEVICE_CREATED
