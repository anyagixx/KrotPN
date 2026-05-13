# FILE: backend/app/email/templates.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Render verification email subject, HTML and text fallback content
#   SCOPE: Russian and English verification email templates for KrotPN registration
#   DEPENDS: M-040
#   LINKS: V-M-040
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   VerificationEmailTemplate - Rendered subject/html/text content
#   build_verification_template - Render localized KrotPN verification email content
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-27 verification email templates
# END_CHANGE_SUMMARY

from dataclasses import dataclass


# START_BLOCK_TEMPLATE_TYPES
@dataclass(frozen=True)
class VerificationEmailTemplate:
    """Rendered verification email payload."""

    subject: str
    html: str
    text: str
# END_BLOCK_TEMPLATE_TYPES


# START_CONTRACT: build_verification_template
#   PURPOSE: Render a localized verification email without logging or mutating state
#   INPUTS: verification_url: str - one-time verification URL; language: str - ru/en locale; app_name: str - product name
#   OUTPUTS: VerificationEmailTemplate
#   SIDE_EFFECTS: none
#   LINKS: M-040, V-M-040
# END_CONTRACT: build_verification_template
# START_BLOCK_BUILD_TEMPLATE
def build_verification_template(
    verification_url: str,
    *,
    language: str = "ru",
    app_name: str = "KrotPN",
) -> VerificationEmailTemplate:
    """Build the verification email content."""
    normalized_language = language.lower().split("-")[0]
    if normalized_language == "en":
        subject = f"Confirm your {app_name} email"
        title = f"Confirm your {app_name} account"
        intro = "Open this link to confirm that this email belongs to you."
        fallback = "If the button does not work, copy this link into your browser:"
        button = "Confirm email"
    else:
        subject = f"Подтвердите email для {app_name}"
        title = f"Подтверждение аккаунта {app_name}"
        intro = "Откройте ссылку, чтобы подтвердить, что эта почта принадлежит вам."
        fallback = "Если кнопка не работает, скопируйте эту ссылку в браузер:"
        button = "Подтвердить email"

    html = f"""<!doctype html>
<html lang="{normalized_language if normalized_language in {"ru", "en"} else "ru"}">
  <body style="font-family: Arial, sans-serif; color: #111827; line-height: 1.5;">
    <h1>{title}</h1>
    <p>{intro}</p>
    <p>
      <a href="{verification_url}" style="display: inline-block; padding: 10px 14px; background: #111827; color: #ffffff; text-decoration: none; border-radius: 6px;">
        {button}
      </a>
    </p>
    <p>{fallback}</p>
    <p>{verification_url}</p>
  </body>
</html>"""
    text = f"{title}\n\n{intro}\n\n{verification_url}\n"
    return VerificationEmailTemplate(subject=subject, html=html, text=text)
# END_BLOCK_BUILD_TEMPLATE
