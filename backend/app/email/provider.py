# FILE: backend/app/email/provider.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Email provider adapters and provider error normalization for verified registration
#   SCOPE: Typed delivery requests, Resend/SMTP adapters, disabled-provider guard, and safe provider error mapping
#   DEPENDS: M-001 (settings), httpx, stdlib smtplib
#   LINKS: M-040 (email-delivery), V-M-040
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   EmailMessageRequest - Provider-neutral email send payload
#   EmailDeliveryReceipt - Safe delivery metadata returned by providers
#   EmailDeliveryErrorCode - Stable internal provider failure codes
#   EmailDeliveryError - Typed safe exception for delivery failures
#   map_email_provider_error - Converts HTTP/transport failures into safe internal errors
#   build_email_provider - Builds the configured provider adapter from Settings
#   ResendEmailProvider - Resend HTTP provider implementation
#   SMTPEmailProvider - SMTP provider implementation using stdlib smtplib
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-27 email provider abstraction and safe error mapping
# END_CHANGE_SUMMARY

from __future__ import annotations

import asyncio
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from enum import Enum
from typing import Protocol

import httpx

from app.core.config import Settings, settings


# START_BLOCK_PROVIDER_TYPES
@dataclass(frozen=True)
class EmailMessageRequest:
    """Provider-neutral email request."""

    to_email: str
    subject: str
    html: str
    text: str


@dataclass(frozen=True)
class EmailDeliveryReceipt:
    """Safe provider delivery metadata."""

    provider: str
    message_id: str | None
    status: str


class EmailDeliveryErrorCode(str, Enum):
    """Stable internal email delivery error codes."""

    PROVIDER_DISABLED = "provider_disabled"
    PROVIDER_AUTH = "provider_auth"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_INVALID_REQUEST = "provider_invalid_request"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_TRANSPORT = "provider_transport"
    PROVIDER_UNKNOWN = "provider_unknown"


