# FILE: backend/app/email/templates.py
# VERSION: 1.2.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Render verification and password reset email subject, HTML and text fallback content
#   SCOPE: Russian and English account-security email templates for KrotPN onboarding and password recovery
#   DEPENDS: M-040, M-069
#   LINKS: V-M-040, V-M-062, V-M-069
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
#   PURPOSE: Render a localized branded verification email without logging tokens or mutating state
#   INPUTS: verification_url: str - one-time verification URL; language: str - ru/en locale; app_name: str - product name; brand_base_url: str - public frontend URL for email logo assets
#   OUTPUTS: VerificationEmailTemplate
#   SIDE_EFFECTS: none
#   LINKS: M-040, M-062, M-069, V-M-040, V-M-062, V-M-069
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
        intro = "Open this secure link to confirm that this email belongs to you."
        fallback = "If the button does not work, copy this link into your browser:"
        button = "Confirm email"
        note = "We will never ask you for this link in chat or support messages."
    else:
        subject = f"Подтвердите email для {app_name}"
        title = f"Подтверждение аккаунта {app_name}"
        intro = "Откройте защищённую ссылку, чтобы подтвердить, что эта почта принадлежит вам."
        fallback = "Если кнопка не работает, скопируйте эту ссылку в браузер:"
        button = "Подтвердить email"
        note = "Мы никогда не просим эту ссылку в чатах или сообщениях поддержки."

    logger.info(
        "[EmailTemplates][build_verification_template][RENDER_BRANDED_VERIFICATION] "
        f"language={normalized_language}"
    )
    html = _render_action_email(
        language=normalized_language,
        app_name=app_name,
        title=title,
        intro=intro,
        button=button,
        action_url=verification_url,
        brand_logo_url=_build_brand_logo_url(brand_base_url),
        fallback=fallback,
        note=note,
    )
    text = f"{title}\n\n{intro}\n\n{fallback}\n{verification_url}\n\n{note}\n"
    return VerificationEmailTemplate(subject=subject, html=html, text=text)
# END_BLOCK_BUILD_TEMPLATE


# START_CONTRACT: build_password_reset_template
#   PURPOSE: Render a localized password reset email without logging tokens or mutating state
#   INPUTS: reset_url: str - one-time reset URL; language: str - ru/en locale; app_name: str - product name; brand_base_url: str - public frontend URL for email logo assets
#   OUTPUTS: PasswordResetEmailTemplate
#   SIDE_EFFECTS: safe template-render log marker
#   LINKS: M-040, M-062, M-069, V-M-062, V-M-069
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
        intro = "Use this one-time link to set a new password for your account."
        fallback = "If the button does not work, copy this link into your browser:"
        button = "Reset password"
        note = "If you did not request this email, ignore it and your password will stay unchanged."
    else:
        subject = f"Сброс пароля {app_name}"
        title = f"Сброс пароля {app_name}"
        intro = "Используйте одноразовую ссылку, чтобы задать новый пароль для аккаунта."
        fallback = "Если кнопка не работает, скопируйте эту ссылку в браузер:"
        button = "Сбросить пароль"
        note = "Если вы не запрашивали письмо, просто проигнорируйте его: пароль не изменится."

    logger.info(
        "[EmailTemplates][build_password_reset_template][RENDER_PASSWORD_RESET] "
        f"language={normalized_language}"
    )
    html = _render_action_email(
        language=normalized_language,
        app_name=app_name,
        title=title,
        intro=intro,
        button=button,
        action_url=reset_url,
        brand_logo_url=_build_brand_logo_url(brand_base_url),
        fallback=fallback,
        note=note,
    )
    text = f"{title}\n\n{intro}\n\n{fallback}\n{reset_url}\n\n{note}\n"
    return PasswordResetEmailTemplate(subject=subject, html=html, text=text)
# END_BLOCK_BUILD_PASSWORD_RESET_TEMPLATE


# START_BLOCK_EMAIL_LAYOUT
def _build_brand_logo_url(brand_base_url: str | None) -> str:
    """Build the public email logo URL from the configured frontend origin."""
    normalized_base_url = (brand_base_url or "").strip().rstrip("/")
    if not normalized_base_url:
        return ""
    return f"{normalized_base_url}/brand/email-logo.png"


def _render_action_email(
    *,
    language: str,
    app_name: str,
    title: str,
    intro: str,
    button: str,
    action_url: str,
    brand_logo_url: str,
    fallback: str,
    note: str,
) -> str:
    """Render the shared branded action-email layout."""
    safe_language = language if language in {"ru", "en"} else "ru"
    safe_url = escape(action_url, quote=True)
    safe_app_name = escape(app_name)
    safe_title = escape(title)
    safe_intro = escape(intro)
    safe_button = escape(button)
    safe_fallback = escape(fallback)
    safe_note = escape(note)
    safe_brand_logo_url = escape(brand_logo_url, quote=True)
    logo_markup = ""
    if safe_brand_logo_url:
        logo_markup = (
            f'<img src="{safe_brand_logo_url}" alt="{safe_app_name}" width="96" height="96" '
            'style="display:block;width:96px;height:96px;border:0;margin:0 0 14px 0;" />'
        )
    return f"""<!doctype html>
<html lang="{safe_language}">
  <body style="margin:0;background:#061117;color:#eff8fb;font-family:Arial,Helvetica,sans-serif;line-height:1.5;">
    <div style="display:none;max-height:0;overflow:hidden;color:transparent;">{safe_title}</div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#061117;padding:24px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#0d222c;border:1px solid rgba(157,203,216,0.22);border-radius:12px;overflow:hidden;">
            <tr>
              <td style="padding:26px 28px 16px 28px;">
                {logo_markup}
                <div style="font-size:13px;font-weight:700;letter-spacing:0;color:#75c7ff;">{safe_app_name}</div>
                <h1 style="margin:12px 0 0 0;font-size:26px;line-height:1.2;color:#ffffff;">{safe_title}</h1>
                <p style="margin:14px 0 0 0;font-size:15px;color:#b7cbd3;">{safe_intro}</p>
              </td>
            </tr>
            <tr>
              <td style="padding:8px 28px 20px 28px;">
                <a href="{safe_url}" style="display:inline-block;background:#5cd5b6;color:#061117;text-decoration:none;font-weight:800;padding:12px 16px;border-radius:8px;">{safe_button}</a>
              </td>
            </tr>
            <tr>
              <td style="padding:0 28px 24px 28px;">
                <p style="margin:0 0 8px 0;font-size:13px;color:#8da6b0;">{safe_fallback}</p>
                <p style="margin:0;word-break:break-all;font-size:13px;color:#d6f6ff;">{safe_url}</p>
                <p style="margin:18px 0 0 0;font-size:12px;color:#8da6b0;">{safe_note}</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
# END_BLOCK_EMAIL_LAYOUT
