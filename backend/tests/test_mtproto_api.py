"""MTProto user-cabinet API tests.

# FILE: backend/tests/test_mtproto_api.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify Phase-31 owner-only MTProto proxy API behavior
#   SCOPE: Authenticated /api/v1/mtproto/proxy response shape, owner-only secrets,
#          safe failure states, idempotency, and reissue guidance
#   DEPENDS: M-045, M-043, M-042, M-001, M-002
#   LINKS: V-M-045, V-M-043, V-M-042
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   _settings - Build deterministic MTProto settings for tests
#   _build_app - Build FastAPI test app with scoped dependency overrides
#   _create_user - Create verified or unverified user fixture
#   test_get_my_mtproto_proxy_returns_owner_payload_and_reuses_assignment - Owner payload success
#   test_get_my_mtproto_proxy_requires_authentication - Auth gate
#   test_get_my_mtproto_proxy_hides_secret_for_unverified_user - Unverified safe state
#   test_get_my_mtproto_proxy_maps_config_pending_without_secret - Config pending state
#   test_get_my_mtproto_proxy_returns_reissue_required_without_stale_credentials - Rotation state
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-31 MTProto owner API tests
# END_CHANGE_SUMMARY
"""

from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_current_user
from app.core.config import Settings
from app.core.database import get_session
from app.mtproto import router as mtproto_router_module
from app.mtproto.models import MTProtoAssignment
from app.mtproto.service import MTProtoProvisioningService
from app.users.models import User


BASE_SECRET = "0123456789abcdef0123456789abcdef"
SECRET_SALT = "abcdef0123456789abcdef0123456789"


# START_BLOCK_MTPROTO_API_TEST_HELPERS
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


def _build_app(session: AsyncSession, current_user: User | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(mtproto_router_module.router)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_session] = override_session

    if current_user is not None:
        async def current_user_override() -> User:
            return current_user

        app.dependency_overrides[get_current_user] = current_user_override

    return TestClient(app)


async def _create_user(
    session: AsyncSession,
    email: str,
    *,
    email_verified: bool = True,
    is_active: bool = True,
) -> User:
    user = User(email=email, email_verified=email_verified, is_active=is_active)
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _assignment_count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(MTProtoAssignment))
    return int(result.scalar_one())


def _set_service(monkeypatch: pytest.MonkeyPatch, app_settings: Settings) -> None:
    def factory(session: AsyncSession) -> MTProtoProvisioningService:
        return MTProtoProvisioningService(session, app_settings=app_settings)

    monkeypatch.setattr(mtproto_router_module, "build_mtproto_service", factory)
# END_BLOCK_MTPROTO_API_TEST_HELPERS


# START_BLOCK_MTPROTO_API_TESTS
@pytest.mark.asyncio
async def test_get_my_mtproto_proxy_returns_owner_payload_and_reuses_assignment(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    user = await _create_user(db_session, "owner-mtproto@example.com")
    _set_service(monkeypatch, _settings())
    client = _build_app(db_session, user)

    first_response = client.get("/api/v1/mtproto/proxy")
    second_response = client.get("/api/v1/mtproto/proxy")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    body = first_response.json()
    assert body["status"] == "activated"
    assert body["server"].endswith(".krotpn.xyz")
    assert body["port"] == 443
    assert body["secret"].startswith("ee")
    assert body["tg_link"].startswith("tg://proxy?")
    assert body["secret"] in body["tg_link"]
    assert BASE_SECRET not in body["tg_link"]
    assert second_response.json()["assignment_id"] == body["assignment_id"]
    assert await _assignment_count(db_session) == 1


@pytest.mark.asyncio
async def test_get_my_mtproto_proxy_requires_authentication(db_session: AsyncSession):
    client = _build_app(db_session)

    response = client.get("/api/v1/mtproto/proxy")

    assert response.status_code == 401
    assert await _assignment_count(db_session) == 0


@pytest.mark.asyncio
async def test_get_my_mtproto_proxy_hides_secret_for_unverified_user(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    user = await _create_user(
        db_session,
        "unverified-api-mtproto@example.com",
        email_verified=False,
    )
    _set_service(monkeypatch, _settings())
    client = _build_app(db_session, user)

    response = client.get("/api/v1/mtproto/proxy")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unverified"
    assert body["action_required"] == "verify_email"
    assert body["secret"] is None
    assert body["tg_link"] is None
    assert await _assignment_count(db_session) == 0


@pytest.mark.asyncio
async def test_get_my_mtproto_proxy_maps_config_pending_without_secret(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    user = await _create_user(db_session, "config-pending-mtproto@example.com")
    _set_service(
        monkeypatch,
        _settings(mtproto_base_secret_hex=None, mtproto_secret_salt=None),
    )
    client = _build_app(db_session, user)

    response = client.get("/api/v1/mtproto/proxy")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["action_required"] == "wait"
    assert body["secret"] is None
    assert body["tg_link"] is None
    assert await _assignment_count(db_session) == 0


@pytest.mark.asyncio
async def test_get_my_mtproto_proxy_returns_reissue_required_without_stale_credentials(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    user = await _create_user(db_session, "reissue-api-mtproto@example.com")
    await MTProtoProvisioningService(db_session, app_settings=_settings()).issue_user_proxy(user)
    _set_service(monkeypatch, _settings(mtproto_rotation_marker="v2"))
    client = _build_app(db_session, user)

    response = client.get("/api/v1/mtproto/proxy")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "reissue_required"
    assert body["action_required"] == "contact_support"
    assert body["reissue_required"] is True
    assert body["secret"] is None
    assert body["tg_link"] is None
    assert await _assignment_count(db_session) == 1
# END_BLOCK_MTPROTO_API_TESTS
