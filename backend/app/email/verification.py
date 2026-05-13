# FILE: backend/app/email/verification.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Pending email registration, token hashing, risk checks and replay-safe verification foundation
#   SCOPE: Email normalization, domain guard checks, pending-registration persistence, token issue/consume, safe status responses
#   DEPENDS: M-001 (settings/security), M-002 (users model/schema), M-027 (token safety concept), M-040 (email delivery)
#   LINKS: M-041, V-M-041
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   EmailVerificationErrorCode, EmailVerificationError - Typed safe verification failures
#   EmailRiskResult, PendingRegistrationResult, VerificationConsumeResult, RegistrationStatusResult - Result contracts
#   DefaultEmailDomainResolver - Optional MX/DNS resolver with stdlib fallback
#   normalize_email_address - Canonical lower-case email normalization
#   hash_verification_token, generate_verification_token - Token primitives
#   email_risk_check - Syntax/domain/disposable/DNS guard
#   request_registration - Create pending registration and send verification email without active access
#   verify_registration - Consume a token once without Phase-28 user activation
#   registration_status - Return safe pending-registration status
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-27 pending verified-registration foundation without /register cutover
# END_CHANGE_SUMMARY

from __future__ import annotations

import asyncio
import hashlib
import hmac
import re
import secrets
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Awaitable, Callable, Protocol

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.core.security import hash_password
from app.email.provider import EmailDeliveryReceipt
from app.email.service import mask_email_for_logs, send_verification_email
from app.users.models import (
    PendingEmailRegistration,
    PendingEmailRegistrationStatus,
    User,
)
from app.users.schemas import UserCreate


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# START_BLOCK_VERIFICATION_TYPES
class EmailVerificationErrorCode(str, Enum):
    """Stable email verification failure codes."""

    EMAIL_REQUIRED = "email_required"
    EMAIL_INVALID = "email_invalid"
    DOMAIN_NOT_ALLOWED = "domain_not_allowed"
    DOMAIN_BLOCKED = "domain_blocked"
    DISPOSABLE_DOMAIN = "disposable_domain"
    DOMAIN_NO_DNS = "domain_no_dns"
    EMAIL_UNAVAILABLE = "email_unavailable"
    TOKEN_INVALID = "token_invalid"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_REPLAYED = "token_replayed"


class EmailVerificationError(ValueError):
    """Typed safe exception for verified-registration failures."""

    def __init__(self, code: EmailVerificationErrorCode, safe_message: str) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


@dataclass(frozen=True)
class EmailRiskResult:
    """Email risk-check result."""

    allowed: bool
    normalized_email: str
    domain: str
    reason: EmailVerificationErrorCode | None = None
    dns_checked: bool = False
    allowlist_override: bool = False


@dataclass(frozen=True)
class PendingRegistrationResult:
    """Safe pending-registration response."""

    email: str
    status: PendingEmailRegistrationStatus
    expires_at: datetime
    delivery: EmailDeliveryReceipt


@dataclass(frozen=True)
class VerificationConsumeResult:
    """Safe verification-token consume response."""

    email: str
    status: PendingEmailRegistrationStatus
    consumed_at: datetime


@dataclass(frozen=True)
class RegistrationStatusResult:
    """Safe pending-registration status response."""

    email: str
    status: PendingEmailRegistrationStatus | None
    expires_at: datetime | None
    reason: str | None = None


class EmailDomainResolver(Protocol):
    """Email domain resolver contract for tests and default DNS checks."""

    async def has_mx_or_address(self, domain: str) -> bool:
        """Return whether the domain has MX or address DNS evidence."""


EmailSender = Callable[..., Awaitable[EmailDeliveryReceipt]]
# END_BLOCK_VERIFICATION_TYPES


# START_BLOCK_DOMAIN_RESOLVER
class DefaultEmailDomainResolver:
    """Best-effort MX/DNS resolver with optional dnspython support."""

    async def has_mx_or_address(self, domain: str) -> bool:
        """Return whether the domain has MX or address DNS evidence."""
        return await asyncio.to_thread(self._has_mx_or_address_sync, domain)

    def _has_mx_or_address_sync(self, domain: str) -> bool:
        try:
            import dns.resolver  # type: ignore[import-not-found]

            try:
                dns.resolver.resolve(domain, "MX")
                return True
            except Exception:
                pass
        except Exception:
            pass

        try:
            socket.getaddrinfo(domain, None)
            return True
        except OSError:
            return False
