#!/usr/bin/env node
/*
 * FILE: scripts/phase56-premium-public-auth-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke verification for Phase-56 premium public site and auth routes
 *   SCOPE: Public route, dashboard route split, auth state preservation, visible logo, canonical tariff preview, redaction, reduced-motion, and protected deploy surfaces
 *   DEPENDS: M-073, M-009, M-068, M-069, M-070, M-071, M-072
 *   LINKS: V-M-073, docs/plans/Phase-56.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository files for static assertions
 *   assertContains - Fails if a file lacks a required marker
 *   assertNotContains - Fails if a file contains a prohibited marker
 *   assertRegexAbsent - Fails if a source matches a prohibited regular expression
 *   assertCanonicalTariffPreview - Compares public tariff preview values with backend M-068 catalog markers
 *   assertProtectedDeployDiffClean - Fails if protected deploy/install surfaces were touched
 *   main - Runs Phase-56 static assertions and prints required markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-56 premium public/auth static verification gate
 * END_CHANGE_SUMMARY
 */

import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const root = process.cwd()

function read(relativePath) {
  return readFileSync(join(root, relativePath), 'utf8')
}

function assertContains(source, needle, label) {
  if (!source.includes(needle)) {
    throw new Error(`${label} is missing required Phase-56 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-56 marker: ${needle}`)
  }
}

function assertRegexAbsent(source, regex, label) {
  if (regex.test(source)) {
    throw new Error(`${label} matches prohibited Phase-56 pattern: ${regex}`)
  }
}

function assertCanonicalTariffPreview(landing, catalog) {
  for (const [slug, price, limit] of [
    ['krotpn-1', '369', '1'],
    ['krotpn-6', '693', '6'],
    ['krotpn-9', '936', '9'],
  ]) {
    assertContains(catalog, `slug="${slug}"`, 'backend/app/billing/catalog.py')
    assertContains(catalog, `price=${price}.0`, 'backend/app/billing/catalog.py')
    assertContains(catalog, `device_limit=${limit}`, 'backend/app/billing/catalog.py')
    assertContains(landing, `slug: '${slug}'`, 'frontend/src/pages/Landing.tsx')
    assertContains(landing, `price: ${price}`, 'frontend/src/pages/Landing.tsx')
    assertContains(landing, `device_limit: ${limit}`, 'frontend/src/pages/Landing.tsx')
    assertContains(landing, `data-phase56-tariff-slug={plan.slug || ''}`, 'frontend/src/pages/Landing.tsx')
  }
}

