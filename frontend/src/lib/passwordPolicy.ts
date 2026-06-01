// FILE: frontend/src/lib/passwordPolicy.ts
// VERSION: 1.0.0
// ROLE: RUNTIME
// MAP_MODE: EXPORTS
// START_MODULE_CONTRACT
//   PURPOSE: Shared frontend password-strength helper matching the Phase-44 backend policy
//   SCOPE: Deterministic client-side password hints for registration, password reset, and settings forms
//   DEPENDS: M-009 (frontend-user), M-062 (auth email UX and password security)
//   LINKS: M-009, M-062, V-M-062
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   passwordStrengthIssues - Returns safe localized weakness reasons
//   passwordPolicyHint - Compact Russian password policy hint
//   passwordPolicyExample - Format-only password example that satisfies the active policy
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.1.0 - Added Phase-46 format-only password example for registration UX
//   LAST_CHANGE: v1.0.0 - Added Phase-44 client-side strong-password helper
// END_CHANGE_SUMMARY

// START_BLOCK_PASSWORD_POLICY
const COMMON_PASSWORDS = new Set([
  'password',
  'password1',
  'qwerty',
  'qwerty123',
  '12345678',
  '123456789',
  'letmein',
  'admin123',
  'krotpn',
])

export const passwordPolicyHint = 'Минимум 10 символов: заглавная и строчная буква, цифра и спецсимвол.'
export const passwordPolicyExample = 'Krot-47!Primer'

export function passwordStrengthIssues(password: string): string[] {
  const issues: string[] = []
  const normalized = password || ''
  const lowered = normalized.toLowerCase()

  if (normalized.length < 10) issues.push('минимум 10 символов')
  if (normalized.length > 100) issues.push('максимум 100 символов')
  if (/\s/.test(normalized)) issues.push('без пробелов')
  if (!/[a-zа-я]/.test(normalized)) issues.push('строчная буква')
  if (!/[A-ZА-Я]/.test(normalized)) issues.push('заглавная буква')
  if (!/\d/.test(normalized)) issues.push('цифра')
  if (!/[^A-Za-zА-Яа-я0-9]/.test(normalized)) issues.push('спецсимвол')
  if (COMMON_PASSWORDS.has(lowered)) issues.push('не популярный пароль')
  if (/(.)\1\1\1/.test(normalized)) issues.push('без длинных повторов')

  return issues
}
// END_BLOCK_PASSWORD_POLICY