# END_BLOCK_DOMAIN_RESOLVER


# START_CONTRACT: normalize_email_address
#   PURPOSE: Normalize a submitted email for lookup and pending-registration storage
#   INPUTS: email: str | None - submitted email address
#   OUTPUTS: str
#   SIDE_EFFECTS: raises EmailVerificationError for missing or malformed input
#   LINKS: M-041, V-M-041
# END_CONTRACT: normalize_email_address
# START_BLOCK_NORMALIZE_EMAIL
def normalize_email_address(email: str | None) -> str:
    """Normalize email address for KrotPN identity checks."""
    if email is None:
        raise EmailVerificationError(
            EmailVerificationErrorCode.EMAIL_REQUIRED,
            "Email is required",
        )
    normalized = email.strip().lower()
    if not EMAIL_RE.match(normalized):
        raise EmailVerificationError(
            EmailVerificationErrorCode.EMAIL_INVALID,
            "Email address is invalid",
        )
    local, domain = normalized.rsplit("@", 1)
    try:
        ascii_domain = domain.encode("idna").decode("ascii").rstrip(".")
    except UnicodeError as exc:
        raise EmailVerificationError(
            EmailVerificationErrorCode.EMAIL_INVALID,
            "Email address is invalid",
        ) from exc
    return f"{local}@{ascii_domain}"
# END_BLOCK_NORMALIZE_EMAIL


# START_CONTRACT: generate_verification_token
#   PURPOSE: Generate an opaque one-time verification token
#   INPUTS: none
#   OUTPUTS: str
#   SIDE_EFFECTS: consumes secure randomness
#   LINKS: M-041, V-M-041
# END_CONTRACT: generate_verification_token
# START_BLOCK_TOKEN_PRIMITIVES
def generate_verification_token() -> str:
    """Generate an opaque verification token."""
    return secrets.token_urlsafe(32)


