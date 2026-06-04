#!/usr/bin/env node
// FILE: scripts/phase28-register-flow-smoke.mjs
// VERSION: 1.1.0
// ROLE: SCRIPT
// MAP_MODE: LOCALS
// START_MODULE_CONTRACT
//   PURPOSE: Static smoke gate for Phase-28 frontend verified-registration flow
//   SCOPE: Assert register does not store tokens, verify-email route exists, session-helper token persistence is used after ownership proof, and pending/success/expired/resend anchors are present
//   DEPENDS: M-009, M-039 frontend files, Node.js fs/path
//   LINKS: V-M-009
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   read - Load repo file as UTF-8
//   assertContains/assertNotContains - Minimal static assertions
//   BLOCK_PHASE28_REGISTER_FLOW_SMOKE - Smoke assertions for API, Register, VerifyEmail and App route files
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: 2026-06-04 - Updated verified-email token expectation to the 60-day session helper contract.
//   LAST_CHANGE: 2026-05-13 - Added Phase-28 register flow static smoke gate
// END_CHANGE_SUMMARY

import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = process.cwd()

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8')
}

function assertContains(content, needle, file) {
  if (!content.includes(needle)) {
    throw new Error(`${file} is missing ${needle}`)
  }
}

function assertNotContains(content, needle, file) {
  if (content.includes(needle)) {
    throw new Error(`${file} must not contain ${needle}`)
  }
}

// START_BLOCK_PHASE28_REGISTER_FLOW_SMOKE
const api = read('frontend/src/lib/api.ts')
const register = read('frontend/src/pages/Register.tsx')
const verifyEmail = read('frontend/src/pages/VerifyEmail.tsx')
const app = read('frontend/src/App.tsx')

assertContains(api, 'PendingRegistrationResponse', 'frontend/src/lib/api.ts')
assertContains(api, "api.post<PendingRegistrationResponse>('/auth/register'", 'frontend/src/lib/api.ts')
assertContains(api, "api.post<TokenResponse>('/auth/verify-email'", 'frontend/src/lib/api.ts')

assertNotContains(register, "localStorage.setItem('access_token'", 'frontend/src/pages/Register.tsx')
assertNotContains(register, "localStorage.setItem('refresh_token'", 'frontend/src/pages/Register.tsx')
assertContains(register, 'REGISTER_PENDING_STATE', 'frontend/src/pages/Register.tsx')
assertContains(register, 'REGISTER_RESEND_AVAILABLE', 'frontend/src/pages/Register.tsx')

assertContains(verifyEmail, 'REGISTER_VERIFIED_SUCCESS', 'frontend/src/pages/VerifyEmail.tsx')
assertContains(verifyEmail, 'REGISTER_EXPIRED_LINK', 'frontend/src/pages/VerifyEmail.tsx')
assertContains(verifyEmail, 'persistUserSessionTokens(data.access_token, data.refresh_token)', 'frontend/src/pages/VerifyEmail.tsx')

assertContains(app, 'path="/verify-email"', 'frontend/src/App.tsx')
// END_BLOCK_PHASE28_REGISTER_FLOW_SMOKE

console.log('Phase-28 register flow smoke passed')