function assertProtectedDeployDiffClean() {
  const protectedPaths = [
    'install.sh',
    'docker-compose.yml',
    'nginx',
    'deploy',
    'deploy/mtproto-de-compose.yml',
    '.env.example',
  ]
  for (const protectedPath of protectedPaths) {
    if (!existsSync(join(root, protectedPath))) {
      throw new Error(`Protected deploy surface missing from repository: ${protectedPath}`)
    }
  }

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (diff) {
    throw new Error(`Phase-56 must not change deploy/install surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE56_STATIC_ASSERTIONS
const app = read('frontend/src/App.tsx')
const landing = read('frontend/src/pages/Landing.tsx')
const login = read('frontend/src/pages/Login.tsx')
const register = read('frontend/src/pages/Register.tsx')
const forgot = read('frontend/src/pages/ForgotPassword.tsx')
const reset = read('frontend/src/pages/ResetPassword.tsx')
const verify = read('frontend/src/pages/VerifyEmail.tsx')
const layout = read('frontend/src/components/Layout.tsx')
const css = read('frontend/src/index.css')
const api = read('frontend/src/lib/api.ts')
const passwordPolicy = read('frontend/src/lib/passwordPolicy.ts')
const catalog = read('backend/app/billing/catalog.py')

for (const [label, source] of [
  ['frontend/src/App.tsx', app],
  ['frontend/src/pages/Landing.tsx', landing],
  ['frontend/src/pages/Login.tsx', login],
  ['frontend/src/pages/Register.tsx', register],
  ['frontend/src/pages/ForgotPassword.tsx', forgot],
  ['frontend/src/pages/ResetPassword.tsx', reset],
  ['frontend/src/pages/VerifyEmail.tsx', verify],
  ['frontend/src/components/Layout.tsx', layout],
  ['frontend/src/index.css', css],
]) {
  assertContains(source, 'START_MODULE_CONTRACT', label)
  assertContains(source, 'START_MODULE_MAP', label)
  assertContains(source, 'START_CHANGE_SUMMARY', label)
}

for (const needle of [
  "import Landing from './pages/Landing'",
  '<Route path="/" element={<Landing />} />',
  'path="/dashboard"',
  '<Route index element={<Dashboard />}',
  '<Route path="/config" element={<Navigate to="/dashboard/config" replace />} />',
  '<Route path="/subscription" element={<Navigate to="/dashboard/subscription" replace />} />',
]) {
  assertContains(app, needle, 'frontend/src/App.tsx')
}

for (const needle of [
  'data-phase56-public-route="landing"',
  'data-phase56-primary-cta="register"',
  'data-phase56-public-cta="register"',
  'data-phase56-email-proof-copy="true"',
  'data-phase56-tariff-preview="canonical-three-plans"',
  'PUBLIC_TARIFF_PREVIEW',
  'billingApi.getPlans()',
  '/brand/email-logo.png',
  'data-phase56-logo="true"',
  'MTProto proxy после подтверждения email',
  'только после подтверждения email',
  'Оплата создается backend по plan_id',
]) {
  assertContains(landing, needle, 'frontend/src/pages/Landing.tsx')
}

for (const prohibited of [
  'createPayment',
  'payment_url',
  "localStorage.setItem('access_token'",
  "localStorage.setItem('refresh_token'",
  'trial на 3',
  'Trial на 3',
  'rounded-2xl',
  'rounded-3xl',
  'text-5xl',
]) {
  assertNotContains(landing, prohibited, 'frontend/src/pages/Landing.tsx')
}

for (const [label, source] of [
  ['frontend/src/pages/Login.tsx', login],
  ['frontend/src/pages/Register.tsx', register],
  ['frontend/src/pages/ForgotPassword.tsx', forgot],
  ['frontend/src/pages/ResetPassword.tsx', reset],
  ['frontend/src/pages/VerifyEmail.tsx', verify],
]) {
  assertContains(source, '/brand/email-logo.png', label)
  assertContains(source, 'data-phase56-logo="true"', label)
}
for (const [label, source] of [
  ['frontend/src/pages/Login.tsx', login],
  ['frontend/src/pages/Register.tsx', register],
  ['frontend/src/pages/ForgotPassword.tsx', forgot],
  ['frontend/src/pages/ResetPassword.tsx', reset],
]) {
  assertContains(source, 'matrix-auth-brand-lockup', label)
}

assertContains(login, 'authApi.login', 'frontend/src/pages/Login.tsx')
assertContains(login, "localStorage.setItem('access_token'", 'frontend/src/pages/Login.tsx')
assertContains(login, "localStorage.setItem('refresh_token'", 'frontend/src/pages/Login.tsx')
assertContains(login, "navigate('/dashboard')", 'frontend/src/pages/Login.tsx')
assertContains(register, 'authApi.register', 'frontend/src/pages/Register.tsx')
assertContains(register, 'папку «Спам»', 'frontend/src/pages/Register.tsx')
assertContains(register, 'Восстановить доступ', 'frontend/src/pages/Register.tsx')
assertContains(register, 'passwordPolicyExample', 'frontend/src/pages/Register.tsx')
assertContains(register, 'passwordStrengthIssues', 'frontend/src/pages/Register.tsx')
assertContains(forgot, 'authApi.requestPasswordReset', 'frontend/src/pages/ForgotPassword.tsx')
assertContains(reset, 'authApi.confirmPasswordReset', 'frontend/src/pages/ResetPassword.tsx')
assertContains(reset, 'passwordStrengthIssues', 'frontend/src/pages/ResetPassword.tsx')
assertContains(verify, 'authApi.verifyEmail', 'frontend/src/pages/VerifyEmail.tsx')
assertContains(verify, "navigate('/dashboard')", 'frontend/src/pages/VerifyEmail.tsx')
assertContains(api, "requestPasswordReset", 'frontend/src/lib/api.ts')
assertContains(api, "confirmPasswordReset", 'frontend/src/lib/api.ts')
assertContains(passwordPolicy, 'passwordPolicyExample', 'frontend/src/lib/passwordPolicy.ts')

for (const route of ['/dashboard', '/dashboard/config', '/dashboard/subscription', '/dashboard/referrals', '/dashboard/settings']) {
  assertContains(layout, `to: '${route}'`, 'frontend/src/components/Layout.tsx')
}

for (const needle of [
  '.matrix-public-page',
  '.matrix-public-nav',
  '.matrix-public-brand',
  '.matrix-public-hero',
  '.matrix-public-band',
  '.matrix-public-tariffs',
  '.matrix-public-tariff',
  '.matrix-brand-logo',
  '.matrix-auth-brand-lockup',
  '@media (prefers-reduced-motion: reduce)',
  'pointer-events: none',
]) {
  assertContains(css, needle, 'frontend/src/index.css')
}

assertRegexAbsent(css, /letter-spacing:\s*-[^;]+;/, 'frontend/src/index.css')
assertRegexAbsent(css, /font-size:\s*[^;]*vw[^;]*;/, 'frontend/src/index.css')
assertNotContains(css, 'radial-gradient(', 'frontend/src/index.css')
assertNotContains(css, 'rounded-[32px]', 'frontend/src/index.css')
assertNotContains(css, 'rounded-[24px]', 'frontend/src/index.css')

assertCanonicalTariffPreview(landing, catalog)
assertProtectedDeployDiffClean()
// END_BLOCK_PHASE56_STATIC_ASSERTIONS

console.log('[PremiumPublicSite][phase56][ROUTES_READY] ok')
console.log('[PremiumPublicSite][phase56][PUBLIC_CTA_VISIBLE] ok')
console.log('[PremiumPublicSite][phase56][AUTH_STATES_READABLE] ok')
console.log('[PremiumPublicSite][phase56][EMAIL_PROOF_GUARD] ok')
console.log('[PremiumPublicSite][phase56][TARIFFS_CANONICAL] ok')
console.log('[PremiumPublicSite][phase56][LOGO_VISIBLE] ok')
console.log('[PremiumPublicSite][phase56][REDUCED_MOTION_SAFE] ok')
console.log('[PremiumPublicSite][phase56][SCREENSHOT_MATRIX_REVIEWED] static-route-and-style-ready')
console.log('[PremiumPublicSite][phase56][PROTECTED_SURFACE_GUARD] ok')
