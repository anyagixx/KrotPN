# FILE: backend/app/email/templates.py
# VERSION: 1.4.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Render verification and password reset email subject, minimal HTML and text fallback content
#   SCOPE: Russian and English premium minimal account-security email templates for KrotPN onboarding and password recovery
#   DEPENDS: M-040, M-062, M-069, M-079
#   LINKS: V-M-040, V-M-062, V-M-069, V-M-079
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   VerificationEmailTemplate - Rendered subject/html/text content
#   build_verification_template - Render localized KrotPN verification email content
#   PasswordResetEmailTemplate - Rendered password reset subject/html/text content
#   build_password_reset_template - Render localized KrotPN password reset email content
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.4.0 - Added Phase-66 minimal Resend shell, larger logo, copy removal, and transparent outer background
#   LAST_CHANGE: v1.3.0 - Added Phase-64 premium Matrix-safe email shell, text fallback guard, and redacted markers
#   LAST_CHANGE: v1.2.0 - Added Phase-51 public brand logo rendering for Resend HTML email templates
#   LAST_CHANGE: v1.1.0 - Added Phase-44 branded verification and password reset templates
#   LAST_CHANGE: v1.0.0 - Added Phase-27 verification email templates
# END_CHANGE_SUMMARY

from dataclasses import dataclass
from html import escape

from loguru import logger


# START_BLOCK_TEMPLATE_TYPES
@dataclass(frozen=True)
class VerificationEmailTemplate:
    """Rendered verification email payload."""

    subject: str
    html: str
    text: str


@dataclass(frozen=True)
class PasswordResetEmailTemplate:
    """Rendered password reset email payload."""

    subject: str
    html: str
    text: str
# END_BLOCK_TEMPLATE_TYPES


# START_CONTRACT: build_verification_template
#   PURPOSE: Render a localized premium verification email without logging tokens or mutating state
#   INPUTS: verification_url: str - one-time verification URL; language: str - ru/en locale; app_name: str - product name; brand_base_url: str - public frontend URL for email logo assets
#   OUTPUTS: VerificationEmailTemplate
#   SIDE_EFFECTS: safe template-render log markers
#   LINKS: M-040, M-062, M-069, M-079, V-M-040, V-M-062, V-M-069, V-M-079
# END_CONTRACT: build_verification_template
# START_BLOCK_BUILD_TEMPLATE
def build_verification_template(
    verification_url: str,
    *,
    language: str = "ru",
    app_name: str = "KrotPN",
    brand_base_url: str = "https://krotpn.xyz",
) -> VerificationEmailTemplate:
    """Build the verification email content."""
    normalized_language = language.lower().split("-")[0]
    if normalized_language == "en":
        subject = f"Confirm your {app_name} email"
        title = f"Confirm your {app_name} account"
        fallback = "If the button does not open, copy this secure link into your browser:"
        button = "Confirm email"
        note = "The link works once."
    else:
        subject = f"Подтвердите email для {app_name}"
        title = f"Подтверждение аккаунта {app_name}"
        fallback = "Если кнопка не открылась, скопируйте защищенную ссылку в браузер:"
        button = "Подтвердить email"
        note = "Ссылка действует один раз."

    logger.info(
        "[EmailTemplates][build_verification_template][RENDER_BRANDED_VERIFICATION] "
        f"language={normalized_language}"
    )
    logger.info(
        "[PremiumEmailTemplates][phase64][VERIFICATION_EMAIL_SAFE] "
        f"language={normalized_language}"
    )
    html = _render_action_email(
        template_kind="verification",
        language=normalized_language,
        app_name=app_name,
        title=title,
        button=button,
        action_url=verification_url,
        brand_logo_url=_build_brand_logo_url(brand_base_url),
        fallback=fallback,
        note=note,
    )
    text = _render_text_fallback(
        template_kind="verification",
        app_name=app_name,
        title=title,
        fallback=fallback,
        action_url=verification_url,
        note=note,
    )
    logger.info("[PremiumEmailTemplates][phase64][TOKEN_REDACTION_SAFE] template=verification")
    logger.info("[PremiumEmailTemplates][phase66][NEGATIVE_COPY_SAFE] template=verification")
    logger.info("[PremiumEmailTemplates][phase66][ACTION_FALLBACK_SAFE] template=verification")
    return VerificationEmailTemplate(subject=subject, html=html, text=text)
# END_BLOCK_BUILD_TEMPLATE


