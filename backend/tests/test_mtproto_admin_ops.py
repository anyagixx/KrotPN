"""MTProto admin operations tests.

# FILE: backend/tests/test_mtproto_admin_ops.py
# VERSION: 2.1.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify admin-only MTProto assignment operations and redaction gates
#   SCOPE: Redacted list/detail/health, role gates, reissue/revoke confirmation, audit records,
#          and non-MTProto account/device preservation
#   DEPENDS: M-047, M-006, M-024, M-042, M-043, M-044
#   LINKS: V-M-047, V-M-044
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   _settings - Build deterministic MTProto provisioning settings for reissue
#   _build_client - Build FastAPI app with admin router and DB override
#   _create_user - Create role-aware test users
#   _create_assignment - Persist MTProto assignment rows
#   _headers - Build access-token headers for real admin dependency checks
#   _assert_redacted - Assert no admin response/audit payload contains secrets or tg links
#   test_admin_mtproto_list_detail_health_are_redacted_and_role_gated - Covers read APIs and auth
#   test_admin_mtproto_reissue_requires_confirmation_and_redacted_audit - Covers explicit reissue
#   test_admin_mtproto_revoke_disables_assignment_without_account_or_device_side_effects - Covers scoped revoke and KPprotoN policy removal
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.1.0 - Restored admin MTProto operations to KPprotoN runtime bridge.
#   LAST_CHANGE: v2.0.0 - Updated admin MTProto operations for official MTProxy manifest sync.
#   LAST_CHANGE: v1.1.0 - Added runtime SNI policy removal assertion for admin revoke
#   LAST_CHANGE: v1.0.0 - Added Phase-33 MTProto admin ops verification
# END_CHANGE_SUMMARY
"""

from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import router as admin_router_module
from app.admin.audit import AdminAuditEvent
from app.core.config import Settings
from app.core.database import get_session
from app.core.security import create_access_token
from app.devices.models import DeviceStatus, UserDevice
from app.mtproto.models import MTProtoAssignment, MTProtoAssignmentStatus
from app.mtproto.provisioning import MTProtoProvisioningService
from app.mtproto.runtime_bridge import InMemoryMTProtoPolicyAdapter, MTProtoRuntimeBridge
from app.users.models import User, UserRole


BASE_SECRET = "0123456789abcdef0123456789abcdef"
SECRET_SALT = "abcdef0123456789abcdef0123456789"


# START_BLOCK_TEST_HELPERS
def _settings(**overrides) -> Settings:
    values = {
        "secret_key": "test-secret-key-with-enough-length",
        "mtproto_base_domain": "krotpn.xyz",
        "mtproto_proxy_port": 443,
        "mtproto_base_secret_hex": BASE_SECRET,
        "mtproto_secret_salt": SECRET_SALT,
        "mtproto_sni_prefix": "u",
        "mtproto_rotation_marker": "v1",
    }
    values.update(overrides)
    return Settings(**values)


def _build_client(session: AsyncSession) -> TestClient:
    app = FastAPI()
    app.include_router(admin_router_module.router)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


async def _create_user(
    session: AsyncSession,
    email: str,
    *,
    role: UserRole = UserRole.USER,
    email_verified: bool = True,
) -> User:
    user = User(
        email=email,
        role=role,
        email_verified=email_verified,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _create_assignment(
    session: AsyncSession,
    user: User,
    sni: str,
    *,
    status: MTProtoAssignmentStatus = MTProtoAssignmentStatus.ACTIVE,
    rotation_marker: str = "v1",
) -> MTProtoAssignment:
    assignment = MTProtoAssignment(
        user_id=int(user.id),
        sni=sni,
        status=status,
        rotation_marker=rotation_marker,
    )
    session.add(assignment)
    await session.flush()
    await session.refresh(assignment)
    return assignment


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}


def _assert_redacted(payload: object) -> None:
    payload_text = str(payload)
    assert "tg://proxy" not in payload_text
    assert "https://t.me/proxy" not in payload_text
    assert "secret=" not in payload_text
    assert BASE_SECRET not in payload_text
    assert SECRET_SALT not in payload_text
    assert "MTPROTO_BASE_SECRET_HEX" not in payload_text
    assert "MTPROTO_SECRET_SALT" not in payload_text
# END_BLOCK_TEST_HELPERS


# START_BLOCK_MTPROTO_ADMIN_OPS_TESTS
@pytest.mark.asyncio
async def test_admin_mtproto_list_detail_health_are_redacted_and_role_gated(
    db_session: AsyncSession,
):
    admin = await _create_user(db_session, "admin-mtproto@example.com", role=UserRole.ADMIN)
    regular_user = await _create_user(db_session, "regular-mtproto@example.com")
    owner = await _create_user(db_session, "alice-mtproto@example.com")
    assignment = await _create_assignment(
        db_session,
        owner,
        "u-alice111111.krotpn.xyz",
    )
    client = _build_client(db_session)

    list_response = client.get(
        "/api/v1/admin/mtproto/assignments?search=alice&status=active",
        headers=_headers(admin),
    )
    detail_response = client.get(
        f"/api/v1/admin/mtproto/assignments/{assignment.id}",
        headers=_headers(admin),
    )
    health_response = client.get("/api/v1/admin/mtproto/health", headers=_headers(admin))
    rejected_response = client.get(
        "/api/v1/admin/mtproto/assignments",
        headers=_headers(regular_user),
    )

    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["total"] == 1
    assert list_body["items"][0]["assignment_id"] == assignment.id
    assert list_body["items"][0]["user_email"] == owner.email
    assert list_body["items"][0]["sni"] == assignment.sni
    assert "secret" not in list_body["items"][0]
    _assert_redacted(list_body)

    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "active"
    _assert_redacted(detail_response.json())

    assert health_response.status_code == 200
    assert health_response.json()["status"] in {"healthy", "degraded"}
    _assert_redacted(health_response.json())
    assert rejected_response.status_code == 403


