"""Phase-34 verified-registration to MTProto integration tests.

# FILE: backend/tests/test_phase34_mtproto_integration.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify release-readiness integration between email verification, onboarding,
#            and owner-only MTProto proxy issuance.
#   SCOPE: Pending registration guard, verified activation side effects, referral/trial/device
#          creation, authenticated MTProto owner payload, idempotent assignment reuse, replay safety.
#   DEPENDS: M-041, M-042, M-043, M-045, M-040, M-004, M-005, M-020
#   LINKS: V-M-041, V-M-042, V-M-043, V-M-045, docs/plans/Phase-34.xml
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   AlwaysResolvable - Test DNS resolver accepting deterministic example domains.
#   CapturingSender - Test email sender that captures verification tokens without network I/O.
#   StubVPNService - Test VPN provisioning stub preventing host/network mutation.
#   _settings - Deterministic email and MTProto settings for Phase-34 tests.
#   _build_phase34_client - FastAPI TestClient with real auth and MTProto routers.
#   _count/_get_user_by_email - DB helpers for side-effect assertions.
#   test_verified_registration_issues_single_owner_mtproto_proxy - End-to-end release gate.
#   test_unverified_user_cannot_get_mtproto_assignment - Unverified owner-safe MTProto state.
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-34 verified-registration/MTProto integration gate.
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from app.billing.models import Subscription
from app.core.config import Settings
from app.core.database import get_session
from app.core.security import create_access_token
from app.devices.models import UserDevice
from app.email.provider import EmailDeliveryReceipt
from app.email.verification import (
    activate_registration,
    request_registration,
)
from app.mtproto import router as mtproto_router_module
from app.mtproto.models import MTProtoAssignment
from app.mtproto.service import MTProtoProvisioningService
from app.referrals.models import Referral, ReferralCode
from app.users import router as users_router_module
from app.users.models import PendingEmailRegistration, PendingEmailRegistrationStatus, User
from app.users.schemas import UserCreate


BASE_SECRET = "0123456789abcdef0123456789abcdef"
SECRET_SALT = "abcdef0123456789abcdef0123456789"


# START_BLOCK_PHASE34_INTEGRATION_HELPERS
class AlwaysResolvable:
    async def has_mx_or_address(self, domain: str) -> bool:
        return True


class CapturingSender:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, to_email: str, token: str, **kwargs) -> EmailDeliveryReceipt:
        self.calls.append((to_email, token))
        return EmailDeliveryReceipt(provider="fake", message_id="msg_phase34", status="sent")


class StubVPNService:
    provision_calls: list[tuple[int, int, bool]] = []

    def __init__(self, session):
        self.session = session

    async def get_user_client(self, user_id: int):
        return None

    async def provision_device_client(
        self,
        user_id: int,
        device_id: int,
        *,
        reprovision: bool = False,
    ):
        self.provision_calls.append((user_id, device_id, reprovision))
        return SimpleNamespace(id=934, user_id=user_id, device_id=device_id)


def _settings(**overrides) -> Settings:
    values = {
        "secret_key": "test-secret-key-with-enough-length",
        "frontend_url": "https://krotpn.xyz",
        "email_provider": "disabled",
        "email_dns_check_enabled": False,
        "mtproto_base_domain": "krotpn.xyz",
        "mtproto_proxy_port": 443,
        "mtproto_base_secret_hex": BASE_SECRET,
        "mtproto_secret_salt": SECRET_SALT,
        "mtproto_sni_prefix": "u",
        "mtproto_rotation_marker": "v1",
    }
    values.update(overrides)
    return Settings(**values)


def _build_phase34_client(session: AsyncSession) -> TestClient:
    app = FastAPI()
    app.include_router(users_router_module.router)
    app.include_router(mtproto_router_module.router)
    app.state.limiter = users_router_module.limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def _set_deterministic_services(monkeypatch: pytest.MonkeyPatch, sender: CapturingSender) -> None:
    app_settings = _settings(email_dns_check_enabled=True)

    async def fake_request_registration(session, data):
        return await request_registration(
            session,
            data,
            email_sender=sender,
            resolver=AlwaysResolvable(),
            app_settings=app_settings,
        )

    async def fake_activate_registration(session, token):
        return await activate_registration(session, token, app_settings=app_settings)

    def mtproto_factory(session: AsyncSession) -> MTProtoProvisioningService:
        return MTProtoProvisioningService(session, app_settings=_settings())

    monkeypatch.setattr(users_router_module, "request_registration", fake_request_registration)
    monkeypatch.setattr(users_router_module, "activate_registration", fake_activate_registration)
    monkeypatch.setattr(users_router_module, "VPNService", StubVPNService)
    monkeypatch.setattr(mtproto_router_module, "build_mtproto_service", mtproto_factory)


async def _count(session: AsyncSession, model: type) -> int:
    result = await session.execute(select(func.count()).select_from(model))
    return int(result.scalar_one())


async def _get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()
# END_BLOCK_PHASE34_INTEGRATION_HELPERS


# START_BLOCK_PHASE34_REGISTRATION_TO_MTPROTO_TESTS
@pytest.mark.asyncio
async def test_verified_registration_issues_single_owner_mtproto_proxy(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    sender = CapturingSender()
    StubVPNService.provision_calls = []
    _set_deterministic_services(monkeypatch, sender)

    referrer = User(email="phase34-referrer@example.com", email_verified=True, is_active=True)
    db_session.add(referrer)
    await db_session.flush()
    referral_code = ReferralCode(user_id=int(referrer.id), code="PHASE34")
    db_session.add(referral_code)
    await db_session.flush()

    client = _build_phase34_client(db_session)
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "Phase34.Owner@Example.com",
            "password": "very-secret-password",
            "name": "Phase 34 Owner",
            "referral_code": "PHASE34",
        },
    )

    assert register_response.status_code == 202
    assert register_response.json()["status"] == PendingEmailRegistrationStatus.PENDING.value
    assert "access_token" not in register_response.json()
    assert sender.calls and sender.calls[0][0] == "phase34.owner@example.com"
    assert await _get_user_by_email(db_session, "phase34.owner@example.com") is None
    assert await _count(db_session, Subscription) == 0
    assert await _count(db_session, UserDevice) == 0
    assert await _count(db_session, Referral) == 0
    assert await _count(db_session, MTProtoAssignment) == 0

    verification_token = sender.calls[0][1]
    verify_response = client.post("/api/v1/auth/verify-email", json={"token": verification_token})

    assert verify_response.status_code == 200
    access_token = verify_response.json()["access_token"]
    owner = await _get_user_by_email(db_session, "phase34.owner@example.com")
    assert owner is not None
    assert owner.email_verified is True
    assert owner.referred_by_id == referrer.id
    assert await _count(db_session, Subscription) == 1
    assert await _count(db_session, UserDevice) == 1
    assert await _count(db_session, Referral) == 1
    assert await _count(db_session, MTProtoAssignment) == 0
    assert len(StubVPNService.provision_calls) == 1

    headers = {"Authorization": f"Bearer {access_token}"}
    first_proxy_response = client.get("/api/v1/mtproto/proxy", headers=headers)
    second_proxy_response = client.get("/api/v1/mtproto/proxy", headers=headers)

    assert first_proxy_response.status_code == 200
    assert second_proxy_response.status_code == 200
    first_proxy = first_proxy_response.json()
    second_proxy = second_proxy_response.json()
    assert first_proxy["status"] == "activated"
    assert first_proxy["server"].endswith(".krotpn.xyz")
    assert first_proxy["sni"] == first_proxy["server"]
    assert first_proxy["port"] == 443
    assert first_proxy["secret"].startswith("ee")
    assert first_proxy["tg_link"].startswith("tg://proxy?")
    assert BASE_SECRET not in first_proxy["tg_link"]
    assert SECRET_SALT not in first_proxy["tg_link"]
    assert second_proxy["assignment_id"] == first_proxy["assignment_id"]
    assert second_proxy["tg_link"] == first_proxy["tg_link"]
    assert await _count(db_session, MTProtoAssignment) == 1

    replay_response = client.post("/api/v1/auth/verify-email", json={"token": verification_token})

    assert replay_response.status_code == 409
    assert replay_response.json()["detail"]["code"] == "token_replayed"
    assert await _count(db_session, Subscription) == 1
    assert await _count(db_session, UserDevice) == 1
    assert await _count(db_session, Referral) == 1
    assert await _count(db_session, MTProtoAssignment) == 1
    assert len(StubVPNService.provision_calls) == 1


@pytest.mark.asyncio
async def test_unverified_user_cannot_get_mtproto_assignment(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    sender = CapturingSender()
    _set_deterministic_services(monkeypatch, sender)
    client = _build_phase34_client(db_session)

    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": "phase34.pending@example.com", "password": "very-secret-password"},
    )

    assert register_response.status_code == 202
    assert await _count(db_session, PendingEmailRegistration) == 1
    assert await _count(db_session, MTProtoAssignment) == 0

    unverified_user = User(
        email="phase34-unverified-user@example.com",
        email_verified=False,
        is_active=True,
    )
    db_session.add(unverified_user)
    await db_session.flush()
    await db_session.refresh(unverified_user)
    token = create_access_token(subject=int(unverified_user.id))

    response = client.get(
        "/api/v1/mtproto/proxy",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unverified"
    assert body["action_required"] == "verify_email"
    assert body["secret"] is None
    assert body["tg_link"] is None
    assert await _count(db_session, MTProtoAssignment) == 0
# END_BLOCK_PHASE34_REGISTRATION_TO_MTPROTO_TESTS
