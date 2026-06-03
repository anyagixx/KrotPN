# FILE: backend/app/email/templates.py
# VERSION: 1.3.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Render verification and password reset email subject, HTML and text fallback content
#   SCOPE: Russian and English premium account-security email templates for KrotPN onboarding and password recovery
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
        eyebrow = "Secure registration"
        intro = "One action confirms that this mailbox belongs to you and prepares your KrotPN account."
        fallback = "If the button does not open, copy this secure link into your browser:"
        button = "Confirm email"
        note = "The link is one-time. Do not forward it to chats or support messages."
        support_hint = "Remote images are optional: the link below is enough to complete verification."
    else:
        subject = f"Подтвердите email для {app_name}"
        title = f"Подтверждение аккаунта {app_name}"
        eyebrow = "Защищенная регистрация"
        intro = "Один шаг подтверждает, что эта почта принадлежит вам, и подготавливает аккаунт KrotPN."
        fallback = "Если кнопка не открылась, скопируйте защищенную ссылку в браузер:"
        button = "Подтвердить email"
        note = "Ссылка одноразовая. Не пересылайте ее в чаты или сообщения поддержки."
        support_hint = "Удаленные изображения необязательны: ссылки ниже достаточно для подтверждения."

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
        eyebrow=eyebrow,
        title=title,
        intro=intro,
        button=button,
        action_url=verification_url,
        brand_logo_url=_build_brand_logo_url(brand_base_url),
        fallback=fallback,
        note=note,
        support_hint=support_hint,
    )
    text = _render_text_fallback(
        template_kind="verification",
        app_name=app_name,
        title=title,
        intro=intro,
        fallback=fallback,
        action_url=verification_url,
        note=note,
        support_hint=support_hint,
    )
    logger.info("[PremiumEmailTemplates][phase64][TOKEN_REDACTION_SAFE] template=verification")
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
        eyebrow = "Account recovery"
        intro = "Use this one-time route to create a new password for your KrotPN account."
        fallback = "If the button does not open, copy this secure link into your browser:"
        button = "Reset password"
        note = "If you did not request this email, ignore it and your password will stay unchanged."
        support_hint = "The recovery link works even when your mailbox blocks remote images."
    else:
        subject = f"Сброс пароля {app_name}"
        title = f"Сброс пароля {app_name}"
        eyebrow = "Восстановление доступа"
        intro = "Используйте одноразовый маршрут, чтобы задать новый пароль для аккаунта KrotPN."
        fallback = "Если кнопка не открылась, скопируйте защищенную ссылку в браузер:"
        button = "Сбросить пароль"
        note = "Если вы не запрашивали письмо, просто проигнорируйте его: пароль не изменится."
        support_hint = "Ссылка восстановления работает даже если почтовый клиент блокирует изображения."

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
        eyebrow=eyebrow,
        title=title,
        intro=intro,
        button=button,
        action_url=reset_url,
        brand_logo_url=_build_brand_logo_url(brand_base_url),
        fallback=fallback,
        note=note,
        support_hint=support_hint,
    )
    text = _render_text_fallback(
        template_kind="password_reset",
        app_name=app_name,
        title=title,
        intro=intro,
        fallback=fallback,
        action_url=reset_url,
        note=note,
        support_hint=support_hint,
    )
    logger.info("[PremiumEmailTemplates][phase64][TOKEN_REDACTION_SAFE] template=password_reset")
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
    intro: str,
    fallback: str,
    action_url: str,
    note: str,
    support_hint: str,
) -> str:
    """Render a plain text fallback with the required one-time action link only."""
    logger.info(
        "[PremiumEmailTemplates][phase64][TEXT_FALLBACK_SAFE] "
        f"template={template_kind}"
    )
    return (
        f"{app_name}\n"
        f"{title}\n\n"
        f"{intro}\n\n"
        f"{fallback}\n"
        f"{action_url}\n\n"
        f"{support_hint}\n\n"
        f"{note}\n"
    )


def _render_action_email(
    *,
    template_kind: str,
    language: str,
    app_name: str,
    eyebrow: str,
    title: str,
    intro: str,
    button: str,
    action_url: str,
    brand_logo_url: str,
    fallback: str,
    note: str,
    support_hint: str,
) -> str:
    """Render the shared premium action-email layout with email-client-safe markup."""
    safe_language = language if language in {"ru", "en"} else "ru"
    safe_url = escape(action_url, quote=True)
    safe_app_name = escape(app_name)
    safe_eyebrow = escape(eyebrow)
    safe_title = escape(title)
    safe_intro = escape(intro)
    safe_button = escape(button)
    safe_fallback = escape(fallback)
    safe_note = escape(note)
    safe_support_hint = escape(support_hint)
    safe_brand_logo_url = escape(brand_logo_url, quote=True)
    logo_markup = ""
    if safe_brand_logo_url:
        logo_markup = (
            f'<img src="{safe_brand_logo_url}" alt="{safe_app_name}" width="96" height="96" '
            'style="display:block;width:96px;height:96px;border:0;margin:0 auto 14px auto;" />'
        )
    logger.info(
        "[PremiumEmailTemplates][phase64][TEMPLATE_SHELL_READY] "
        f"template={template_kind} language={safe_language}"
    )
    logger.info("[PremiumEmailTemplates][phase64][BRAND_ASSET_BOUNDARY_SAFE] asset=public_email_logo")
    return f"""<!doctype html>
<html lang="{safe_language}">
  <body style="margin:0;background:#04090d;color:#eff8fb;font-family:Arial,Helvetica,sans-serif;line-height:1.5;">
    <div style="display:none;max-height:0;overflow:hidden;color:transparent;">{safe_title} - {safe_intro}</div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" data-phase64-template="premium-action" style="background:#04090d;padding:28px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:584px;background:#07141b;border:1px solid #1b3941;border-radius:12px;overflow:hidden;">
            <tr>
              <td style="height:4px;background:#5cf2c8;font-size:0;line-height:0;">&nbsp;</td>
            </tr>
            <tr>
              <td align="center" style="padding:28px 28px 14px 28px;">
                {logo_markup}
                <div style="font-size:12px;font-weight:700;letter-spacing:0;color:#5cf2c8;text-transform:uppercase;">KrotPN Matrix Access</div>
                <div style="margin:6px 0 0 0;font-size:13px;font-weight:700;letter-spacing:0;color:#89d8ff;">{safe_eyebrow}</div>
                <h1 style="margin:12px 0 0 0;font-size:25px;line-height:1.22;color:#ffffff;font-weight:800;">{safe_title}</h1>
                <p style="margin:13px auto 0 auto;max-width:440px;font-size:15px;color:#c6dbe2;">{safe_intro}</p>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:8px 28px 22px 28px;">
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
                      <p style="margin:14px 0 0 0;font-size:12px;color:#85a0a8;">{safe_support_hint}</p>
                    </td>
                  </tr>
                </table>
                <p style="margin:16px 0 0 0;font-size:12px;color:#8da6b0;">{safe_note}</p>
              </td>
            </tr>
            <tr>
              <td style="padding:0 28px 28px 28px;">
                <p style="margin:0;font-size:11px;color:#5f7680;">{safe_app_name} account security message. No password or payment data is requested in this email.</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
# END_BLOCK_EMAIL_LAYOUT