def hash_verification_token(
    token: str,
    *,
    app_settings: Settings = settings,
) -> str:
    """Hash a verification token with HMAC so plaintext is never persisted."""
    return hmac.new(
        app_settings.secret_key.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
# END_BLOCK_TOKEN_PRIMITIVES


# START_CONTRACT: email_risk_check
#   PURPOSE: Evaluate syntax, domain allow/deny/disposable policy and optional DNS evidence
#   INPUTS: email: str | None; app_settings: Settings; resolver: EmailDomainResolver | None
#   OUTPUTS: EmailRiskResult
#   SIDE_EFFECTS: optional DNS lookup through resolver
#   LINKS: M-041, V-M-041
# END_CONTRACT: email_risk_check
# START_BLOCK_EMAIL_RISK_CHECK
async def email_risk_check(
    email: str | None,
    *,
    app_settings: Settings = settings,
    resolver: EmailDomainResolver | None = None,
) -> EmailRiskResult:
    """Evaluate configured email risk policy."""
    normalized = normalize_email_address(email)
    domain = normalized.rsplit("@", 1)[1]
    allowed_domains = set(app_settings.email_allowed_domains)
    blocked_domains = set(app_settings.email_blocked_domains)
    disposable_domains = set(app_settings.email_disposable_domains)

    allowlist_override = bool(allowed_domains and domain in allowed_domains)
    if allowed_domains and not allowlist_override:
        logger.info(
            "[M-041][email_risk_check][BLOCK_DOMAIN] "
            f"email={mask_email_for_logs(normalized)} reason=domain_not_allowed"
        )
        return EmailRiskResult(
            allowed=False,
            normalized_email=normalized,
            domain=domain,
            reason=EmailVerificationErrorCode.DOMAIN_NOT_ALLOWED,
        )

    if not allowlist_override and domain in blocked_domains:
        logger.info(
            "[M-041][email_risk_check][BLOCK_DOMAIN] "
            f"email={mask_email_for_logs(normalized)} reason=domain_blocked"
        )
        return EmailRiskResult(
            allowed=False,
            normalized_email=normalized,
            domain=domain,
            reason=EmailVerificationErrorCode.DOMAIN_BLOCKED,
        )

    if (
        not allowlist_override
        and app_settings.email_disposable_domain_guard_enabled
        and domain in disposable_domains
    ):
        logger.info(
            "[M-041][email_risk_check][BLOCK_DOMAIN] "
            f"email={mask_email_for_logs(normalized)} reason=disposable_domain"
        )
        return EmailRiskResult(
            allowed=False,
            normalized_email=normalized,
            domain=domain,
            reason=EmailVerificationErrorCode.DISPOSABLE_DOMAIN,
        )

    dns_checked = False
    if app_settings.email_dns_check_enabled and not allowlist_override:
        dns_checked = True
        domain_resolver = resolver or DefaultEmailDomainResolver()
        has_dns = await domain_resolver.has_mx_or_address(domain)
        if not has_dns:
            logger.info(
                "[M-041][email_risk_check][BLOCK_DOMAIN] "
                f"email={mask_email_for_logs(normalized)} reason=domain_no_dns"
            )
            return EmailRiskResult(
                allowed=False,
                normalized_email=normalized,
                domain=domain,
                reason=EmailVerificationErrorCode.DOMAIN_NO_DNS,
                dns_checked=True,
            )

    return EmailRiskResult(
        allowed=True,
        normalized_email=normalized,
        domain=domain,
        dns_checked=dns_checked,
        allowlist_override=allowlist_override,
    )
# END_BLOCK_EMAIL_RISK_CHECK


# START_CONTRACT: request_registration
#   PURPOSE: Create pending registration and send verification email without active KrotPN access
#   INPUTS: session: AsyncSession; data: UserCreate; email_sender: EmailSender; resolver: EmailDomainResolver | None
#   OUTPUTS: PendingRegistrationResult
#   SIDE_EFFECTS: writes PendingEmailRegistration and sends email through M-040
#   LINKS: M-041, M-040, V-M-041
# END_CONTRACT: request_registration
# START_BLOCK_REQUEST_REGISTRATION
async def request_registration(
    session: AsyncSession,
    data: UserCreate,
    *,
    email_sender: EmailSender = send_verification_email,
    resolver: EmailDomainResolver | None = None,
    app_settings: Settings = settings,
    now: datetime | None = None,
) -> PendingRegistrationResult:
    """Create a pending registration record and send a verification email."""
    risk = await email_risk_check(
        str(data.email) if data.email is not None else None,
        app_settings=app_settings,
        resolver=resolver,
    )
    logger.info(
        "[M-041][request_registration][EMAIL_RISK_CHECK] "
        f"email={mask_email_for_logs(risk.normalized_email)} allowed={risk.allowed}"
    )
    if not risk.allowed:
        raise EmailVerificationError(
            risk.reason or EmailVerificationErrorCode.EMAIL_INVALID,
            "Registration email is not allowed",
        )

    existing_user_result = await session.execute(
        select(User).where(User.email == risk.normalized_email)
    )
    if existing_user_result.scalar_one_or_none() is not None:
        raise EmailVerificationError(
            EmailVerificationErrorCode.EMAIL_UNAVAILABLE,
            "Registration cannot be completed",
        )

    issued_at = now or datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(
        minutes=app_settings.email_verification_token_ttl_minutes
    )
    token = generate_verification_token()
    token_hash = hash_verification_token(token, app_settings=app_settings)

    pending = PendingEmailRegistration(
        email=risk.normalized_email,
        token_hash=token_hash,
        password_hash=hash_password(data.password),
        name=data.name,
        language=data.language,
        referral_code=data.referral_code,
        status=PendingEmailRegistrationStatus.PENDING,
        expires_at=expires_at,
        created_at=issued_at,
        updated_at=issued_at,
    )
    session.add(pending)
    await session.flush()

    logger.info(
        "[M-041][request_registration][STORE_PENDING] "
        f"email={mask_email_for_logs(risk.normalized_email)} pending_id={pending.id}"
    )

    delivery = await email_sender(
        risk.normalized_email,
        token,
        language=data.language,
        app_settings=app_settings,
    )
    return PendingRegistrationResult(
        email=risk.normalized_email,
        status=pending.status,
        expires_at=expires_at,
        delivery=delivery,
    )
# END_BLOCK_REQUEST_REGISTRATION


# START_CONTRACT: verify_registration
#   PURPOSE: Consume a verification token once without Phase-28 account activation side effects
#   INPUTS: session: AsyncSession; token: str; app_settings: Settings; now: datetime | None
#   OUTPUTS: VerificationConsumeResult
#   SIDE_EFFECTS: marks pending registration verified or expired
#   LINKS: M-041, V-M-041
# END_CONTRACT: verify_registration
# START_BLOCK_VERIFY_REGISTRATION
async def verify_registration(
    session: AsyncSession,
    token: str,
    *,
    app_settings: Settings = settings,
    now: datetime | None = None,
) -> VerificationConsumeResult:
    """Consume a pending-registration token once."""
    token_hash = hash_verification_token(token, app_settings=app_settings)
    result = await session.execute(
        select(PendingEmailRegistration).where(
            PendingEmailRegistration.token_hash == token_hash
        )
    )
    pending = result.scalar_one_or_none()
    if pending is None:
        raise EmailVerificationError(
            EmailVerificationErrorCode.TOKEN_INVALID,
            "Verification token is invalid",
        )

    checked_at = now or datetime.now(timezone.utc)
    expires_at = _as_aware_utc(pending.expires_at)
    if pending.status != PendingEmailRegistrationStatus.PENDING or pending.consumed_at:
        logger.warning(
            "[M-041][verify_registration][TOKEN_REPLAYED] "
            f"email={mask_email_for_logs(pending.email)} pending_id={pending.id}"
        )
        raise EmailVerificationError(
            EmailVerificationErrorCode.TOKEN_REPLAYED,
            "Verification token was already used",
        )
    if expires_at <= checked_at:
        pending.status = PendingEmailRegistrationStatus.EXPIRED
        pending.updated_at = checked_at
        await session.flush()
        raise EmailVerificationError(
            EmailVerificationErrorCode.TOKEN_EXPIRED,
            "Verification token has expired",
        )

    pending.status = PendingEmailRegistrationStatus.VERIFIED
    pending.consumed_at = checked_at
    pending.updated_at = checked_at
    await session.flush()

    logger.info(
        "[M-041][verify_registration][CONSUME_TOKEN] "
        f"email={mask_email_for_logs(pending.email)} pending_id={pending.id}"
    )
    return VerificationConsumeResult(
        email=pending.email,
        status=pending.status,
        consumed_at=checked_at,
    )
# END_BLOCK_VERIFY_REGISTRATION


# START_CONTRACT: registration_status
#   PURPOSE: Return safe pending registration state by email
#   INPUTS: session: AsyncSession; email: str | None; now: datetime | None
#   OUTPUTS: RegistrationStatusResult
#   SIDE_EFFECTS: marks expired pending records expired
#   LINKS: M-041, V-M-041
# END_CONTRACT: registration_status
# START_BLOCK_REGISTRATION_STATUS
async def registration_status(
    session: AsyncSession,
    email: str | None,
    *,
    now: datetime | None = None,
) -> RegistrationStatusResult:
    """Return safe pending-registration status."""
    normalized = normalize_email_address(email)
    result = await session.execute(
        select(PendingEmailRegistration)
        .where(PendingEmailRegistration.email == normalized)
        .order_by(PendingEmailRegistration.created_at.desc())
    )
    pending = result.scalars().first()
    if pending is None:
        return RegistrationStatusResult(email=normalized, status=None, expires_at=None)

    checked_at = now or datetime.now(timezone.utc)
    expires_at = _as_aware_utc(pending.expires_at)
    if (
        pending.status == PendingEmailRegistrationStatus.PENDING
        and expires_at <= checked_at
    ):
        pending.status = PendingEmailRegistrationStatus.EXPIRED
        pending.updated_at = checked_at
        await session.flush()

    return RegistrationStatusResult(
        email=normalized,
        status=pending.status,
        expires_at=expires_at,
        reason=pending.risk_reason,
    )
# END_BLOCK_REGISTRATION_STATUS


# START_BLOCK_TIME_HELPERS
def _as_aware_utc(value: datetime) -> datetime:
    """Normalize DB datetime values to timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
# END_BLOCK_TIME_HELPERS
