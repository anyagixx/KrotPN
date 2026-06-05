"""
# START_MODULE_CONTRACT
- PURPOSE: Verify Phase-78 VPN device abuse alert inbox service behavior.
- SCOPE: Alert creation/dedupe, ignored non-abuse events, safe serialization, resolved archive, confirmation guards, and one-device rotate/block actions.
- DEPENDS: M-001 database models, M-020 device registry, M-025 audit log, M-031 anti-abuse events, M-081 alert inbox.
- LINKS: V-M-081.
# END_MODULE_CONTRACT

# START_MODULE_MAP
- device_abuse_alert_session: In-memory SQLModel session with all models registered.
- _seed_user_device: Create one user/device pair for alert tests.
- _record_event: Persist one device security event.
- test_confirmed_abuse_event_creates_and_dedupes_open_alert: Verifies ping-pong alert creation and dedupe.
- test_non_confirmed_events_do_not_create_alerts: Verifies warning/degraded/normal events do not enter inbox.
- test_resolve_archives_without_changing_device: Verifies review-only resolution has no VPN device side effect.
- test_rotate_and_block_alert_actions_require_confirmation_and_target_one_device: Verifies confirmed actions affect only the alert device.
- test_serialized_alert_payload_is_redacted: Verifies admin payload excludes config/key markers.
# END_MODULE_MAP

# START_CHANGE_SUMMARY
- 2026-06-06: Added Phase-78 VPN device abuse alert inbox tests.
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.core.database import import_all_models
from app.devices.models import (
    DeviceEventSeverity,
    DeviceSecurityEvent,
    DeviceSecurityEventType,
    DeviceStatus,
    UserDevice,
)
from app.users.models import User, UserRole
from app.vpn.abuse_alerts import (
    VPNDeviceAbuseAlert,
    VPNDeviceAbuseAlertStatus,
    block_device_for_alert,
    create_device_abuse_alert,
    list_device_abuse_alerts,
    resolve_device_abuse_alert,
    rotate_device_for_alert,
    serialize_device_abuse_alert,
)


@pytest.fixture
async def device_abuse_alert_session():
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


async def _seed_user_device(
    session: AsyncSession,
    *,
    email: str = "vpn-abuse@example.com",
    name: str = "Phone",
) -> tuple[User, UserDevice]:
    user = User(
        email=email,
        password_hash="hash",
        role=UserRole.USER,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    device = UserDevice(
        user_id=int(user.id),
        name=name,
        platform="android",
        status=DeviceStatus.ACTIVE,
        last_endpoint="203.0.113.10:51820",
        last_handshake_at=datetime.now(timezone.utc),
    )
    session.add(device)
    await session.flush()
    return user, device


async def _record_event(
    session: AsyncSession,
    *,
    user: User,
    device: UserDevice,
    event_type: DeviceSecurityEventType,
    severity: DeviceEventSeverity = DeviceEventSeverity.WARNING,
) -> DeviceSecurityEvent:
    event = DeviceSecurityEvent(
        user_id=int(user.id),
        device_id=int(device.id),
        event_type=event_type,
        severity=severity,
        details_json='{"source":"test"}',
    )
    session.add(event)
    await session.flush()
    return event


@pytest.mark.asyncio
async def test_confirmed_abuse_event_creates_and_dedupes_open_alert(device_abuse_alert_session: AsyncSession):
    user, device = await _seed_user_device(device_abuse_alert_session)
    first_event = await _record_event(
        device_abuse_alert_session,
        user=user,
        device=device,
        event_type=DeviceSecurityEventType.PING_PONG_ABUSE_DETECTED,
    )
    second_event = await _record_event(
        device_abuse_alert_session,
        user=user,
        device=device,
        event_type=DeviceSecurityEventType.PING_PONG_ABUSE_DETECTED,
    )

    alert = await create_device_abuse_alert(device_abuse_alert_session, first_event)
    deduped = await create_device_abuse_alert(device_abuse_alert_session, second_event)
    payload = await list_device_abuse_alerts(device_abuse_alert_session, status_filter=VPNDeviceAbuseAlertStatus.OPEN)

    assert alert is not None
    assert deduped is not None
    assert alert.id == deduped.id
    assert deduped.occurrence_count == 2
    assert payload["open_count"] == 1
    assert payload["items"][0]["signal_type"] == DeviceSecurityEventType.PING_PONG_ABUSE_DETECTED.value
    assert payload["items"][0]["source_event_id"] == second_event.id


@pytest.mark.asyncio
async def test_non_confirmed_events_do_not_create_alerts(device_abuse_alert_session: AsyncSession):
    user, device = await _seed_user_device(device_abuse_alert_session)
    ignored_types = [
        DeviceSecurityEventType.SUSPICIOUS_ENDPOINT_CHURN,
        DeviceSecurityEventType.CONCURRENT_HANDSHAKE_SUSPECTED,
        DeviceSecurityEventType.ANTI_ABUSE_REDIS_DEGRADED,
        DeviceSecurityEventType.DEVICE_CREATED,
    ]

    for event_type in ignored_types:
        event = await _record_event(
            device_abuse_alert_session,
            user=user,
            device=device,
            event_type=event_type,
            severity=DeviceEventSeverity.INFO,
        )
        assert await create_device_abuse_alert(device_abuse_alert_session, event) is None

    result = await device_abuse_alert_session.execute(select(VPNDeviceAbuseAlert))
    assert list(result.scalars().all()) == []


@pytest.mark.asyncio
async def test_resolve_archives_without_changing_device(device_abuse_alert_session: AsyncSession):
    user, device = await _seed_user_device(device_abuse_alert_session)
    event = await _record_event(
        device_abuse_alert_session,
        user=user,
        device=device,
        event_type=DeviceSecurityEventType.MULTI_NETWORK_ABUSE_DETECTED,
    )
    alert = await create_device_abuse_alert(device_abuse_alert_session, event)

    payload = await resolve_device_abuse_alert(
        device_abuse_alert_session,
        alert_id=int(alert.id),
        admin_id=99,
        action_taken="reviewed",
        action_result="false_positive",
    )
    await device_abuse_alert_session.refresh(device)
    archived = await list_device_abuse_alerts(device_abuse_alert_session, status_filter=VPNDeviceAbuseAlertStatus.RESOLVED)

    assert payload is not None
    assert payload["status"] == VPNDeviceAbuseAlertStatus.RESOLVED.value
    assert device.status == DeviceStatus.ACTIVE
    assert device.config_version == 1
    assert archived["resolved_count"] == 1
    assert archived["items"][0]["action_result"] == "false_positive"


@pytest.mark.asyncio
async def test_rotate_and_block_alert_actions_require_confirmation_and_target_one_device(device_abuse_alert_session: AsyncSession):
    user, device = await _seed_user_device(device_abuse_alert_session, email="owner@example.com", name="Owner phone")
    _, other_device = await _seed_user_device(device_abuse_alert_session, email="other@example.com", name="Other phone")
    event = await _record_event(
        device_abuse_alert_session,
        user=user,
        device=device,
        event_type=DeviceSecurityEventType.PING_PONG_ABUSE_DETECTED,
    )
    alert = await create_device_abuse_alert(device_abuse_alert_session, event)
    vpn_calls: list[tuple[int, int, bool]] = []

    class StubPolicy:
        async def rotate_device_config(self, target, *, reason=""):
            target.config_version += 1
            return target

        async def block_device(self, target, *, reason=""):
            target.status = DeviceStatus.BLOCKED
            target.block_reason = reason
            return target

    class StubVPN:
        async def provision_device_client(self, user_id, device_id, *, reprovision=False):
            vpn_calls.append((user_id, device_id, reprovision))
            return None

    with pytest.raises(ValueError, match="confirmation"):
        await rotate_device_for_alert(device_abuse_alert_session, alert_id=int(alert.id), admin_id=99)

    rotated = await rotate_device_for_alert(
        device_abuse_alert_session,
        alert_id=int(alert.id),
        admin_id=99,
        confirm=True,
        policy=StubPolicy(),
        vpn=StubVPN(),
    )
    await device_abuse_alert_session.refresh(device)
    await device_abuse_alert_session.refresh(other_device)

    assert rotated is not None
    assert rotated["action_taken"] == "rotate_device"
    assert device.config_version == 2
    assert other_device.config_version == 1
    assert other_device.status == DeviceStatus.ACTIVE
    assert vpn_calls == [(int(user.id), int(device.id), True)]

    second_event = await _record_event(
        device_abuse_alert_session,
        user=user,
        device=device,
        event_type=DeviceSecurityEventType.MULTI_NETWORK_ABUSE_DETECTED,
    )
    second_alert = await create_device_abuse_alert(device_abuse_alert_session, second_event)

    with pytest.raises(ValueError, match="confirmation"):
        await block_device_for_alert(device_abuse_alert_session, alert_id=int(second_alert.id), admin_id=99)

    blocked = await block_device_for_alert(
        device_abuse_alert_session,
        alert_id=int(second_alert.id),
        admin_id=99,
        confirm=True,
        policy=StubPolicy(),
    )
    await device_abuse_alert_session.refresh(device)
    await device_abuse_alert_session.refresh(other_device)

    assert blocked is not None
    assert blocked["action_taken"] == "block_device"
    assert device.status == DeviceStatus.BLOCKED
    assert other_device.status == DeviceStatus.ACTIVE


@pytest.mark.asyncio
async def test_serialized_alert_payload_is_redacted(device_abuse_alert_session: AsyncSession):
    user, device = await _seed_user_device(device_abuse_alert_session)
    event = await _record_event(
        device_abuse_alert_session,
        user=user,
        device=device,
        event_type=DeviceSecurityEventType.PING_PONG_ABUSE_DETECTED,
    )
    alert = await create_device_abuse_alert(device_abuse_alert_session, event)

    payload = await serialize_device_abuse_alert(device_abuse_alert_session, alert)
    payload_text = str(payload)

    assert "private_key" not in payload_text
    assert "preshared_key" not in payload_text
    assert "[Interface]" not in payload_text
    assert "Address =" not in payload_text
    assert payload["last_endpoint"] == "203.0.113.10:51820"
