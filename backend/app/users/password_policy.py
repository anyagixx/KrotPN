"""
Password strength policy for KrotPN user accounts.

# FILE: backend/app/users/password_policy.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Enforce reusable password strength rules for registration, password change, and password reset flows
#   SCOPE: Deterministic password checks, safe rejection messages, and redacted policy telemetry
#   DEPENDS: M-002 (users), loguru
#   LINKS: M-002, M-062, V-M-062
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   password_strength_issues - Return safe human-readable weakness reasons without exposing the password
#   validate_password_strength - Raise ValueError when a password does not satisfy the policy
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-44 shared strong-password policy
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

import re

from loguru import logger


COMMON_PASSWORDS = {
    "password",
    "password1",
    "qwerty",
    "qwerty123",
    "12345678",
    "123456789",
    "letmein",
    "admin123",
    "krotpn",
}


# START_CONTRACT: password_strength_issues
#   PURPOSE: Return safe password weakness reasons
#   INPUTS: password: str - candidate password; email: str | None - optional account email; name: str | None - optional display name
#   OUTPUTS: list[str] - safe policy reasons suitable for API errors
#   SIDE_EFFECTS: none
#   LINKS: M-002, M-062, V-M-062
# END_CONTRACT: password_strength_issues
# START_BLOCK_PASSWORD_STRENGTH_ISSUES
def password_strength_issues(
    password: str,
    *,
    email: str | None = None,
    name: str | None = None,
) -> list[str]:
    """Return safe password policy issues without echoing the password."""
    issues: list[str] = []
    normalized = password or ""
    lowered = normalized.lower()

    if len(normalized) < 10:
        issues.append("минимум 10 символов")
    if len(normalized) > 100:
        issues.append("максимум 100 символов")
    if any(char.isspace() for char in normalized):
        issues.append("без пробелов")
    if not re.search(r"[a-zа-я]", normalized):
        issues.append("строчная буква")
    if not re.search(r"[A-ZА-Я]", normalized):
        issues.append("заглавная буква")
    if not re.search(r"\d", normalized):
        issues.append("цифра")
    if not re.search(r"[^A-Za-zА-Яа-я0-9]", normalized):
        issues.append("спецсимвол")
    if lowered in COMMON_PASSWORDS:
        issues.append("не входит в список популярных паролей")
    if re.search(r"(.)\1\1\1", normalized):
        issues.append("без длинных повторов одного символа")

    if email:
        local_part = email.split("@", 1)[0].lower()
        if len(local_part) >= 3 and local_part in lowered:
            issues.append("не содержит часть email")
    if name:
        name_part = re.sub(r"\s+", "", name).lower()
        if len(name_part) >= 3 and name_part in lowered:
            issues.append("не содержит имя")

    return issues
# END_BLOCK_PASSWORD_STRENGTH_ISSUES


# START_CONTRACT: validate_password_strength
#   PURPOSE: Enforce password strength policy and emit safe policy telemetry
#   INPUTS: password: str - candidate password; email: str | None; name: str | None
#   OUTPUTS: str - unchanged password when accepted
#   SIDE_EFFECTS: writes redacted policy log marker
#   LINKS: M-002, M-062, V-M-062
# END_CONTRACT: validate_password_strength
# START_BLOCK_VALIDATE_PASSWORD_STRENGTH
def validate_password_strength(
    password: str,
    *,
    email: str | None = None,
    name: str | None = None,
) -> str:
    """Validate password strength and return the unchanged password when accepted."""
    issues = password_strength_issues(password, email=email, name=name)
    if issues:
        logger.info(
            "[UsersService][validate_password_strength][POLICY_CHECK] "
            f"status=rejected issue_count={len(issues)}"
        )
        raise ValueError("Пароль слишком простой: " + ", ".join(issues))

    logger.info("[UsersService][validate_password_strength][POLICY_CHECK] status=accepted")
    return password
# END_BLOCK_VALIDATE_PASSWORD_STRENGTH
