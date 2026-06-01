"""
MODULE_CONTRACT
- PURPOSE: Verify Phase-44 password recovery and password strength flows.
- SCOPE: Router/service regression tests for request/reset endpoints, token replay, weak-password rejection, duplicate-email recovery status, and safe logging.
- DEPENDS: app.users.router, app.users.password_reset, app.users.models, app.core.security.
- LINKS: V-M-062.

MODULE_MAP
- _build_auth_client: Constructs auth-router TestClient with DB dependency override.
- test_password_reset_request_and_confirm_consumes_token_once: Verifies reset email request, token consumption, login with new password, and replay guard.
- test_password_reset_request_is_generic_for_unknown_email: Verifies unknown accounts do not leak existence.
- test_password_reset_rejects_weak_password_without_consuming_token: Verifies strong-password gate before reset consumption.
- test_register_duplicate_email_returns_recovery_cta: Verifies duplicate registration gives recovery CTA and 409.

CHANGE_SUMMARY
- 2026-06-01: Added Phase-44 password recovery verification.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from loguru import logger
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from app.core.config import Settings
from app.core.database import get_session
from app.core.security import hash_password, verify_password
from app.email.provider import EmailDeliveryReceipt
from app.email.verification import request_registration
from app.users import router as users_router_module
from app.users.models import PasswordResetToken, PasswordResetTokenStatus, User
from app.users.password_reset import request_password_reset, reset_password_with_token


# START_BLOCK_PASSWORD_RECOVERY_TEST_HELPERS
class AlwaysResolvable:
    async def has_mx_or_address(self, domain: str) -> bool:
        return True


class CapturingResetSender:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, to_email: str, token: str, **kwargs) -> EmailDeliveryReceipt:
        self.calls.append((to_email, token))
        return EmailDeliveryReceipt(provider="fake", message_id="msg_reset", status="sent")


class CapturingVerificationSender:
    async def __call__(self, to_email: str, token: str, **kwargs) -> EmailDeliveryReceipt:
        return EmailDeliveryReceipt(provider="fake", message_id="msg_verify", status="sent")


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
# END_BLOCK_PASSWORD_RECOVERY_TEST_HELPERS


# START_BLOCK_PASSWORD_RECOVERY_TESTS
@pytest.mark.asyncio
async def test_password_reset_request_and_confirm_consumes_token_once(
    db_session: AsyncSession,
    monkeypatch,
):
    user = User(
        email="owner@example.com",
        email_verified=True,
        password_hash=hash_password("OldPassword1!"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    sender = CapturingResetSender()

    async def fake_request_password_reset_flow(session, email):
        return await request_password_reset(
            session,
            email,
            email_sender=sender,
            app_settings=_settings(),
        )

    async def fake_reset_password_with_token(session, token, new_password):
        return await reset_password_with_token(
            session,
            token,
            new_password,
            app_settings=_settings(),
        )

    monkeypatch.setattr(users_router_module, "request_password_reset_flow", fake_request_password_reset_flow)
    monkeypatch.setattr(users_router_module, "reset_password_with_token", fake_reset_password_with_token)
    client = _build_auth_client(db_session)

    token_secret = ""
    log_lines: list[str] = []
    sink_id = logger.add(lambda message: log_lines.append(str(message)), format="{message}")
    try:
        request_response = client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "Owner@Example.com"},
        )
        token_secret = sender.calls[0][1]
        confirm_response = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token_secret, "new_password": "NewPassword1!"},
        )
        replay_response = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token_secret, "new_password": "OtherPassword1!"},
        )
    finally:
        logger.remove(sink_id)

    assert request_response.status_code == 202
    assert request_response.json()["status"] == "accepted"
    assert len(sender.calls) == 1
    assert sender.calls[0][0] == "owner@example.com"
    assert confirm_response.status_code == 200
    assert replay_response.status_code == 409
    assert replay_response.json()["detail"]["code"] == "token_replayed"

    reset_result = await db_session.execute(select(PasswordResetToken))
    reset_record = reset_result.scalar_one()
    assert reset_record.status == PasswordResetTokenStatus.CONSUMED
    assert token_secret not in reset_record.token_hash
    assert verify_password("NewPassword1!", user.password_hash or "") is True

    joined_logs = "\n".join(log_lines)
    assert "[UsersRouter][request_password_reset][CREATE_RESET_TOKEN]" in joined_logs
    assert "[UsersRouter][reset_password][CONSUME_RESET_TOKEN]" in joined_logs
    assert token_secret not in joined_logs


@pytest.mark.asyncio
async def test_password_reset_request_is_generic_for_unknown_email(db_session: AsyncSession, monkeypatch):
    sender = CapturingResetSender()

    async def fake_request_password_reset_flow(session, email):
        return await request_password_reset(
            session,
            email,
            email_sender=sender,
            app_settings=_settings(),
        )

    monkeypatch.setattr(users_router_module, "request_password_reset_flow", fake_request_password_reset_flow)
    client = _build_auth_client(db_session)

    response = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "missing@example.com"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert sender.calls == []
    assert await _count(db_session, PasswordResetToken) == 0


@pytest.mark.asyncio
async def test_password_reset_rejects_weak_password_without_consuming_token(
    db_session: AsyncSession,
    monkeypatch,
):
    user = User(
        email="weak-reset@example.com",
        email_verified=True,
        password_hash=hash_password("OldPassword1!"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    sender = CapturingResetSender()
    result = await request_password_reset(
        db_session,
        "weak-reset@example.com",
        email_sender=sender,
        app_settings=_settings(),
    )
    assert result.token_created is True
    token = sender.calls[0][1]

    async def fake_reset_password_with_token(session, token_value, new_password):
        return await reset_password_with_token(
            session,
            token_value,
            new_password,
            app_settings=_settings(),
        )

    monkeypatch.setattr(users_router_module, "reset_password_with_token", fake_reset_password_with_token)
    client = _build_auth_client(db_session)

    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "weakpassword"},
    )

    assert response.status_code == 422
    reset_result = await db_session.execute(select(PasswordResetToken))
    reset_record = reset_result.scalar_one()
    assert reset_record.status == PasswordResetTokenStatus.PENDING
    assert verify_password("OldPassword1!", user.password_hash or "") is True


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_recovery_cta(
    db_session: AsyncSession,
    monkeypatch,
):
    user = User(
        email="exists@example.com",
        email_verified=True,
        password_hash=hash_password("OldPassword1!"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    async def fake_request_registration(session, data):
        return await request_registration(
            session,
            data,
            email_sender=CapturingVerificationSender(),
            resolver=AlwaysResolvable(),
            app_settings=_settings(),
        )

    monkeypatch.setattr(users_router_module, "request_registration", fake_request_registration)
    client = _build_auth_client(db_session)

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "Exists@Example.com", "password": "StrongPassword1!"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "email_unavailable"
    assert "сброс пароля" in response.json()["detail"]["message"]
# END_BLOCK_PASSWORD_RECOVERY_TESTS