@pytest.mark.asyncio
async def test_admin_mtproto_reissue_requires_confirmation_and_redacted_audit(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    admin = await _create_user(db_session, "admin-reissue-mtproto@example.com", role=UserRole.ADMIN)
    owner = await _create_user(db_session, "owner-reissue-mtproto@example.com")
    assignment = await _create_assignment(
        db_session,
        owner,
        "u-reissue1111.krotpn.xyz",
        status=MTProtoAssignmentStatus.REISSUE_REQUIRED,
        rotation_marker="v1",
    )

    def service_factory(session: AsyncSession) -> MTProtoProvisioningService:
        return MTProtoProvisioningService(
            session,
            app_settings=_settings(mtproto_rotation_marker="v2"),
        )

    monkeypatch.setattr(admin_router_module, "MTProtoProvisioningService", service_factory)
    client = _build_client(db_session)
    url = f"/api/v1/admin/mtproto/assignments/{assignment.id}/reissue"

    rejected_response = client.post(url, json={"confirm": False}, headers=_headers(admin))
    response = client.post(url, json={"confirm": True}, headers=_headers(admin))

    assert rejected_response.status_code == 400
    assert response.status_code == 200
    body = response.json()
    assert body["assignment"]["status"] == "active"
    assert body["assignment"]["rotation_marker"] == "v2"
    assert body["runtime_apply"]["status"] in {"activated", "degraded", "skipped"}
    _assert_redacted(body)

    audit_result = await db_session.execute(
        select(AdminAuditEvent).where(AdminAuditEvent.action == "mtproto.reissue")
    )
    audit_event = audit_result.scalar_one()
    assert audit_event.resource_id == assignment.id
    assert '"action": "reissue"' in audit_event.details
    _assert_redacted(audit_event.details)


@pytest.mark.asyncio
async def test_admin_mtproto_revoke_disables_assignment_without_account_or_device_side_effects(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    admin = await _create_user(db_session, "admin-revoke-mtproto@example.com", role=UserRole.ADMIN)
    owner = await _create_user(db_session, "owner-revoke-mtproto@example.com")
    assignment = await _create_assignment(
        db_session,
        owner,
        "u-revoke11111.krotpn.xyz",
    )
    adapter = InMemoryMTProtoPolicyAdapter()
    pre_bridge = MTProtoRuntimeBridge(db_session, adapter=adapter)
    pre_result = await pre_bridge.apply_domain_policy(assignment)
    assert pre_result.status.value == "activated"
    assert assignment.sni in adapter.policies
    device = UserDevice(
        user_id=int(owner.id),
        name="Owner phone",
        platform="ios",
        status=DeviceStatus.ACTIVE,
    )
    db_session.add(device)
    await db_session.flush()

    class TestRuntimeBridge(MTProtoRuntimeBridge):
        def __init__(self, session: AsyncSession) -> None:
            super().__init__(session, adapter=adapter)

    monkeypatch.setattr(admin_router_module, "MTProtoRuntimeBridge", TestRuntimeBridge)
    client = _build_client(db_session)

    rejected_response = client.post(
        f"/api/v1/admin/mtproto/assignments/{assignment.id}/revoke",
        json={"confirm": False},
        headers=_headers(admin),
    )
    response = client.post(
        f"/api/v1/admin/mtproto/assignments/{assignment.id}/revoke",
        json={"confirm": True},
        headers=_headers(admin),
    )
    await db_session.refresh(assignment)
    await db_session.refresh(owner)
    await db_session.refresh(device)

    assert rejected_response.status_code == 400
    assert response.status_code == 200
    body = response.json()
    assert body["revoked"] is True
    assert body["assignment"]["status"] == "disabled"
    assert body["runtime_revoke"]["status"] == "revoked"
    assert assignment.status == MTProtoAssignmentStatus.DISABLED
    assert owner.is_active is True
    assert device.status == DeviceStatus.ACTIVE
    assert assignment.sni not in adapter.policies
    _assert_redacted(body)

    audit_result = await db_session.execute(
        select(AdminAuditEvent).where(AdminAuditEvent.action == "mtproto.revoke")
    )
    audit_event = audit_result.scalar_one()
    assert audit_event.resource_id == assignment.id
    assert '"action": "revoke"' in audit_event.details
    _assert_redacted(audit_event.details)
# END_BLOCK_MTPROTO_ADMIN_OPS_TESTS
