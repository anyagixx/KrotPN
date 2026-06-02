# FILE: backend/app/email/service.py
# VERSION: 1.2.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Email delivery orchestration for one-time account security messages
#   SCOPE: Verification/password-reset URL construction, template rendering, provider dispatch, safe telemetry and token redaction boundaries
#   DEPENDS: M-001 (settings), M-040 provider/templates, M-069 brand assets
#   LINKS: M-040, M-069, V-M-040, V-M-069
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   mask_email_for_logs - Redact local email parts for safe telemetry
#   build_verification_url - Build frontend verification URL from token and settings
#   send_verification_email - Render and dispatch verification email through configured provider
#   build_password_reset_url - Build frontend password reset URL from token and settings
#   send_password_reset_email - Render and dispatch password reset email through configured provider
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.2.0 - Passed configured frontend origin into Phase-51 email brand logo templates
#   LAST_CHANGE: v1.1.0 - Added Phase-44 password reset email delivery service
#   LAST_CHANGE: v1.0.0 - Added Phase-27 verification email delivery service
# END_CHANGE_SUMMARY

from urllib.parse import urlencode

from loguru import logger

from app.core.config import Settings, settings
from app.email.provider import (
    EmailDeliveryError,
    EmailDeliveryReceipt,
    EmailMessageRequest,
    EmailProvider,
    build_email_provider,
)
from app.email.templates import build_password_reset_template, build_verification_template


# START_CONTRACT: mask_email_for_logs
#   PURPOSE: Redact email local parts before logging
#   INPUTS: email: str - normalized or raw email address
#   OUTPUTS: str
#   SIDE_EFFECTS: none
#   LINKS: V-M-040, V-M-041
# END_CONTRACT: mask_email_for_logs
# START_BLOCK_MASK_EMAIL
def mask_email_for_logs(email: str) -> str:
    """Mask an email address for logs."""
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if not local:
        masked_local = "***"
    elif len(local) == 1:
        masked_local = f"{local[0]}***"
    else:
        masked_local = f"{local[0]}***{local[-1]}"
    return f"{masked_local}@{domain.lower()}"
# END_BLOCK_MASK_EMAIL


# START_CONTRACT: build_verification_url
#   PURPOSE: Build the one-time frontend verification URL
#   INPUTS: token: str - plaintext one-time token; app_settings: Settings - URL settings
#   OUTPUTS: str
#   SIDE_EFFECTS: none
#   LINKS: M-040, M-041
# END_CONTRACT: build_verification_url
# START_BLOCK_BUILD_VERIFICATION_URL
def build_verification_url(token: str, app_settings: Settings = settings) -> str:
    """Build a verification URL without logging the token."""
    base_url = (
        app_settings.email_verification_url_base
        or f"{app_settings.frontend_url.rstrip('/')}/verify-email"
    )
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode({'token': token})}"
# END_BLOCK_BUILD_VERIFICATION_URL


# START_CONTRACT: build_password_reset_url
#   PURPOSE: Build the one-time frontend password reset URL
#   INPUTS: token: str - plaintext one-time token; app_settings: Settings - URL settings
#   OUTPUTS: str
#   SIDE_EFFECTS: none
#   LINKS: M-040, M-062
# END_CONTRACT: build_password_reset_url
# START_BLOCK_BUILD_PASSWORD_RESET_URL
def build_password_reset_url(token: str, app_settings: Settings = settings) -> str:
    """Build a password reset URL without logging the token."""
    base_url = (
        app_settings.password_reset_url_base
        or f"{app_settings.frontend_url.rstrip('/')}/reset-password"
    )
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode({'token': token})}"
# END_BLOCK_BUILD_PASSWORD_RESET_URL


