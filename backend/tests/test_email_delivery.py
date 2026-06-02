"""
MODULE_CONTRACT
- PURPOSE: Verify Phase-27/Phase-44/Phase-51 email delivery foundation.
- SCOPE: Unit tests for verification/password reset templates, brand-logo rendering, fake-provider dispatch, Resend request shape, provider-disabled guard, and typed provider error mapping.
- DEPENDS: app.email.service, app.email.provider, app.core.config.
- LINKS: V-M-040, V-M-069.

MODULE_MAP
- test_send_verification_email_uses_template_and_redacts_token_from_logs: Verifies fake-provider dispatch, brand-logo HTML, and token redaction.
- test_send_password_reset_email_uses_template_and_redacts_token_from_logs: Verifies Phase-44 reset dispatch, brand-logo HTML, and token redaction.
- test_resend_provider_builds_production_request_shape: Verifies Resend URL, sender, payload, Bearer auth, and safe receipt metadata.
- test_send_verification_email_blocks_when_provider_disabled: Verifies disabled provider fails before a network call.
- test_map_email_provider_error_returns_stable_safe_codes: Verifies HTTP status mapping.

CHANGE_SUMMARY
- 2026-06-02: Added Phase-51 email logo assertions for verification and reset templates.
- 2026-06-01: Added Phase-44 password reset email delivery tests.
- 2026-05-17: Added Phase-36 Resend production request-shape test.
- 2026-05-13: Added Phase-27 email delivery tests.
"""

import pytest
from loguru import logger

from app.core.config import Settings
from app.email.provider import (
    EmailDeliveryError,
    EmailDeliveryErrorCode,
    EmailDeliveryReceipt,
    EmailMessageRequest,
    ResendEmailProvider,
    map_email_provider_error,
)
from app.email import provider as provider_module
from app.email.service import send_password_reset_email, send_verification_email


class RecordingProvider:
    def __init__(self) -> None:
        self.requests: list[EmailMessageRequest] = []

    async def send(self, request: EmailMessageRequest) -> EmailDeliveryReceipt:
        self.requests.append(request)
        return EmailDeliveryReceipt(
            provider="fake",
            message_id="msg_test",
            status="sent",
        )


def _settings(**overrides) -> Settings:
    data = {
        "secret_key": "test-secret-key-with-enough-length",
        "app_name": "KrotPN",
        "frontend_url": "https://krotpn.xyz",
        "email_provider": "disabled",
        **overrides,
    }
    return Settings(**data)


# START_BLOCK_EMAIL_DELIVERY_TESTS
@pytest.mark.asyncio
async def test_send_verification_email_uses_template_and_redacts_token_from_logs():
    provider = RecordingProvider()
    token = "secret-token-that-must-not-be-logged"
    log_lines: list[str] = []
    sink_id = logger.add(lambda message: log_lines.append(str(message)), format="{message}")

    try:
        receipt = await send_verification_email(
            "friend@example.com",
            token,
            provider=provider,
            app_settings=_settings(email_provider="resend"),
        )
    finally:
        logger.remove(sink_id)

    assert receipt.provider == "fake"
    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert request.to_email == "friend@example.com"
    assert "KrotPN" in request.subject
    assert 'src="https://krotpn.xyz/brand/email-logo.png"' in request.html
    assert 'alt="KrotPN"' in request.html
    assert "https://krotpn.xyz/verify-email?token=secret-token-that-must-not-be-logged" in request.text
    assert "brand/email-logo.png" not in request.text

    joined_logs = "\n".join(log_lines)
    assert "[M-040][send_verification_email][BUILD_REQUEST]" in joined_logs
    assert "[M-040][send_verification_email][POST_PROVIDER]" in joined_logs
    assert "[EmailTemplates][build_verification_template][RENDER_BRANDED_VERIFICATION]" in joined_logs
    assert token not in joined_logs


