"""
Password reset lifecycle for email/password users.

# FILE: backend/app/users/password_reset.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Create, deliver, consume, expire, and replay-protect one-time password reset tokens
#   SCOPE: Token generation, HMAC hashing, generic request result, reset validation, and safe errors
#   DEPENDS: M-001 (settings/security), M-002 (users models/password policy), M-040 (email service)
#   LINKS: M-002, M-040, M-062, V-M-062
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   PasswordResetErrorCode, PasswordResetError - Typed safe password reset failures
#   PasswordResetRequestResult - Generic request outcome without account-enumeration payloads
#   generate_password_reset_token, hash_password_reset_token - Opaque token primitives
#   request_password_reset - Create reset token and send email when an active email account exists
#   reset_password_with_token - Consume one valid token and set a new strong password
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-44 password reset lifecycle
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import hmac
import secrets
from typing import Protocol

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.core.security import hash_password
from app.email.provider import EmailDeliveryReceipt
from app.email.service import mask_email_for_logs, send_password_reset_email
from app.email.verification import normalize_email_address
from app.users.models import PasswordResetToken, PasswordResetTokenStatus, User
from app.users.password_policy import validate_password_strength


class PasswordResetErrorCode(str, Enum):
    """Stable password reset failure codes."""

    TOKEN_INVALID = "token_invalid"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_REPLAYED = "token_replayed"
    USER_UNAVAILABLE = "user_unavailable"


class PasswordResetError(Exception):
    """Password reset failure with safe API metadata."""

    def __init__(self, code: PasswordResetErrorCode, safe_message: str) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


class PasswordResetSender(Protocol):
    async def __call__(
        self,
        to_email: str,
        reset_token: str,
        *,
        language: str = "ru",
        app_settings: Settings = settings,
    ) -> EmailDeliveryReceipt:
        """Protocol for reset email delivery implementations."""


@dataclass(frozen=True)
class PasswordResetRequestResult:
    """Generic password reset request outcome."""

    email: str
    token_created: bool
    expires_at: datetime | None
    delivery: EmailDeliveryReceipt | None = None


# START_CONTRACT: generate_password_reset_token
#   PURPOSE: Generate an opaque one-time password reset token
#   INPUTS: none
#   OUTPUTS: str
#   SIDE_EFFECTS: cryptographic randomness
#   LINKS: M-002, V-M-062
# END_CONTRACT: generate_password_reset_token
# START_BLOCK_PASSWORD_RESET_TOKEN_PRIMITIVES
def generate_password_reset_token() -> str:
    """Generate an opaque reset token."""
    return secrets.token_urlsafe(32)


def hash_password_reset_token(
    token: str,
    *,
    app_settings: Settings = settings,
) -> str:
    """Hash a reset token with HMAC so plaintext is never persisted."""
    return hmac.new(
        app_settings.secret_key.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
# END_BLOCK_PASSWORD_RESET_TOKEN_PRIMITIVES


# START_CONTRACT: request_password_reset
#   PURPOSE: Create a reset token and send email when the account exists while returning a generic public result
#   INPUTS: session: AsyncSession; email: str; email_sender: PasswordResetSender; app_settings: Settings; now: datetime | None
#   OUTPUTS: PasswordResetRequestResult
#   SIDE_EFFECTS: writes PasswordResetToken and sends reset email for active email/password users
#   LINKS: M-002, M-040, M-062, V-M-062
# END_CONTRACT: request_password_reset
# START_BLOCK_REQUEST_PASSWORD_RESET
async def request_password_reset(
    session: AsyncSession,
    email: str,
    *,
    email_sender: PasswordResetSender = send_password_reset_email,
    app_settings: Settings = settings,
    now: datetime | None = None,
) -> PasswordResetRequestResult:
    """Create and send a password reset token when an eligible account exists."""
    normalized_email = normalize_email_address(email)
    issued_at = now or datetime.now(timezone.utc)

    result = await session.execute(select(User).where(User.email == normalized_email))
    user = result.scalar_one_or_none()
    if user is None or user.password_hash is None or not user.is_active:
        logger.info(
            "[UsersService][request_password_reset][GENERIC_ACCEPT] "
            f"email={mask_email_for_logs(normalized_email)} eligible=false"
        )
        return PasswordResetRequestResult(
            email=normalized_email,
            token_created=False,
            expires_at=None,
        )

    await _expire_pending_tokens(session, int(user.id), issued_at)

    expires_at = issued_at + timedelta(minutes=app_settings.password_reset_token_ttl_minutes)
    token = generate_password_reset_token()
    reset_record = PasswordResetToken(
        user_id=int(user.id),
        email=normalized_email,
        token_hash=hash_password_reset_token(token, app_settings=app_settings),
        status=PasswordResetTokenStatus.PENDING,
        created_at=issued_at,
        updated_at=issued_at,
        expires_at=expires_at,
    )
    session.add(reset_record)
    await session.flush()

    delivery = await email_sender(
        normalized_email,
        token,
        language=user.language or "ru",
        app_settings=app_settings,
    )
    logger.info(
        "[UsersService][request_password_reset][TOKEN_STORED] "
        f"email={mask_email_for_logs(normalized_email)} reset_id={reset_record.id} delivery_status={delivery.status}"
    )
    return PasswordResetRequestResult(
        email=normalized_email,
        token_created=True,
        expires_at=expires_at,
        delivery=delivery,
    )
# END_BLOCK_REQUEST_PASSWORD_RESET


# START_CONTRACT: reset_password_with_token
#   PURPOSE: Consume a one-time token and set a new strong account password
#   INPUTS: session: AsyncSession; token: str; new_password: str; app_settings: Settings; now: datetime | None
#   OUTPUTS: User
#   SIDE_EFFECTS: updates User.password_hash and PasswordResetToken lifecycle fields
#   LINKS: M-002, M-062, V-M-062
# END_CONTRACT: reset_password_with_token
# START_BLOCK_RESET_PASSWORD_WITH_TOKEN
async def reset_password_with_token(
    session: AsyncSession,
    token: str,
    new_password: str,
    *,
    app_settings: Settings = settings,
    now: datetime | None = None,
) -> User:
    """Consume a reset token and set a new password."""
    checked_at = now or datetime.now(timezone.utc)
    token_hash = hash_password_reset_token(token, app_settings=app_settings)
    result = await session.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    reset_record = result.scalar_one_or_none()
    if reset_record is None:
        raise PasswordResetError(
            PasswordResetErrorCode.TOKEN_INVALID,
            "Ссылка для сброса пароля недействительна",
        )

    if reset_record.status != PasswordResetTokenStatus.PENDING or reset_record.consumed_at:
        logger.warning(
            "[UsersService][reset_password][TOKEN_REPLAYED] "
            f"email={mask_email_for_logs(reset_record.email)} reset_id={reset_record.id}"
        )
        raise PasswordResetError(
            PasswordResetErrorCode.TOKEN_REPLAYED,
            "Ссылка для сброса пароля уже использована",
        )

    expires_at = _as_aware_utc(reset_record.expires_at)
    if expires_at <= checked_at:
        reset_record.status = PasswordResetTokenStatus.EXPIRED
        reset_record.updated_at = checked_at
        await session.flush()
        raise PasswordResetError(
            PasswordResetErrorCode.TOKEN_EXPIRED,
            "Срок действия ссылки для сброса пароля истёк",
        )

    user = await session.get(User, reset_record.user_id)
    if user is None or not user.is_active:
        raise PasswordResetError(
            PasswordResetErrorCode.USER_UNAVAILABLE,
            "Аккаунт недоступен для сброса пароля",
        )

    validate_password_strength(new_password, email=user.email, name=user.name)
    user.password_hash = hash_password(new_password)
    user.updated_at = checked_at
    reset_record.status = PasswordResetTokenStatus.CONSUMED
    reset_record.consumed_at = checked_at
    reset_record.updated_at = checked_at
    await session.flush()
    await session.refresh(user)
    return user
# END_BLOCK_RESET_PASSWORD_WITH_TOKEN


# START_BLOCK_PASSWORD_RESET_HELPERS
async def _expire_pending_tokens(
    session: AsyncSession,
    user_id: int,
    checked_at: datetime,
) -> None:
    """Expire older pending reset tokens for the same account."""
    result = await session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.status == PasswordResetTokenStatus.PENDING,
        )
    )
    for reset_record in result.scalars().all():
        reset_record.status = PasswordResetTokenStatus.EXPIRED
        reset_record.updated_at = checked_at
    await session.flush()


def _as_aware_utc(value: datetime) -> datetime:
    """Normalize DB datetime values to timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
# END_BLOCK_PASSWORD_RESET_HELPERS
