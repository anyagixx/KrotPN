// FILE: scripts/session-security-smoke.mjs
// VERSION: 1.1.0
// ROLE: SCRIPT
// MAP_MODE: LOCALS
// START_MODULE_CONTRACT
//   PURPOSE: Static Phase-25/Phase-28/M-039 session-security gate for auth storage, refresh, logout, cookies, blacklist expectations, and 60-day user idle policy.
//   SCOPE: Reads governed auth/config/deploy files and fails when required session, verified-registration, and refresh lifetime guardrails drift.
//   DEPENDS: M-039, M-009, M-010, M-012, M-027, node:fs, node:path, node:url
//   LINKS: docs/modules/M-039.xml, docs/verification/V-M-039.xml
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   readProjectFile - Read a repository file as UTF-8 text
//   requireText - Assert that a file contains a required marker
//   requireAbsent - Assert that a file does not contain a forbidden marker
//   requireCountAtLeast - Assert that a marker appears at least N times
//   run - Execute the static smoke checks and print GRACE log markers
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: 2026-06-04 - Added 60-day idle TTL, stored-session resume, and clean-deploy refresh lifetime guards.
//   LAST_CHANGE: 2026-05-13 - Moved user register token-storage expectation to Phase-28 verify-email page
//   LAST_CHANGE: v1.0.0 - Phase-25 static session security smoke gate
// END_CHANGE_SUMMARY

import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = resolve(dirname(fileURLToPath(import.meta.url)), '..')

// START_BLOCK_IO
function readProjectFile(path) {
  return readFileSync(resolve(rootDir, path), 'utf8')
}
// END_BLOCK_IO

// START_BLOCK_ASSERTIONS
function requireText(file, marker, label) {
  const content = readProjectFile(file)
  if (!content.includes(marker)) {
    throw new Error(`${label}: expected ${file} to contain ${JSON.stringify(marker)}`)
  }
}

function requireAbsent(file, marker, label) {
  const content = readProjectFile(file)
  if (content.includes(marker)) {
    throw new Error(`${label}: expected ${file} not to contain ${JSON.stringify(marker)}`)
  }
}

function requireCountAtLeast(file, marker, minimum, label) {
  const content = readProjectFile(file)
  const count = content.split(marker).length - 1
  if (count < minimum) {
    throw new Error(`${label}: expected ${file} to contain ${JSON.stringify(marker)} at least ${minimum} times, found ${count}`)
  }
}
// END_BLOCK_ASSERTIONS

// START_BLOCK_RUN
function run() {
  requireText('backend/app/users/router.py', 'key="access_token"', 'access cookie is issued')
  requireText('backend/app/users/router.py', 'key="refresh_token"', 'refresh cookie is issued')
  requireCountAtLeast('backend/app/users/router.py', 'httponly=True', 2, 'auth cookies are httpOnly')
  requireCountAtLeast('backend/app/users/router.py', 'secure=True', 2, 'auth cookies are Secure')
  requireCountAtLeast('backend/app/users/router.py', 'samesite="strict"', 2, 'auth cookies use SameSite strict')

  requireText('frontend/src/lib/session.ts', 'USER_SESSION_IDLE_TIMEOUT_DAYS = 60', 'user session idle policy is 60 days')
  requireText('frontend/src/lib/session.ts', "'auth_last_seen_at'", 'user session records last seen timestamp')
  requireText('frontend/src/lib/session.ts', 'persistUserSessionTokens', 'user session helper stores tokens atomically')
  requireText('frontend/src/lib/session.ts', 'enforceUserSessionTtl', 'user session helper enforces idle TTL')
  requireText('frontend/src/lib/session.ts', 'clearUserSessionStorage', 'user session helper clears all browser auth keys')
  requireText('frontend/src/pages/Login.tsx', 'persistUserSessionTokens(data.access_token, data.refresh_token)', 'user login stores tokens through 60-day session helper')
  requireText('frontend/src/pages/Login.tsx', "navigate('/dashboard', { replace: true })", 'login route resumes existing stored session in a new tab')
  requireText('frontend/src/pages/Login.tsx', 'useAuthStore.getState().isAuthenticated', 'login route checks hydrated auth state before showing form')
  requireAbsent('frontend/src/pages/Register.tsx', "localStorage.setItem('refresh_token'", 'pending register does not store refresh token before email verification')
  requireAbsent('frontend/src/pages/Register.tsx', "localStorage.setItem('access_token'", 'pending register does not store access token before email verification')
  requireText('frontend/src/pages/VerifyEmail.tsx', 'persistUserSessionTokens(data.access_token, data.refresh_token)', 'verify-email stores tokens through session helper after ownership proof')
  requireText('frontend/src/stores/auth.ts', 'clearUserSessionStorage()', 'user logout clears session through helper')
  requireText('frontend/src/stores/auth.ts', 'merge:', 'persisted auth state is recomputed through session TTL merge')
  requireText('frontend/src/stores/auth.ts', 'touchUserSession()', 'user store refreshes last-seen timestamp')
  requireText('frontend/src/lib/api.ts', "localStorage.getItem('refresh_token')", 'user 401 retry uses refresh token')
  requireText('frontend/src/lib/api.ts', 'enforceUserSessionTtl()', 'user API enforces idle TTL before attaching auth token')
  requireText('frontend/src/lib/api.ts', 'persistUserSessionTokens(data.access_token, data.refresh_token)', 'user API refresh stores tokens through session helper')
  requireText('frontend/src/lib/api.ts', 'touchUserSession()', 'user API refreshes last-seen timestamp on authenticated traffic')

  requireText('frontend-admin/src/pages/Login.tsx', "localStorage.setItem('admin_refresh_token'", 'admin login stores refresh token for 401 retry')
  requireText('frontend-admin/src/stores/auth.ts', "localStorage.removeItem('admin_refresh_token')", 'admin logout clears refresh token')
  requireText('frontend-admin/src/lib/api.ts', "localStorage.getItem('admin_refresh_token')", 'admin 401 retry uses refresh token')

  requireText('backend/app/core/security.py', 'verify_token_with_blacklist', 'token blacklist helper exists')
  requireText('backend/app/core/security.py', 'return False', 'token blacklist degrades open when Redis is unavailable')
  requireText('backend/app/core/config.py', 'refresh_token_expire_days: int = 60', 'backend default refresh lifetime matches 60-day idle policy')
  requireText('.env.example', 'REFRESH_TOKEN_EXPIRE_DAYS=60', 'example env matches 60-day refresh policy')
  requireText('deploy/deploy-on-server.sh', 'REFRESH_TOKEN_EXPIRE_DAYS=60', 'clean server deploy writes 60-day refresh policy')
  requireText('deploy/deploy-all.sh', 'REFRESH_TOKEN_EXPIRE_DAYS=60', 'multi-server deploy writes 60-day refresh policy')

  console.log('[SessionSecurity][auth][USER_SMOKE_PASS] static user session guard passed')
  console.log('[SessionSecurity][auth][ADMIN_SMOKE_PASS] static admin session guard passed')
  console.log('[SessionSecurity][auth][SESSION_TTL_60_DAYS] static 60-day idle refresh guard passed')
}
// END_BLOCK_RUN

run()
