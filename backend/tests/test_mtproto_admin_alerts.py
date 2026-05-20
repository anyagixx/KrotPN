"""MTProto admin alert tests.

# FILE: backend/tests/test_mtproto_admin_alerts.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify MTProto abuse alert inbox, dedupe, review states, and TTL IP block records
#   SCOPE: High/critical alert creation, acknowledge/resolve transitions, safe payloads, and IP block evidence guard
#   DEPENDS: M-060, M-061, M-056, M-026
#   LINKS: V-M-060, V-M-061
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   _create_assignment - Persist admin, user, and assignment fixtures
#   test_abuse_alert_dedupes_and_review_states_are_safe - Covers alert lifecycle
#   test_ip_block_requires_confirmation_and_trusted_observation - Covers TTL block evidence guard
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-43 MTProto admin alert verification
# END_CHANGE_SUMMARY
"""

from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security as security_mod
from app.mtproto.admin_alerts import (
    acknowledge_alert,
    block_ip_for_alert,
    create_abuse_alert,
    list_admin_alerts,
    resolve_alert,
)
from app.mtproto.ip_observability import record_ip_observation
from app.mtproto.models import MTProtoAssignment
from app.mtproto.usage_models import (
    MTProtoAbuseSignal,
    MTProtoAbuseSignalType,
    MTProtoAdminAlert,
    MTProtoAdminAlertStatus,
    MTProtoBlockedIP,
)
from app.users.models import User, UserRole


# START_BLOCK_TEST_HELPERS
@pytest.fixture(autouse=True)
def _phase43_encryption_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(security_mod.settings, "data_encryption_key", key)
    security_mod._fernet = None
    yield
    security_mod._fernet = None


async def _create_assignment(session: AsyncSession) -> tuple[User, User, MTProtoAssignment]:
    admin = User(email="alert-admin@example.com", role=UserRole.ADMIN, email_verified=True, is_active=True)
    user = User(email="alert-owner@example.com", email_verified=True, is_active=True)
    session.add(admin)
    session.add(user)
    await session.flush()
    assignment = MTProtoAssignment(user_id=int(user.id), sni="u-alertowner.krotpn.xyz", rotation_marker="v1")
    session.add(assignment)
    await session.flush()
    await session.refresh(admin)
    await session.refresh(user)
    await session.refresh(assignment)
    return admin, user, assignment


async def _create_signal(
    session: AsyncSession,
    *,
    assignment: MTProtoAssignment,
    user: User,
    severity: str = "high",
) -> MTProtoAbuseSignal:
    now = datetime.now(timezone.utc)
    signal = MTProtoAbuseSignal(
        assignment_id=int(assignment.id),
        user_id=int(user.id),
        signal_type=MTProtoAbuseSignalType.MANY_IP_HASHES,
        severity=severity,
        observe_only=True,
        window_start=now - timedelta(hours=1),
        window_end=now,
        metric_value=12,
        threshold_value=4,
    )
    session.add(signal)
    await session.flush()
    await session.refresh(signal)
    return signal
# END_BLOCK_TEST_HELPERS


# START_BLOCK_ADMIN_ALERT_TESTS
@pytest.mark.asyncio
async def test_abuse_alert_dedupes_and_review_states_are_safe(db_session: AsyncSession):
    admin, user, assignment = await _create_assignment(db_session)
    signal = await _create_signal(db_session, assignment=assignment, user=user)

    first = await create_abuse_alert(db_session, signal)
    second = await create_abuse_alert(db_session, signal)
    alert_list = await list_admin_alerts(db_session)

    assert first is not None
    assert second is not None
    assert first.id == second.id
    assert alert_list["total"] == 1
    assert alert_list["open_count"] == 1
    assert "https://t.me/proxy" not in str(alert_list)

    acknowledged = await acknowledge_alert(db_session, alert_id=int(first.id), admin_id=int(admin.id))
    resolved = await resolve_alert(
        db_session,
        alert_id=int(first.id),
        admin_id=int(admin.id),
        action_taken="reviewed",
        action_result="no_enforcement",
    )

    assert acknowledged["status"] == MTProtoAdminAlertStatus.ACKNOWLEDGED.value
    assert resolved["status"] == MTProtoAdminAlertStatus.RESOLVED.value
    result = await db_session.execute(select(MTProtoAdminAlert))
    alert = result.scalar_one()
    assert alert.occurrence_count == 2
    assert alert.resolved_by_admin_id == admin.id


@pytest.mark.asyncio
async def test_ip_block_requires_confirmation_and_trusted_observation(db_session: AsyncSession):
    admin, user, assignment = await _create_assignment(db_session)
    signal = await _create_signal(db_session, assignment=assignment, user=user, severity="critical")
    alert = await create_abuse_alert(db_session, signal)
    raw_ip = "198.51.100.88"
    observation = await record_ip_observation(
        db_session,
        assignment_id=int(assignment.id),
        user_id=int(user.id),
        client_ip=raw_ip,
        observed_at=datetime.now(timezone.utc),
        event_type="handshake",
        connection_count=1,
    )

    with pytest.raises(ValueError, match="requires explicit confirmation"):
        await block_ip_for_alert(
            db_session,
            alert_id=int(alert.id),
            ip_observation_id=int(observation.id),
            admin_id=int(admin.id),
            confirm=True,
            confirm_risk=False,
        )

    payload = await block_ip_for_alert(
        db_session,
        alert_id=int(alert.id),
        ip_observation_id=int(observation.id),
        admin_id=int(admin.id),
        ttl_hours=12,
        confirm=True,
        confirm_risk=True,
    )

    assert payload["status"] == "active"
    assert payload["ip_observation_id"] == observation.id
    assert payload["enforcement_status"] == "recorded_pending_runtime_enforcement"
    assert raw_ip not in str(payload)
    result = await db_session.execute(select(MTProtoBlockedIP))
    block = result.scalar_one()
    assert block.ip_hash == observation.ip_hash
    assert block.encrypted_ip != raw_ip
# END_BLOCK_ADMIN_ALERT_TESTS
