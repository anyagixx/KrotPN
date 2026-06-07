"""Manual external MTProto proxy pool tests.

# FILE: backend/tests/test_mtproto_manual_proxy_pool.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify Phase-80 manual external MTProto proxy pool and delivery mode behavior
#   SCOPE: Admin CRUD validation/redaction, encrypted secret persistence, confirmation guards,
#          automatic-mode preservation, manual-mode owner response, and missing-active fallback
#   DEPENDS: M-045, M-047, M-082, M-001, M-002
#   LINKS: V-M-082, Phase-80
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   _build_app - Build FastAPI app with admin and owner MTProto routers
#   _create_user - Create admin/user fixtures
#   _headers - Build JWT auth headers
#   _manual_proxy_payload - Valid external proxy request body
#   test_automatic_mode_preserves_existing_provisioning_path - Default automatic source
#   test_admin_manual_proxy_create_encrypts_secret_and_redacts_responses - Admin pool redaction/encryption
#   test_manual_mode_owner_response_uses_external_proxy_without_assignment - Manual owner payload
#   test_manual_mode_missing_active_proxy_returns_pending_without_secret - Missing active fallback
#   test_manual_proxy_confirmation_and_validation_guards - Confirmation and validation guards
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-80 manual external MTProto pool tests.
# END_CHANGE_SUMMARY
"""

from collections.abc import AsyncGenerator

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import router as admin_router_module
from app.core.config import Settings
from app.core.database import get_session
from app.core.security import create_access_token
import app.core.security as security_mod
from app.mtproto import router as mtproto_router_module
from app.mtproto.models import (
    MTProtoAssignment,
    MTProtoDeliveryMode,
    MTProtoDeliverySettings,
    MTProtoManualExternalProxy,
)
from app.mtproto.provisioning import MTProtoProvisioningService
from app.users.models import User, UserRole


BASE_SECRET = "0123456789abcdef0123456789abcdef"
SECRET_SALT = "abcdef0123456789abcdef0123456789"
EXTERNAL_SECRET = "aabbccddeeff00112233445566778899"


# START_BLOCK_TEST_HELPERS
@pytest.fixture(autouse=True)
def _fernet_key(monkeypatch: pytest.MonkeyPatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(security_mod.settings, "data_encryption_key", key)
    security_mod._fernet = None
    yield
    security_mod._fernet = None


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


def _build_app(session: AsyncSession) -> TestClient:
    app = FastAPI()
    app.include_router(admin_router_module.router)
    app.include_router(mtproto_router_module.router)

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


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}


def _manual_proxy_payload(**overrides) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Operator verified fallback",
        "server": "fallback-proxy.example.net",
        "port": 443,
        "secret": EXTERNAL_SECRET,
        "priority": 10,
        "notes": "manually verified outside KrotPN",
    }
    payload.update(overrides)
    return payload


async def _assignment_count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(MTProtoAssignment))
    return int(result.scalar_one())


def _assert_admin_manual_payload_redacted(payload: object) -> None:
    payload_text = str(payload)
    assert EXTERNAL_SECRET not in payload_text
    assert "tg://proxy" not in payload_text
    assert "https://t.me/proxy" not in payload_text
    assert "secret=" not in payload_text
# END_BLOCK_TEST_HELPERS