class EmailDeliveryError(RuntimeError):
    """Typed safe exception for email delivery failures."""

    def __init__(
        self,
        code: EmailDeliveryErrorCode,
        safe_message: str,
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
        self.status_code = status_code


class EmailProvider(Protocol):
    """Async email provider contract."""

    async def send(self, request: EmailMessageRequest) -> EmailDeliveryReceipt:
        """Send an email message and return safe delivery metadata."""
# END_BLOCK_PROVIDER_TYPES


# START_CONTRACT: map_email_provider_error
#   PURPOSE: Map provider HTTP/transport failures to stable safe internal codes
#   INPUTS: exc: BaseException | None - caught exception; status_code: int | None - provider HTTP status
#   OUTPUTS: EmailDeliveryError
#   SIDE_EFFECTS: none
#   LINKS: V-M-040
# END_CONTRACT: map_email_provider_error
# START_BLOCK_MAP_PROVIDER_ERROR
def map_email_provider_error(
    exc: BaseException | None = None,
    *,
    status_code: int | None = None,
) -> EmailDeliveryError:
    """Map provider failures without exposing raw provider bodies."""
    if isinstance(exc, httpx.TimeoutException):
        return EmailDeliveryError(
            EmailDeliveryErrorCode.PROVIDER_TIMEOUT,
            "Email provider timed out",
            status_code=status_code,
        )
    if isinstance(exc, httpx.TransportError):
        return EmailDeliveryError(
            EmailDeliveryErrorCode.PROVIDER_TRANSPORT,
            "Email provider transport failed",
            status_code=status_code,
        )
    if status_code in (401, 403):
        return EmailDeliveryError(
            EmailDeliveryErrorCode.PROVIDER_AUTH,
            "Email provider rejected credentials",
            status_code=status_code,
        )
    if status_code == 429:
        return EmailDeliveryError(
            EmailDeliveryErrorCode.PROVIDER_RATE_LIMITED,
            "Email provider rate limit reached",
            status_code=status_code,
        )
    if status_code is not None and 400 <= status_code < 500:
        return EmailDeliveryError(
            EmailDeliveryErrorCode.PROVIDER_INVALID_REQUEST,
            "Email provider rejected request",
            status_code=status_code,
        )
    if status_code is not None and status_code >= 500:
        return EmailDeliveryError(
            EmailDeliveryErrorCode.PROVIDER_UNAVAILABLE,
            "Email provider unavailable",
            status_code=status_code,
        )
    return EmailDeliveryError(
        EmailDeliveryErrorCode.PROVIDER_UNKNOWN,
        "Email provider failed",
        status_code=status_code,
    )
# END_BLOCK_MAP_PROVIDER_ERROR


# START_CONTRACT: build_email_provider
#   PURPOSE: Build the configured email provider adapter from runtime settings
#   INPUTS: app_settings: Settings - runtime email settings
#   OUTPUTS: EmailProvider
#   SIDE_EFFECTS: none
#   LINKS: M-001, M-040
# END_CONTRACT: build_email_provider
# START_BLOCK_BUILD_PROVIDER
def build_email_provider(app_settings: Settings = settings) -> EmailProvider:
    """Build the configured provider adapter."""
    if app_settings.email_provider == "resend":
        return ResendEmailProvider(app_settings)
    if app_settings.email_provider == "smtp":
        return SMTPEmailProvider(app_settings)
    raise EmailDeliveryError(
        EmailDeliveryErrorCode.PROVIDER_DISABLED,
        "Email provider is disabled",
    )
# END_BLOCK_BUILD_PROVIDER


# START_BLOCK_RESEND_PROVIDER
class ResendEmailProvider:
    """Resend HTTP provider implementation."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings

    def _require_config(self) -> tuple[str, str]:
        if not self.settings.resend_api_key or not self.settings.email_from:
            raise EmailDeliveryError(
                EmailDeliveryErrorCode.PROVIDER_DISABLED,
                "Email provider is not configured",
            )
        return self.settings.resend_api_key, self.settings.email_from

    async def send(self, request: EmailMessageRequest) -> EmailDeliveryReceipt:
        api_key, email_from = self._require_config()
        payload = {
            "from": email_from,
            "to": [request.to_email],
            "subject": request.subject,
            "html": request.html,
            "text": request.text,
        }
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            async with httpx.AsyncClient(
                timeout=self.settings.email_provider_timeout_seconds
            ) as client:
                response = await client.post(
                    self.settings.resend_api_url,
                    json=payload,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise map_email_provider_error(exc) from exc

        if response.status_code >= 400:
            raise map_email_provider_error(status_code=response.status_code)

        message_id = None
        try:
            data = response.json()
            if isinstance(data, dict):
                raw_id = data.get("id")
                message_id = str(raw_id) if raw_id else None
        except ValueError:
            message_id = None

        return EmailDeliveryReceipt(
            provider="resend",
            message_id=message_id,
            status="sent",
        )
# END_BLOCK_RESEND_PROVIDER


# START_BLOCK_SMTP_PROVIDER
class SMTPEmailProvider:
    """SMTP provider implementation using stdlib smtplib."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings

    def _require_config(self) -> str:
        if not self.settings.smtp_host or not self.settings.email_from:
            raise EmailDeliveryError(
                EmailDeliveryErrorCode.PROVIDER_DISABLED,
                "SMTP provider is not configured",
            )
        return self.settings.email_from

    async def send(self, request: EmailMessageRequest) -> EmailDeliveryReceipt:
        email_from = self._require_config()
        await asyncio.to_thread(self._send_sync, request, email_from)
        return EmailDeliveryReceipt(provider="smtp", message_id=None, status="sent")

    def _send_sync(self, request: EmailMessageRequest, email_from: str) -> None:
        message = EmailMessage()
        message["From"] = email_from
        message["To"] = request.to_email
        message["Subject"] = request.subject
        message.set_content(request.text)
        message.add_alternative(request.html, subtype="html")

        try:
            with smtplib.SMTP(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=self.settings.email_provider_timeout_seconds,
            ) as client:
                client.starttls(context=ssl.create_default_context())
                if self.settings.smtp_user and self.settings.smtp_password:
                    client.login(self.settings.smtp_user, self.settings.smtp_password)
                client.send_message(message)
        except TimeoutError as exc:
            raise EmailDeliveryError(
                EmailDeliveryErrorCode.PROVIDER_TIMEOUT,
                "SMTP provider timed out",
            ) from exc
        except smtplib.SMTPAuthenticationError as exc:
            raise EmailDeliveryError(
                EmailDeliveryErrorCode.PROVIDER_AUTH,
                "SMTP provider rejected credentials",
            ) from exc
        except smtplib.SMTPException as exc:
            raise EmailDeliveryError(
                EmailDeliveryErrorCode.PROVIDER_TRANSPORT,
                "SMTP provider transport failed",
            ) from exc
# END_BLOCK_SMTP_PROVIDER
