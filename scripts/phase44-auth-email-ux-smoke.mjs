#!/usr/bin/env node
/*
 * FILE: scripts/phase44-auth-email-ux-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke verification for Phase-44 auth email UX and password recovery integration
 *   SCOPE: Checks frontend route/API/source markers, removed stale registration copy, backend log markers, and migration presence
 *   DEPENDS: M-009, M-040, M-062
 *   LINKS: V-M-062
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   main - Runs Phase-44 static assertions and exits non-zero on drift
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-44 auth/email UX smoke gate
 * END_CHANGE_SUMMARY
 */

import fs from 'node:fs'
import path from 'node:path'

const root = process.cwd()

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8')
}

function assertIncludes(text, expected, label) {
  if (!text.includes(expected)) {
    throw new Error(`${label}: expected to include ${expected}`)
  }
}

function assertNotIncludes(text, unexpected, label) {
  if (text.includes(unexpected)) {
    throw new Error(`${label}: must not include ${unexpected}`)
  }
}

// START_BLOCK_PHASE44_STATIC_ASSERTIONS
const register = read('frontend/src/pages/Register.tsx')
assertIncludes(register, 'папку «Спам»', 'Register pending state')
assertIncludes(register, 'Восстановить доступ', 'Duplicate email recovery CTA')
assertIncludes(register, 'passwordStrengthIssues', 'Register password policy')
assertNotIncludes(register, 'trial на 3 дня', 'Removed stale registration trial copy')
assertNotIncludes(register, 'hidden border-l border-white/5 p-8 lg:flex', 'Removed right-side registration panel')

const api = read('frontend/src/lib/api.ts')
assertIncludes(api, "requestPasswordReset", 'Frontend auth API')
assertIncludes(api, "confirmPasswordReset", 'Frontend auth API')

const app = read('frontend/src/App.tsx')
assertIncludes(app, 'path="/forgot-password"', 'Forgot password route')
assertIncludes(app, 'path="/reset-password"', 'Reset password route')

read('frontend/src/pages/ForgotPassword.tsx')
read('frontend/src/pages/ResetPassword.tsx')
read('frontend/src/lib/passwordPolicy.ts')

const templates = read('backend/app/email/templates.py')
assertIncludes(templates, '[EmailTemplates][build_verification_template][RENDER_BRANDED_VERIFICATION]', 'Verification template marker')
assertIncludes(templates, '[EmailTemplates][build_password_reset_template][RENDER_PASSWORD_RESET]', 'Password reset template marker')

const usersRouter = read('backend/app/users/router.py')
assertIncludes(usersRouter, '/password-reset/request', 'Password reset request endpoint')
assertIncludes(usersRouter, '/password-reset/confirm', 'Password reset confirm endpoint')
assertIncludes(usersRouter, '[UsersRouter][request_password_reset][CREATE_RESET_TOKEN]', 'Password reset request log marker')
assertIncludes(usersRouter, '[UsersRouter][reset_password][CONSUME_RESET_TOKEN]', 'Password reset confirm log marker')

const passwordPolicy = read('backend/app/users/password_policy.py')
assertIncludes(passwordPolicy, '[UsersService][validate_password_strength][POLICY_CHECK]', 'Backend password policy marker')

const verification = read('backend/app/email/verification.py')
assertIncludes(verification, '[VerifiedRegistration][register][DUPLICATE_EMAIL_RECOVERY]', 'Duplicate email recovery marker')

const migration = read('backend/alembic/versions/phase44_add_password_reset_tokens.py')
assertIncludes(migration, 'password_reset_tokens', 'Phase-44 migration')
// END_BLOCK_PHASE44_STATIC_ASSERTIONS

console.log('[phase44-auth-email-ux-smoke] ok')
