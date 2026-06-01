# FILE: backend/app/email/__init__.py
# VERSION: 1.1.0
# ROLE: BARREL
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: Email module public exports for verified registration and password recovery foundation
#   SCOPE: Re-export provider, template and delivery service entry points
#   DEPENDS: M-040
#   LINKS: V-M-040
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   EmailDeliveryError, EmailDeliveryErrorCode, EmailDeliveryReceipt, EmailMessageRequest - provider types
#   build_verification_template, build_password_reset_template - account email template renderers
#   build_verification_url, build_password_reset_url, mask_email_for_logs, send_verification_email, send_password_reset_email - delivery service functions
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.1.0 - Exported Phase-44 password reset email helpers
#   LAST_CHANGE: v1.0.0 - Added Phase-27 email module exports
# END_CHANGE_SUMMARY

from app.email.provider import (
    EmailDeliveryError,
    EmailDeliveryErrorCode,
    EmailDeliveryReceipt,
    EmailMessageRequest,
)
from app.email.service import (
    build_password_reset_url,
    build_verification_url,
    mask_email_for_logs,
    send_password_reset_email,
    send_verification_email,
)
from app.email.templates import build_password_reset_template, build_verification_template

__all__ = [
    "EmailDeliveryError",
    "EmailDeliveryErrorCode",
    "EmailDeliveryReceipt",
    "EmailMessageRequest",
    "build_password_reset_template",
    "build_password_reset_url",
    "build_verification_template",
    "build_verification_url",
    "mask_email_for_logs",
    "send_password_reset_email",
    "send_verification_email",
]