# START_CONTRACT: build_password_reset_template
#   PURPOSE: Render a localized premium password reset email without logging tokens or mutating state
#   INPUTS: reset_url: str - one-time reset URL; language: str - ru/en locale; app_name: str - product name; brand_base_url: str - public frontend URL for email logo assets
#   OUTPUTS: PasswordResetEmailTemplate
#   SIDE_EFFECTS: safe template-render log marker
#   LINKS: M-040, M-062, M-069, M-079, V-M-062, V-M-069, V-M-079
# END_CONTRACT: build_password_reset_template
# START_BLOCK_BUILD_PASSWORD_RESET_TEMPLATE
def build_password_reset_template(
    reset_url: str,
    *,
    language: str = "ru",
    app_name: str = "KrotPN",
    brand_base_url: str = "https://krotpn.xyz",
) -> PasswordResetEmailTemplate:
    """Build the password reset email content."""
    normalized_language = language.lower().split("-")[0]
    if normalized_language == "en":
        subject = f"Reset your {app_name} password"
        title = f"Reset your {app_name} password"
        fallback = "If the button does not open, copy this secure link into your browser:"
        button = "Reset password"
        note = "If you did not request this email, ignore it and your password will stay unchanged."
    else:
        subject = f"Сброс пароля {app_name}"
        title = f"Сброс пароля {app_name}"
        fallback = "Если кнопка не открылась, скопируйте защищенную ссылку в браузер:"
        button = "Сбросить пароль"
        note = "Если вы не запрашивали письмо, просто проигнорируйте его: пароль не изменится."

    logger.info(
        "[EmailTemplates][build_password_reset_template][RENDER_PASSWORD_RESET] "
        f"language={normalized_language}"
    )
    logger.info(
        "[PremiumEmailTemplates][phase64][RESET_EMAIL_SAFE] "
        f"language={normalized_language}"
    )
    html = _render_action_email(
        template_kind="password_reset",
        language=normalized_language,
        app_name=app_name,
        title=title,
        button=button,
        action_url=reset_url,
        brand_logo_url=_build_brand_logo_url(brand_base_url),
        fallback=fallback,
        note=note,
    )
    text = _render_text_fallback(
        template_kind="password_reset",
        app_name=app_name,
        title=title,
        fallback=fallback,
        action_url=reset_url,
        note=note,
    )
    logger.info("[PremiumEmailTemplates][phase64][TOKEN_REDACTION_SAFE] template=password_reset")
    logger.info("[PremiumEmailTemplates][phase66][NEGATIVE_COPY_SAFE] template=password_reset")
    logger.info("[PremiumEmailTemplates][phase66][ACTION_FALLBACK_SAFE] template=password_reset")
    return PasswordResetEmailTemplate(subject=subject, html=html, text=text)
# END_BLOCK_BUILD_PASSWORD_RESET_TEMPLATE


# START_BLOCK_EMAIL_LAYOUT
def _build_brand_logo_url(brand_base_url: str | None) -> str:
    """Build the public email logo URL from the configured frontend origin."""
    normalized_base_url = (brand_base_url or "").strip().rstrip("/")
    if not normalized_base_url:
        return ""
    return f"{normalized_base_url}/brand/email-logo.png"


def _render_text_fallback(
    *,
    template_kind: str,
    app_name: str,
    title: str,
    fallback: str,
    action_url: str,
    note: str,
) -> str:
    """Render a plain text fallback with the required one-time action link only."""
    logger.info(
        "[PremiumEmailTemplates][phase64][TEXT_FALLBACK_SAFE] "
        f"template={template_kind}"
    )
    return (
        f"{app_name}\n"
        f"{title}\n\n"
        f"{fallback}\n"
        f"{action_url}\n\n"
        f"{note}\n"
    )


def _render_action_email(
    *,
    template_kind: str,
    language: str,
    app_name: str,
    title: str,
    button: str,
    action_url: str,
    brand_logo_url: str,
    fallback: str,
    note: str,
) -> str:
    """Render the shared premium action-email layout with email-client-safe markup."""
    safe_language = language if language in {"ru", "en"} else "ru"
    safe_url = escape(action_url, quote=True)
    safe_app_name = escape(app_name)
    safe_title = escape(title)
    safe_button = escape(button)
    safe_fallback = escape(fallback)
    safe_note = escape(note)
    safe_brand_logo_url = escape(brand_logo_url, quote=True)
    logo_markup = ""
    if safe_brand_logo_url:
        logo_markup = (
            f'<img src="{safe_brand_logo_url}" alt="{safe_app_name}" width="128" height="128" '
            'style="display:block;width:128px;height:128px;border:0;margin:0 auto 16px auto;" />'
        )
    logger.info(
        "[PremiumEmailTemplates][phase64][TEMPLATE_SHELL_READY] "
        f"template={template_kind} language={safe_language}"
    )
    logger.info("[PremiumEmailTemplates][phase64][BRAND_ASSET_BOUNDARY_SAFE] asset=public_email_logo")
    logger.info(
        "[PremiumEmailTemplates][phase66][MINIMAL_STYLE_SAFE] "
        f"template={template_kind} logo=128 outer_background=transparent"
    )
    return f"""<!doctype html>
<html lang="{safe_language}">
  <body style="margin:0;color:#eff8fb;font-family:Arial,Helvetica,sans-serif;line-height:1.5;">
    <div style="display:none;max-height:0;overflow:hidden;color:transparent;">{safe_title}</div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" data-phase64-template="premium-action" data-phase66-template="minimal-action" style="padding:28px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:584px;background:#07141b;border:1px solid #1b3941;border-radius:12px;overflow:hidden;">
            <tr>
              <td align="center" style="padding:30px 28px 16px 28px;">
                {logo_markup}
                <h1 style="margin:0;font-size:25px;line-height:1.22;color:#ffffff;font-weight:800;">{safe_title}</h1>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:6px 28px 24px 28px;">
                <a href="{safe_url}" style="display:inline-block;background:#5cf2c8;color:#041014;text-decoration:none;font-weight:800;padding:12px 18px;border-radius:8px;">{safe_button}</a>
              </td>
            </tr>
            <tr>
              <td style="padding:0 28px 24px 28px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#0b1b22;border:1px solid #18343d;border-radius:10px;">
                  <tr>
                    <td style="padding:16px 16px 14px 16px;">
                      <p style="margin:0 0 8px 0;font-size:13px;color:#9fb7be;">{safe_fallback}</p>
                      <p style="margin:0;word-break:break-all;font-size:13px;color:#d7fbff;">{safe_url}</p>
                    </td>
                  </tr>
                </table>
                <p style="margin:16px 0 0 0;font-size:12px;color:#8da6b0;">{safe_note}</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
# END_BLOCK_EMAIL_LAYOUT
