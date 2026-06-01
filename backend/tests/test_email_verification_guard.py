"""
MODULE_CONTRACT
- PURPOSE: Verify Phase-27 pending verified-registration foundation.
- SCOPE: Unit tests for email risk policy, pending token storage, replay/expiry guards, and /register compatibility boundary.
- DEPENDS: app.email.verification, app.users.models, app.users.router.
- LINKS: V-M-041.

MODULE_MAP
- test_email_risk_check_blocks_disposable_domain_before_send: Verifies disposable domains are rejected.
- test_email_risk_check_allowlist_overrides_block_rules: Verifies operator allowlist override.
- test_request_registration_blocks_domain_before_sender_call: Verifies blocked domains never call email delivery.
- test_request_registration_stores_hashed_token_without_user_side_effects: Verifies pending-only registration.
- test_verify_registration_consumes_token_once: Verifies one-time token consumption.
- test_email_domain_settings_accept_comma_env: Verifies operator-friendly comma env parsing.
- test_phase_28_register_is_wired_to_pending_flow: Verifies active /register now uses pending email verification.

CHANGE_SUMMARY
- 2026-05-13: Updated /register compatibility guard for Phase-28 cutover.
- 2026-05-13: Added Phase-27 email verification guard tests.
"""

import inspect
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.email.provider import EmailDeliveryReceipt
from app.email.service import build_verification_url
from app.email.verification import (
    EmailVerificationError,
    EmailVerificationErrorCode,
    email_risk_check,
    request_registration,
    verify_registration,
)
from app.users.models import PendingEmailRegistration, PendingEmailRegistrationStatus, User
from app.users.schemas import UserCreate


class AlwaysResolvable:
    async def has_mx_or_address(self, domain: str) -> bool:
        return True


class CapturingSender:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, to_email: str, token: str, **kwargs) -> EmailDeliveryReceipt:
        self.calls.append((to_email, token))
        return EmailDeliveryReceipt(provider="fake", message_id="msg_pending", status="sent")


def _settings(**overrides) -> Settings:
    data = {
        "secret_key": "test-secret-key-with-enough-length",
        "frontend_url": "https://krotpn.xyz",
        "email_provider": "disabled",
        "email_dns_check_enabled": False,
        **overrides,
    }
    return Settings(**data)


async def _count_users(session) -> int:
    result = await session.execute(select(func.count()).select_from(User))
    return int(result.scalar_one())


# START_BLOCK_EMAIL_VERIFICATION_GUARD_TESTS
@pytest.mark.asyncio
async def test_email_risk_check_blocks_disposable_domain_before_send():
    result = await email_risk_check(
        "test@mailinator.com",
        app_settings=_settings(email_disposable_domains=["mailinator.com"]),
    )

    assert result.allowed is False
    assert result.reason == EmailVerificationErrorCode.DISPOSABLE_DOMAIN


@pytest.mark.asyncio
async def test_email_risk_check_allowlist_overrides_block_rules():
    result = await email_risk_check(
        "person@example.com",
        app_settings=_settings(
            email_allowed_domains=["example.com"],
            email_blocked_domains=["example.com"],
            email_disposable_domains=["example.com"],
            email_dns_check_enabled=True,
        ),
        resolver=AlwaysResolvable(),
    )

    assert result.allowed is True
    assert result.allowlist_override is True
    assert result.dns_checked is False


@pytest.mark.asyncio
async def test_request_registration_blocks_domain_before_sender_call(db_session):
    sender = CapturingSender()
    data = UserCreate(email="test@mailinator.com", password="Very-secret-password1!")

    with pytest.raises(EmailVerificationError) as exc_info:
        await request_registration(
            db_session,
            data,
            email_sender=sender,
            app_settings=_settings(email_disposable_domains=["mailinator.com"]),
        )

    assert exc_info.value.code == EmailVerificationErrorCode.DISPOSABLE_DOMAIN
    assert sender.calls == []
    assert await _count_users(db_session) == 0

    pending_result = await db_session.execute(select(PendingEmailRegistration))
    assert pending_result.scalars().all() == []


def test_email_domain_settings_accept_comma_env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-with-enough-length")
    monkeypatch.setenv("EMAIL_ALLOWED_DOMAINS", "example.com, krotpn.xyz")
    monkeypatch.setenv("EMAIL_BLOCKED_DOMAINS", '["mailinator.com", "yopmail.com"]')

    app_settings = Settings(_env_file=None)

    assert app_settings.email_allowed_domains == ["example.com", "krotpn.xyz"]
    assert app_settings.email_blocked_domains == ["mailinator.com", "yopmail.com"]


@pytest.mark.asyncio
async def test_request_registration_stores_hashed_token_without_user_side_effects(db_session):
    sender = CapturingSender()
    data = UserCreate(email="Friend@Example.com", password="Very-secret-password1!", name="Friend")

    result = await request_registration(
        db_session,
        data,
        email_sender=sender,
        resolver=AlwaysResolvable(),
        app_settings=_settings(email_dns_check_enabled=True),
    )

    assert result.email == "friend@example.com"
    assert result.status == PendingEmailRegistrationStatus.PENDING
    assert await _count_users(db_session) == 0
    assert len(sender.calls) == 1

    token = sender.calls[0][1]
    pending_result = await db_session.execute(select(PendingEmailRegistration))
    pending = pending_result.scalar_one()

    assert pending.email == "friend@example.com"
    assert pending.password_hash != "Very-secret-password1!"
    assert token not in pending.token_hash
    assert len(pending.token_hash) == 64


@pytest.mark.asyncio
async def test_verify_registration_consumes_token_once(db_session):
    sender = CapturingSender()
    data = UserCreate(email="verify@example.com", password="Very-secret-password1!")
    await request_registration(
        db_session,
        data,
        email_sender=sender,
        resolver=AlwaysResolvable(),
        app_settings=_settings(),
    )
    token = sender.calls[0][1]

    consumed = await verify_registration(db_session, token, app_settings=_settings())

    assert consumed.status == PendingEmailRegistrationStatus.VERIFIED
    assert await _count_users(db_session) == 0

    with pytest.raises(EmailVerificationError) as exc_info:
        await verify_registration(db_session, token, app_settings=_settings())

    assert exc_info.value.code == EmailVerificationErrorCode.TOKEN_REPLAYED


@pytest.mark.asyncio
async def test_verify_registration_marks_expired_token(db_session):
    token = "expired-token"
    app_settings = _settings()
    expired_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    from app.email.verification import hash_verification_token

    pending = PendingEmailRegistration(
        email="expired@example.com",
        token_hash=hash_verification_token(token, app_settings=app_settings),
        password_hash="hashed-password",
        status=PendingEmailRegistrationStatus.PENDING,
        expires_at=expired_at,
    )
    db_session.add(pending)
    await db_session.flush()

    with pytest.raises(EmailVerificationError) as exc_info:
        await verify_registration(db_session, token, app_settings=app_settings)

    assert exc_info.value.code == EmailVerificationErrorCode.TOKEN_EXPIRED
    assert pending.status == PendingEmailRegistrationStatus.EXPIRED


def test_phase_28_register_is_wired_to_pending_flow():
    from app.users.router import register

    source = inspect.getsource(register)
    assert "request_registration" in source
    assert "create_user(" not in source


def test_build_verification_url_encodes_token():
    url = build_verification_url("token with spaces", _settings())
    parsed = urlparse(url)

    assert parsed.path == "/verify-email"
    assert parse_qs(parsed.query)["token"] == ["token with spaces"]
# END_BLOCK_EMAIL_VERIFICATION_GUARD_TESTS