@pytest.mark.asyncio
async def test_send_password_reset_email_uses_template_and_redacts_token_from_logs():
    provider = RecordingProvider()
    token = "reset-token-that-must-not-be-logged"
    log_lines: list[str] = []
    sink_id = logger.add(lambda message: log_lines.append(str(message)), format="{message}")

    try:
        receipt = await send_password_reset_email(
            "friend@example.com",
            token,
            provider=provider,
            app_settings=_settings(email_provider="resend"),
        )
    finally:
        logger.remove(sink_id)

    assert receipt.provider == "fake"
    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert request.to_email == "friend@example.com"
    assert "KrotPN" in request.subject
    assert 'src="https://krotpn.xyz/brand/email-logo.png"' in request.html
    assert 'alt="KrotPN"' in request.html
    assert "https://krotpn.xyz/reset-password?token=reset-token-that-must-not-be-logged" in request.text
    assert "brand/email-logo.png" not in request.text

    joined_logs = "\n".join(log_lines)
    assert "[M-040][send_password_reset_email][BUILD_REQUEST]" in joined_logs
    assert "[M-040][send_password_reset_email][POST_PROVIDER]" in joined_logs
    assert "[EmailTemplates][build_password_reset_template][RENDER_PASSWORD_RESET]" in joined_logs
    assert token not in joined_logs


@pytest.mark.asyncio
async def test_resend_provider_builds_production_request_shape(monkeypatch):
    calls: list[dict] = []

    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, str]:
            return {"id": "email_msg_123"}

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, *, json: dict, headers: dict):
            calls.append(
                {
                    "url": url,
                    "json": json,
                    "headers": headers,
                    "timeout": self.timeout,
                }
            )
            return FakeResponse()

    monkeypatch.setattr(provider_module.httpx, "AsyncClient", FakeAsyncClient)
    app_settings = _settings(
        email_provider="resend",
        resend_api_key="resend_test_secret_123",
        resend_api_url="https://api.resend.com/emails",
        email_from="noreply@krotpn.xyz",
        email_provider_timeout_seconds=7.0,
    )

    receipt = await ResendEmailProvider(app_settings).send(
        EmailMessageRequest(
            to_email="friend@example.com",
            subject="Verify KrotPN",
            html="<p>hello</p>",
            text="hello",
        )
    )

    assert receipt.provider == "resend"
    assert receipt.message_id == "email_msg_123"
    assert receipt.status == "sent"
    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://api.resend.com/emails"
    assert call["headers"] == {"Authorization": "Bearer resend_test_secret_123"}
    assert call["json"] == {
        "from": "noreply@krotpn.xyz",
        "to": ["friend@example.com"],
        "subject": "Verify KrotPN",
        "html": "<p>hello</p>",
        "text": "hello",
    }
    assert "resend_test_secret_123" not in str(call["json"])
    assert call["timeout"] == 7.0


@pytest.mark.asyncio
async def test_send_verification_email_blocks_when_provider_disabled():
    with pytest.raises(EmailDeliveryError) as exc_info:
        await send_verification_email(
            "friend@example.com",
            "secret-token",
            app_settings=_settings(email_provider="disabled"),
        )

    assert exc_info.value.code == EmailDeliveryErrorCode.PROVIDER_DISABLED
    assert "secret-token" not in str(exc_info.value)


def test_map_email_provider_error_returns_stable_safe_codes():
    assert map_email_provider_error(status_code=401).code == EmailDeliveryErrorCode.PROVIDER_AUTH
    assert map_email_provider_error(status_code=422).code == EmailDeliveryErrorCode.PROVIDER_INVALID_REQUEST
    assert map_email_provider_error(status_code=429).code == EmailDeliveryErrorCode.PROVIDER_RATE_LIMITED
    assert map_email_provider_error(status_code=500).code == EmailDeliveryErrorCode.PROVIDER_UNAVAILABLE
    assert map_email_provider_error(status_code=400).code == EmailDeliveryErrorCode.PROVIDER_INVALID_REQUEST
# END_BLOCK_EMAIL_DELIVERY_TESTS
