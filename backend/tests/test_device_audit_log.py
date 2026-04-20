"""
MODULE_CONTRACT
- PURPOSE: Verify that device lifecycle and enforcement actions leave a durable audit trail.
- SCOPE: DeviceSecurityEvent ordering and event coverage for create, rotate, block, unblock and revoke transitions.
- DEPENDS: M-001 database/session wiring, M-004 billing access state, M-020 device-registry, M-021 device-access-policy, M-025 device-audit-log.
- LINKS: V-M-025.

MODULE_MAP
- test_device_policy_writes_full_audit_sequence: Verifies one device accumulates the expected lifecycle and enforcement events.
- test_get_recent_event_types_returns_newest_first: Verifies audit-log helpers expose compact recent event markers in descending order.
- test_get_recent_event_types_includes_anti_abuse_events: Verifies durable anti-abuse event types are exposed by audit helpers.

CHANGE_SUMMARY
- 2026-04-20: Added audit-log coverage for anti-abuse event types.
- 2026-03-27: Added device audit-log tests for lifecycle and admin-enforcement transitions.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.billing.models import Plan, Subscription, SubscriptionStatus
from app.core.database import import_all_models
from app.devices.models import DeviceEventSeverity, DeviceSecurityEvent, DeviceSecurityEventType
from app.devices.service import DeviceAccessPolicyService
from app.users.models import User, UserRole


class StubVPNService:
    def __init__(self):
        self.deactivated_device_ids: list[int] = []

    async def deactivate_device_clients(self, device_id: int) -> int:
        self.deactivated_device_ids.append(device_id)
        return 1


@pytest.fixture
async def audit_session():
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


async def _seed_user_with_subscription(session: AsyncSession) -> int:
    user = User(
        email="audit@example.com",
        password_hash="hash",
        role=UserRole.USER,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    plan = Plan(
        name="Audit plan",
        price=299,
        duration_days=30,
        features='["vpn"]',
        is_active=True,
        device_limit=3,
    )
    session.add(plan)
    await session.flush()

    subscription = Subscription(
        user_id=int(user.id),
        plan_id=int(plan.id),
        status=SubscriptionStatus.ACTIVE,
        started_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=30),
        is_active=True,
        is_trial=False,
    )
    session.add(subscription)
    await session.flush()
    return int(user.id)


@pytest.mark.asyncio
async def test_device_policy_writes_full_audit_sequence(audit_session: AsyncSession):
    user_id = await _seed_user_with_subscription(audit_session)
    policy = DeviceAccessPolicyService(audit_session)
    policy.vpn = StubVPNService()

    device = await policy.create_device_record(user_id, name="MacBook", platform="macos")
    await policy.rotate_device_config(device, reason="user_rotate")
    await policy.block_device(device, reason="admin_block")
    await policy.unblock_device(device, reason="admin_unblock")
    await policy.revoke_device(device, reason="user_request")

    event_types = await policy.get_recent_event_types(int(device.id), limit=10)

    assert DeviceSecurityEventType.DEVICE_REVOKED.value in event_types
    assert DeviceSecurityEventType.DEVICE_UNBLOCKED.value in event_types
    assert DeviceSecurityEventType.DEVICE_BLOCKED.value in event_types
    assert DeviceSecurityEventType.CONFIG_ROTATED.value in event_types
    assert DeviceSecurityEventType.DEVICE_CREATED.value in event_types


@pytest.mark.asyncio
async def test_get_recent_event_types_returns_newest_first(audit_session: AsyncSession):
    user_id = await _seed_user_with_subscription(audit_session)
    policy = DeviceAccessPolicyService(audit_session)
    policy.vpn = StubVPNService()

    device = await policy.create_device_record(user_id, name="iPhone", platform="ios")
    await policy.rotate_device_config(device, reason="first_rotate")
    await policy.block_device(device, reason="admin_block")

    recent = await policy.get_recent_event_types(int(device.id), limit=3)

    assert recent == [
        DeviceSecurityEventType.DEVICE_BLOCKED.value,
        DeviceSecurityEventType.CONFIG_ROTATED.value,
        DeviceSecurityEventType.DEVICE_CREATED.value,
    ]


@pytest.mark.asyncio
async def test_get_recent_event_types_includes_anti_abuse_events(audit_session: AsyncSession):
    user_id = await _seed_user_with_subscription(audit_session)
    policy = DeviceAccessPolicyService(audit_session)
    policy.vpn = StubVPNService()

    device = await policy.create_device_record(user_id, name="Android", platform="android")
    audit_session.add(
        DeviceSecurityEvent(
            user_id=user_id,
            device_id=int(device.id),
            event_type=DeviceSecurityEventType.PING_PONG_ABUSE_DETECTED,
            severity=DeviceEventSeverity.WARNING,
            details_json='{"decision":"ping_pong_abuse"}',
        )
    )
    await audit_session.flush()

    recent = await policy.get_recent_event_types(int(device.id), limit=2)

    assert recent[0] == DeviceSecurityEventType.PING_PONG_ABUSE_DETECTED.value
