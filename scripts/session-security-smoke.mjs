// FILE: scripts/session-security-smoke.mjs
// VERSION: 1.0.0
// ROLE: SCRIPT
// MAP_MODE: LOCALS
// START_MODULE_CONTRACT
//   PURPOSE: Static Phase-25/Phase-28 session-security gate for auth storage, refresh, logout, cookies, and blacklist expectations.
//   SCOPE: Reads governed auth files and fails when required session and verified-registration guardrails drift.
//   DEPENDS: M-039, M-009, M-010, M-027, node:fs, node:path, node:url
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

  requireText('frontend/src/pages/Login.tsx', "localStorage.setItem('refresh_token'", 'user login stores refresh token for current rollback-compatible flow')
  requireAbsent('frontend/src/pages/Register.tsx', "localStorage.setItem('refresh_token'", 'pending register does not store refresh token before email verification')
  requireAbsent('frontend/src/pages/Register.tsx', "localStorage.setItem('access_token'", 'pending register does not store access token before email verification')
  requireText('frontend/src/pages/VerifyEmail.tsx', "localStorage.setItem('refresh_token'", 'verify-email stores refresh token after ownership proof')
  requireText('frontend/src/pages/VerifyEmail.tsx', "localStorage.setItem('access_token'", 'verify-email stores access token after ownership proof')
  requireText('frontend/src/stores/auth.ts', "localStorage.removeItem('refresh_token')", 'user logout clears refresh token')
  requireText('frontend/src/lib/api.ts', "localStorage.getItem('refresh_token')", 'user 401 retry uses refresh token')

  requireText('frontend-admin/src/pages/Login.tsx', "localStorage.setItem('admin_refresh_token'", 'admin login stores refresh token for 401 retry')
  requireText('frontend-admin/src/stores/auth.ts', "localStorage.removeItem('admin_refresh_token')", 'admin logout clears refresh token')
  requireText('frontend-admin/src/lib/api.ts', "localStorage.getItem('admin_refresh_token')", 'admin 401 retry uses refresh token')

  requireText('backend/app/core/security.py', 'verify_token_with_blacklist', 'token blacklist helper exists')
  requireText('backend/app/core/security.py', 'return False', 'token blacklist degrades open when Redis is unavailable')

  console.log('[SessionSecurity][auth][USER_SMOKE_PASS] static user session guard passed')
  console.log('[SessionSecurity][auth][ADMIN_SMOKE_PASS] static admin session guard passed')
}
// END_BLOCK_RUN

run()
