"""
MODULE_CONTRACT
- PURPOSE: Verify Phase-28 verified email registration cutover.
- SCOPE: Router and service regression tests for pending /register, verify-email activation, onboarding side effects, replay, expiry, and pending-record reuse.
- DEPENDS: app.users.router, app.email.verification, app.users.models, app.billing.models, app.devices.models, app.referrals.models.
- LINKS: V-M-041, V-M-002, V-M-004, V-M-005, V-M-022.

MODULE_MAP
- _build_auth_client: Constructs auth-router TestClient with DB dependency override.
- test_register_returns_pending_without_active_access: Verifies unverified registration has no auth or onboarding side effects.
- test_verify_email_activates_user_and_onboarding_once: Verifies activation creates user, trial, device path, referral once and replay is safe.
- test_verify_email_rejects_expired_token_without_user_side_effects: Verifies expired token maps to safe failure.
- test_request_registration_reuses_pending_record_for_resend: Verifies resend-style register retry does not create duplicate pending rows.

CHANGE_SUMMARY
- 2026-06-01: Updated onboarding assertions for Phase-45 pending trial creation.
- 2026-05-13: Added Phase-28 verified-registration cutover regression tests.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
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
from app.email.provider import EmailDeliveryReceipt
from app.email.verification import (
    hash_verification_token,
    request_registration,
)
from app.referrals.models import Referral, ReferralCode
from app.users import router as users_router_module
from app.users.models import PendingEmailRegistration, PendingEmailRegistrationStatus, User
from app.users.schemas import UserCreate
from app.devices.models import UserDevice


# START_BLOCK_VERIFIED_REGISTRATION_TEST_HELPERS
class AlwaysResolvable:
    async def has_mx_or_address(self, domain: str) -> bool:
        return True


class CapturingSender:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, to_email: str, token: str, **kwargs) -> EmailDeliveryReceipt:
        self.calls.append((to_email, token))
        return EmailDeliveryReceipt(provider="fake", message_id="msg_phase28", status="sent")


class StubVPNService:
    provision_calls: list[tuple[int, int, bool]] = []

    def __init__(self, session):
        self.session = session

    async def get_user_client(self, user_id: int):
        return None

    async def provision_device_client(self, user_id: int, device_id: int, *, reprovision: bool = False):
        self.provision_calls.append((user_id, device_id, reprovision))
        return SimpleNamespace(id=91, user_id=user_id, device_id=device_id)


def _settings(**overrides) -> Settings:
    data = {
        "secret_key": "test-secret-key-with-enough-length",
        "frontend_url": "https://krotpn.xyz",
        "email_provider": "disabled",
        "email_dns_check_enabled": False,
        **overrides,
    }
    return Settings(**data)


def _build_auth_client(session: AsyncSession) -> TestClient:
    app = FastAPI()
    app.include_router(users_router_module.router)
    app.state.limiter = users_router_module.limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


async def _count(session: AsyncSession, model: type) -> int:
    result = await session.execute(select(func.count()).select_from(model))
    return int(result.scalar_one())
# END_BLOCK_VERIFIED_REGISTRATION_TEST_HELPERS


# START_BLOCK_VERIFIED_REGISTRATION_CUTOVER_TESTS
@pytest.mark.asyncio
async def test_register_returns_pending_without_active_access(db_session: AsyncSession, monkeypatch):
    sender = CapturingSender()

    async def fake_request_registration(session, data):
        return await request_registration(
            session,
            data,
            email_sender=sender,
            resolver=AlwaysResolvable(),
            app_settings=_settings(email_dns_check_enabled=True),
        )

    monkeypatch.setattr(users_router_module, "request_registration", fake_request_registration)
    client = _build_auth_client(db_session)

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "Pending@Example.com", "password": "Very-secret-password1!"},
    )

    assert response.status_code == 202
    assert "access_token" not in response.json()
    assert "refresh_token" not in response.json()
    assert "access_token" not in response.cookies
    assert response.json()["status"] == PendingEmailRegistrationStatus.PENDING.value
    assert sender.calls and sender.calls[0][0] == "pending@example.com"
    assert await _count(db_session, User) == 0
    assert await _count(db_session, Subscription) == 0
    assert await _count(db_session, UserDevice) == 0
    assert await _count(db_session, Referral) == 0


@pytest.mark.asyncio
async def test_verify_email_activates_user_and_onboarding_once(db_session: AsyncSession, monkeypatch):
    sender = CapturingSender()
    StubVPNService.provision_calls = []
    monkeypatch.setattr(users_router_module, "VPNService", StubVPNService)

    referrer = User(email="referrer@example.com", email_verified=True, is_active=True)
    db_session.add(referrer)
    await db_session.flush()
    referral_code = ReferralCode(user_id=int(referrer.id), code="FRIEND42")
    db_session.add(referral_code)
    await db_session.flush()

    await request_registration(
        db_session,
        UserCreate(
            email="Verified@Example.com",
            password="Very-secret-password1!",
            name="Verified User",
            referral_code="FRIEND42",
        ),
        email_sender=sender,
        resolver=AlwaysResolvable(),
        app_settings=_settings(),
    )
    token = sender.calls[0][1]
    client = _build_auth_client(db_session)

    response = client.post("/api/v1/auth/verify-email", json={"token": token})

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert response.cookies.get("access_token")

    user_result = await db_session.execute(select(User).where(User.email == "verified@example.com"))
    user = user_result.scalar_one()
    assert user.email_verified is True
    assert user.referred_by_id == referrer.id

    assert await _count(db_session, Subscription) == 1
    subscription_result = await db_session.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    subscription = subscription_result.scalar_one()
    assert subscription.pending_activation is True
    assert subscription.activated_at is None
    assert subscription.trial_duration_days == 4
    assert await _count(db_session, UserDevice) == 1
    assert await _count(db_session, Referral) == 1
    assert len(StubVPNService.provision_calls) == 1

    replay_response = client.post("/api/v1/auth/verify-email", json={"token": token})

    assert replay_response.status_code == 409
    assert replay_response.json()["detail"]["code"] == "token_replayed"
    assert await _count(db_session, Subscription) == 1
    assert await _count(db_session, UserDevice) == 1
    assert await _count(db_session, Referral) == 1
    assert len(StubVPNService.provision_calls) == 1


@pytest.mark.asyncio
async def test_verify_email_rejects_expired_token_without_user_side_effects(db_session: AsyncSession):
    token = "expired-token-for-phase28"
    app_settings = _settings()
    pending = PendingEmailRegistration(
        email="expired@example.com",
        token_hash=hash_verification_token(token, app_settings=app_settings),
        password_hash="hashed-password",
        status=PendingEmailRegistrationStatus.PENDING,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(pending)
    await db_session.flush()
    client = _build_auth_client(db_session)

    response = client.post("/api/v1/auth/verify-email", json={"token": token})

    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "token_expired"
    assert await _count(db_session, User) == 0
    assert await _count(db_session, Subscription) == 0
    assert await _count(db_session, UserDevice) == 0


@pytest.mark.asyncio
async def test_request_registration_reuses_pending_record_for_resend(db_session: AsyncSession):
    sender = CapturingSender()
    data = UserCreate(email="resend@example.com", password="Very-secret-password1!")

    await request_registration(
        db_session,
        data,
        email_sender=sender,
        resolver=AlwaysResolvable(),
        app_settings=_settings(),
    )
    await request_registration(
        db_session,
        data,
        email_sender=sender,
        resolver=AlwaysResolvable(),
        app_settings=_settings(),
    )

    assert len(sender.calls) == 2
    assert await _count(db_session, PendingEmailRegistration) == 1
    pending_result = await db_session.execute(select(PendingEmailRegistration))
    pending = pending_result.scalar_one()
    assert pending.status == PendingEmailRegistrationStatus.PENDING
    assert sender.calls[0][1] != sender.calls[1][1]
# END_BLOCK_VERIFIED_REGISTRATION_CUTOVER_TESTS