# START_BLOCK_PHASE80_TESTS
@pytest.mark.asyncio
async def test_automatic_mode_preserves_existing_provisioning_path(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    user = await _create_user(db_session, "phase80-auto-owner@example.com")

    def service_factory(session: AsyncSession) -> MTProtoProvisioningService:
        return MTProtoProvisioningService(session, app_settings=_settings())

    monkeypatch.setattr(mtproto_router_module, "build_mtproto_service", service_factory)
    client = _build_app(db_session)

    response = client.get("/api/v1/mtproto/proxy", headers=_headers(user))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "activated"
    assert body["source"] == "krotpn_auto"
    assert body["telemetry_available"] is True
    assert body["browser_link"].startswith("https://t.me/proxy?")
    assert await _assignment_count(db_session) == 1


@pytest.mark.asyncio
async def test_admin_manual_proxy_create_encrypts_secret_and_redacts_responses(
    db_session: AsyncSession,
):
    admin = await _create_user(db_session, "phase80-admin@example.com", role=UserRole.ADMIN)
    regular_user = await _create_user(db_session, "phase80-regular@example.com")
    client = _build_app(db_session)

    create_response = client.post(
        "/api/v1/admin/mtproto/manual-proxies",
        json=_manual_proxy_payload(),
        headers=_headers(admin),
    )
    list_response = client.get("/api/v1/admin/mtproto/manual-proxies", headers=_headers(admin))
    rejected_response = client.get("/api/v1/admin/mtproto/manual-proxies", headers=_headers(regular_user))

    assert create_response.status_code == 200
    body = create_response.json()
    assert body["status"] == "ready"
    assert body["server"] == "fallback-proxy.example.net"
    assert "secret_fingerprint" in body
    _assert_admin_manual_payload_redacted(body)
    assert list_response.status_code == 200
    _assert_admin_manual_payload_redacted(list_response.json())
    assert rejected_response.status_code == 403

    row = (await db_session.execute(select(MTProtoManualExternalProxy))).scalar_one()
    assert row.secret_enc != EXTERNAL_SECRET
    assert security_mod.decrypt_data(row.secret_enc) == EXTERNAL_SECRET


@pytest.mark.asyncio
async def test_manual_mode_owner_response_uses_external_proxy_without_assignment(
    db_session: AsyncSession,
):
    admin = await _create_user(db_session, "phase80-admin-owner@example.com", role=UserRole.ADMIN)
    owner = await _create_user(db_session, "phase80-manual-owner@example.com")
    client = _build_app(db_session)

    create_response = client.post(
        "/api/v1/admin/mtproto/manual-proxies",
        json=_manual_proxy_payload(name="Fallback active"),
        headers=_headers(admin),
    )
    proxy_id = int(create_response.json()["id"])
    activate_response = client.post(
        f"/api/v1/admin/mtproto/manual-proxies/{proxy_id}/activate",
        json={"confirm": True},
        headers=_headers(admin),
    )
    mode_response = client.put(
        "/api/v1/admin/mtproto/delivery-mode",
        json={"mode": "manual_external", "confirm": True},
        headers=_headers(admin),
    )
    owner_response = client.get("/api/v1/mtproto/proxy", headers=_headers(owner))

    assert activate_response.status_code == 200
    assert mode_response.status_code == 200
    assert mode_response.json()["mode"] == "manual_external"
    assert owner_response.status_code == 200
    body = owner_response.json()
    assert body["status"] == "activated"
    assert body["source"] == "manual_external"
    assert body["telemetry_available"] is False
    assert body["manual_proxy_name"] == "Fallback active"
    assert body["server"] == "fallback-proxy.example.net"
    assert body["secret"] == EXTERNAL_SECRET
    assert body["tg_link"].startswith("tg://proxy?")
    assert body["browser_link"].startswith("https://t.me/proxy?")
    assert await _assignment_count(db_session) == 0


@pytest.mark.asyncio
async def test_manual_mode_missing_active_proxy_returns_pending_without_secret(
    db_session: AsyncSession,
):
    owner = await _create_user(db_session, "phase80-missing-active@example.com")
    db_session.add(
        MTProtoDeliverySettings(
            id=1,
            mode=MTProtoDeliveryMode.MANUAL_EXTERNAL,
            active_manual_proxy_id=None,
        )
    )
    await db_session.flush()
    client = _build_app(db_session)

    response = client.get("/api/v1/mtproto/proxy", headers=_headers(owner))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["source"] == "manual_external"
    assert body["telemetry_available"] is False
    assert body["secret"] is None
    assert body["tg_link"] is None
    assert await _assignment_count(db_session) == 0


@pytest.mark.asyncio
async def test_manual_proxy_confirmation_and_validation_guards(
    db_session: AsyncSession,
):
    admin = await _create_user(db_session, "phase80-guard-admin@example.com", role=UserRole.ADMIN)
    client = _build_app(db_session)

    invalid_secret_response = client.post(
        "/api/v1/admin/mtproto/manual-proxies",
        json=_manual_proxy_payload(secret="not-hex-secret-value"),
        headers=_headers(admin),
    )
    create_response = client.post(
        "/api/v1/admin/mtproto/manual-proxies",
        json=_manual_proxy_payload(name="Guard proxy"),
        headers=_headers(admin),
    )
    proxy_id = int(create_response.json()["id"])
    rejected_activate = client.post(
        f"/api/v1/admin/mtproto/manual-proxies/{proxy_id}/activate",
        json={"confirm": False},
        headers=_headers(admin),
    )
    rejected_mode = client.put(
        "/api/v1/admin/mtproto/delivery-mode",
        json={"mode": "manual_external", "confirm": False},
        headers=_headers(admin),
    )

    assert invalid_secret_response.status_code in {400, 422}
    assert create_response.status_code == 200
    assert rejected_activate.status_code == 400
    assert rejected_mode.status_code == 400
# END_BLOCK_PHASE80_TESTS