# START_CONTRACT: send_verification_email
#   PURPOSE: Send a one-time verification email through the configured provider
#   INPUTS: to_email: str - normalized recipient; verification_token: str - one-time token; language: str - template language; provider: EmailProvider | None - test/provider override; app_settings: Settings
#   OUTPUTS: EmailDeliveryReceipt
#   SIDE_EFFECTS: provider network call unless provider override is fake
#   LINKS: M-040, M-069, V-M-040, V-M-069
# END_CONTRACT: send_verification_email
# START_BLOCK_SEND_VERIFICATION_EMAIL
async def send_verification_email(
    to_email: str,
    verification_token: str,
    *,
    language: str = "ru",
    provider: EmailProvider | None = None,
    app_settings: Settings = settings,
) -> EmailDeliveryReceipt:
    """Render and send a registration verification email."""
    try:
        delivery_provider = provider or build_email_provider(app_settings)
    except EmailDeliveryError as exc:
        logger.warning(
            "[M-040][send_verification_email][PROVIDER_DISABLED] "
            f"to_email={mask_email_for_logs(to_email)} code={exc.code.value}"
        )
        raise

    verification_url = build_verification_url(verification_token, app_settings)
    template = build_verification_template(
        verification_url,
        language=language,
        app_name=app_settings.app_name,
        brand_base_url=app_settings.frontend_url,
    )

    logger.info(
        "[M-040][send_verification_email][BUILD_REQUEST] "
        f"to_email={mask_email_for_logs(to_email)} provider={app_settings.email_provider}"
    )

    try:
        receipt = await delivery_provider.send(
            EmailMessageRequest(
                to_email=to_email,
                subject=template.subject,
                html=template.html,
                text=template.text,
            )
        )
    except EmailDeliveryError as exc:
        marker = (
            "PROVIDER_DISABLED"
            if exc.code.value == "provider_disabled"
            else "MAP_PROVIDER_ERROR"
        )
        logger.warning(
            f"[M-040][send_verification_email][{marker}] "
            f"to_email={mask_email_for_logs(to_email)} code={exc.code.value}"
        )
        raise

    logger.info(
        "[M-040][send_verification_email][POST_PROVIDER] "
        f"to_email={mask_email_for_logs(to_email)} provider={receipt.provider} status={receipt.status}"
    )
    return receipt
# END_BLOCK_SEND_VERIFICATION_EMAIL


# START_CONTRACT: send_password_reset_email
#   PURPOSE: Send a one-time password reset email through the configured provider
#   INPUTS: to_email: str - normalized recipient; reset_token: str - one-time token; language: str - template language; provider: EmailProvider | None - test/provider override; app_settings: Settings
#   OUTPUTS: EmailDeliveryReceipt
#   SIDE_EFFECTS: provider network call unless provider override is fake
#   LINKS: M-040, M-062, M-069, V-M-062, V-M-069
# END_CONTRACT: send_password_reset_email
# START_BLOCK_SEND_PASSWORD_RESET_EMAIL
async def send_password_reset_email(
    to_email: str,
    reset_token: str,
    *,
    language: str = "ru",
    provider: EmailProvider | None = None,
    app_settings: Settings = settings,
) -> EmailDeliveryReceipt:
    """Render and send a password reset email."""
    try:
        delivery_provider = provider or build_email_provider(app_settings)
    except EmailDeliveryError as exc:
        logger.warning(
            "[M-040][send_password_reset_email][PROVIDER_DISABLED] "
            f"to_email={mask_email_for_logs(to_email)} code={exc.code.value}"
        )
        raise

    reset_url = build_password_reset_url(reset_token, app_settings)
    template = build_password_reset_template(
        reset_url,
        language=language,
        app_name=app_settings.app_name,
        brand_base_url=app_settings.frontend_url,
    )

    logger.info(
        "[M-040][send_password_reset_email][BUILD_REQUEST] "
        f"to_email={mask_email_for_logs(to_email)} provider={app_settings.email_provider}"
    )

    try:
        receipt = await delivery_provider.send(
            EmailMessageRequest(
                to_email=to_email,
                subject=template.subject,
                html=template.html,
                text=template.text,
            )
        )
    except EmailDeliveryError as exc:
        marker = (
            "PROVIDER_DISABLED"
            if exc.code.value == "provider_disabled"
            else "MAP_PROVIDER_ERROR"
        )
        logger.warning(
            f"[M-040][send_password_reset_email][{marker}] "
            f"to_email={mask_email_for_logs(to_email)} code={exc.code.value}"
        )
        raise

    logger.info(
        "[M-040][send_password_reset_email][POST_PROVIDER] "
        f"to_email={mask_email_for_logs(to_email)} provider={receipt.provider} status={receipt.status}"
    )
    return receipt
# END_BLOCK_SEND_PASSWORD_RESET_EMAIL
