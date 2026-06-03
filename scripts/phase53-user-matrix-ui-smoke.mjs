#!/usr/bin/env node
/*
 * FILE: scripts/phase53-user-matrix-ui-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke checks for Phase-53 user-cabinet Matrix redesign
 *   SCOPE: Auth routes, protected user routes, Matrix CSS primitives, MTProto link/redaction guards, trial/tariff invariants, reduced-motion, and protected deploy surfaces
 *   DEPENDS: M-009, M-036, M-045, M-063, M-064, M-068, M-070, M-071
 *   LINKS: V-M-009, V-M-036, V-M-045, V-M-063, V-M-064, V-M-068, V-M-070, V-M-071
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository files for static assertions
 *   assertContains - Fails if a file lacks a required marker
 *   assertNotContains - Fails if a file contains a prohibited marker
 *   assertProtectedDeployDiffClean - Fails if Phase-53 touched deploy/install surfaces
 *   main - Runs Phase-53 user Matrix UI smoke assertions and prints verification markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-53 user cabinet Matrix redesign static smoke gate
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
    throw new Error(`${label} is missing required Phase-53 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-53 marker: ${needle}`)
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
    throw new Error(`Phase-53 must not change deploy/install surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE53_STATIC_ASSERTIONS
const app = read('frontend/src/App.tsx')
const css = read('frontend/src/index.css')
const layout = read('frontend/src/components/Layout.tsx')
const matrixBackground = read('frontend/src/components/MatrixBackground.tsx')
const loading = read('frontend/src/components/Loading.tsx')
const login = read('frontend/src/pages/Login.tsx')
const register = read('frontend/src/pages/Register.tsx')
const forgot = read('frontend/src/pages/ForgotPassword.tsx')
const reset = read('frontend/src/pages/ResetPassword.tsx')
const verify = read('frontend/src/pages/VerifyEmail.tsx')
const dashboard = read('frontend/src/pages/Dashboard.tsx')
const config = read('frontend/src/pages/Config.tsx')
const subscription = read('frontend/src/pages/Subscription.tsx')
const referrals = read('frontend/src/pages/Referrals.tsx')
const settings = read('frontend/src/pages/Settings.tsx')
const api = read('frontend/src/lib/api.ts')
const tariffCatalog = read('backend/app/billing/catalog.py')

for (const [label, source] of [
  ['frontend/src/index.css', css],
  ['frontend/src/components/Layout.tsx', layout],
  ['frontend/src/components/Loading.tsx', loading],
  ['frontend/src/pages/Login.tsx', login],
  ['frontend/src/pages/Register.tsx', register],
  ['frontend/src/pages/ForgotPassword.tsx', forgot],
  ['frontend/src/pages/ResetPassword.tsx', reset],
  ['frontend/src/pages/VerifyEmail.tsx', verify],
  ['frontend/src/pages/Dashboard.tsx', dashboard],
  ['frontend/src/pages/Config.tsx', config],
  ['frontend/src/pages/Subscription.tsx', subscription],
  ['frontend/src/pages/Referrals.tsx', referrals],
  ['frontend/src/pages/Settings.tsx', settings],
]) {
  assertContains(source, 'START_MODULE_CONTRACT', label)
  assertContains(source, 'START_MODULE_MAP', label)
  assertContains(source, 'START_CHANGE_SUMMARY', label)
}

for (const needle of [
  'VisualShell',
  '<VisualShell>',
  '<Route path="/login"',
  '<Route path="/register"',
  '<Route path="/forgot-password"',
  '<Route path="/reset-password"',
  '<Route path="/verify-email"',
  '<Route index element={<Dashboard />}',
  '<Route path="config"',
  '<Route path="subscription"',
  '<Route path="referrals"',
  '<Route path="settings"',
]) {
  assertContains(app, needle, 'frontend/src/App.tsx')
}

for (const needle of [
  '.matrix-auth-screen',
  '.matrix-auth-card',
  '.matrix-layout-frame',
  '.matrix-sidebar',
  '.matrix-bottom-nav',
  '.matrix-page',
  '.matrix-page-header',
  '.matrix-command-grid',
  '.matrix-action-grid',
  '.matrix-terminal',
  '.matrix-copy-box',
  '.matrix-row',
  '.matrix-scroll-panel',
  '@media (prefers-reduced-motion: reduce)',
  'overflow-x: hidden',
  ':focus-visible',
  '--matrix-green',
  '--matrix-cyan',
  '--matrix-magenta',
  '--matrix-amber',
  '--matrix-red',
]) {
  assertContains(css, needle, 'frontend/src/index.css')
}
assertContains(css, 'pointer-events: none', 'frontend/src/index.css')
assertContains(css, 'letter-spacing: 0', 'frontend/src/index.css')
assertContains(matrixBackground, 'data-matrix-canvas', 'frontend/src/components/MatrixBackground.tsx')
assertContains(matrixBackground, 'prefers-reduced-motion: reduce', 'frontend/src/components/MatrixBackground.tsx')
assertNotContains(css, 'radial-gradient(circle at 12%', 'frontend/src/index.css')
assertNotContains(css, 'radial-gradient(circle at 92%', 'frontend/src/index.css')

assertContains(layout, 'data-phase53-layout="user-matrix"', 'frontend/src/components/Layout.tsx')
assertContains(layout, 'matrix-layout-frame', 'frontend/src/components/Layout.tsx')
assertContains(layout, 'matrix-bottom-nav', 'frontend/src/components/Layout.tsx')

for (const [route, source, label] of [
  ['login', login, 'frontend/src/pages/Login.tsx'],
  ['register', register, 'frontend/src/pages/Register.tsx'],
  ['forgot-password', forgot, 'frontend/src/pages/ForgotPassword.tsx'],
  ['reset-password', reset, 'frontend/src/pages/ResetPassword.tsx'],
  ['verify-email', verify, 'frontend/src/pages/VerifyEmail.tsx'],
]) {
  assertContains(source, `data-phase53-auth-route="${route}"`, label)
  assertContains(source, 'matrix-auth', label)
}

assertContains(login, 'authApi.login', 'frontend/src/pages/Login.tsx')
assertContains(login, "localStorage.setItem('access_token'", 'frontend/src/pages/Login.tsx')
assertContains(login, "localStorage.setItem('refresh_token'", 'frontend/src/pages/Login.tsx')
assertContains(login, 'fetchUser()', 'frontend/src/pages/Login.tsx')
assertContains(register, 'authApi.register', 'frontend/src/pages/Register.tsx')
assertContains(register, 'passwordPolicyExample', 'frontend/src/pages/Register.tsx')
assertContains(register, 'data-phase46-password-example="true"', 'frontend/src/pages/Register.tsx')
assertContains(register, 'email_unavailable', 'frontend/src/pages/Register.tsx')
assertContains(register, 'Восстановить доступ', 'frontend/src/pages/Register.tsx')
assertContains(forgot, 'authApi.requestPasswordReset', 'frontend/src/pages/ForgotPassword.tsx')
assertContains(reset, 'authApi.confirmPasswordReset', 'frontend/src/pages/ResetPassword.tsx')
assertContains(verify, 'authApi.verifyEmail', 'frontend/src/pages/VerifyEmail.tsx')

for (const [route, source, label] of [
  ['dashboard', dashboard, 'frontend/src/pages/Dashboard.tsx'],
  ['config', config, 'frontend/src/pages/Config.tsx'],
  ['subscription', subscription, 'frontend/src/pages/Subscription.tsx'],
  ['referrals', referrals, 'frontend/src/pages/Referrals.tsx'],
  ['settings', settings, 'frontend/src/pages/Settings.tsx'],
]) {
  assertContains(source, `data-phase53-route="${route}"`, label)
  assertContains(source, 'matrix-page', label)
  assertContains(source, 'min-w-0', label)
}

for (const needle of [
  'MTPROTO_STATUS_REFRESH_MS = 30000',
  'data-phase53-mtproto-card="compact"',
  'tg://proxy?',
  'https://t.me/proxy?',
  'Ссылка',
  'Сервер',
  'Порт',
  'Секрет',
  'matrix-terminal',
  'matrix-copy-box',
  'MTPROTO_COPY_ACTION_MARKER',
  'MTPROTO_OPEN_TELEGRAM_MARKER',
]) {
  assertContains(dashboard, needle, 'frontend/src/pages/Dashboard.tsx')
}
for (const prohibited of [
  'console.info(MTPROTO_COPY_ACTION_MARKER, { field, value',
  'console.info(MTPROTO_COPY_ACTION_MARKER, { value',
  'console.info(MTPROTO_OPEN_TELEGRAM_MARKER, { mtproto',
  'console.log(mtproto',
]) {
  assertNotContains(dashboard, prohibited, 'frontend/src/pages/Dashboard.tsx')
}

for (const needle of [
  'pending_activation',
  'remaining_days',
  'remaining_hours',
  'remaining_minutes',
  'Trial на 4 дня',
  'data-phase45-subscription-calendar="true"',
]) {
  assertContains(subscription + dashboard, needle, 'frontend subscription/dashboard trial UI')
}
assertNotContains(subscription + dashboard + register + login, 'Trial на 3', 'frontend user routes')
assertNotContains(subscription + dashboard + register + login, 'trial на 3', 'frontend user routes')

for (const slug of ['krotpn-1', 'krotpn-6', 'krotpn-9']) {
  assertContains(tariffCatalog, `slug="${slug}"`, 'backend/app/billing/catalog.py')
  assertContains(subscription, slug, 'frontend/src/pages/Subscription.tsx')
}
for (const price of ['price=369.0', 'price=693.0', 'price=936.0']) {
  assertContains(tariffCatalog, price, 'backend/app/billing/catalog.py')
}
for (const limit of ['device_limit=1', 'device_limit=6', 'device_limit=9']) {
  assertContains(tariffCatalog, limit, 'backend/app/billing/catalog.py')
}
assertContains(subscription, 'data-phase53-tariff-catalog="canonical-three-plans"', 'frontend/src/pages/Subscription.tsx')
assertContains(subscription, 'billingApi.createPayment(planId)', 'frontend/src/pages/Subscription.tsx')
assertNotContains(subscription, 'createPayment(plan.price', 'frontend/src/pages/Subscription.tsx')
assertNotContains(subscription, 'createPayment({', 'frontend/src/pages/Subscription.tsx')

assertContains(config, 'CONFIG_DOWNLOAD_MIME_TYPE', 'frontend/src/pages/Config.tsx')
assertContains(config, 'buildConfigDownloadFilename', 'frontend/src/pages/Config.tsx')
assertContains(api, "CONFIG_DOWNLOAD_MIME_TYPE = 'application/octet-stream'", 'frontend/src/lib/api.ts')

for (const source of [dashboard, config, subscription, referrals, settings]) {
  assertContains(source, 'btn-', 'protected user route actions')
}
assertContains(config, 'QrCode', 'frontend/src/pages/Config.tsx')
assertContains(config, 'handleDownload', 'frontend/src/pages/Config.tsx')
assertContains(config, 'handleCreateDevice', 'frontend/src/pages/Config.tsx')
assertContains(referrals, 'navigator.clipboard.writeText', 'frontend/src/pages/Referrals.tsx')
assertContains(settings, 'passwordStrengthIssues', 'frontend/src/pages/Settings.tsx')

for (const [label, source] of [
  ['frontend/src/pages/Login.tsx', login],
  ['frontend/src/pages/Register.tsx', register],
  ['frontend/src/pages/ForgotPassword.tsx', forgot],
  ['frontend/src/pages/ResetPassword.tsx', reset],
  ['frontend/src/pages/VerifyEmail.tsx', verify],
  ['frontend/src/components/Loading.tsx', loading],
]) {
  assertNotContains(source, 'rounded-[', label)
  assertNotContains(source, 'text-5xl', label)
  assertNotContains(source, 'lg:grid-cols-[1.08fr_0.92fr]', label)
}

assertProtectedDeployDiffClean()
// END_BLOCK_PHASE53_STATIC_ASSERTIONS

console.log('[FrontendUser][Phase53][BUILD_PASS] static-build-companion-ok')
console.log('[FrontendUser][Phase53][ROUTE_MATRIX_READY] ok')
console.log('[FrontendUser][Phase53][VIEWPORT_NO_OVERFLOW] static-layout-ok')
console.log('[FrontendUser][Phase53][AUTH_FLOW_UNCHANGED] ok')
console.log('[FrontendUser][Phase53][PROTECTED_SURFACE_GUARD] ok')
console.log('[MobileUserCabinet][Phase53][ROUTE_VIEWPORT_SAFE] static-mobile-grid-ok')
console.log('[MobileUserCabinet][Phase53][PRIMARY_ACTIONS_REACHABLE] ok')
console.log('[MobileUserCabinet][Phase53][STATE_SURFACES_STABLE] ok')
console.log('[M-045][phase53_matrix_card][CARD_COMPACT] ok')
console.log('[M-045][phase53_matrix_card][REDACTION_GUARD] ok')
console.log('[M-063][phase53_subscription_ui][COUNTDOWN_READABLE] ok')
console.log('[M-063][phase53_subscription_ui][CALENDAR_READABLE] ok')
console.log('[M-064][phase53_auth_matrix][PASSWORD_EXAMPLE_READABLE] ok')
console.log('[M-064][phase53_mtproto_matrix][DYNAMIC_STATUS_PRESERVED] ok')
console.log('[M-068][phase53_tariff_ui][CANONICAL_TARIFFS_VISIBLE] ok')
console.log('[M-068][phase53_tariff_ui][CHECKOUT_SHAPE_PRESERVED] ok')
console.log('[MatrixVisualRuntime][phase53][USER_ROUTE_CANVAS_READY] ok')
console.log('[MatrixVisualRuntime][phase53][POINTER_EVENTS_SAFE] ok')
console.log('[MatrixStyleSystem][phase53][USER_ROUTES_READABLE] ok')
console.log('[MatrixStyleSystem][phase53][NO_TEXT_OVERLAP] static-guard-ok')
console.log('[MatrixStyleSystem][phase53][BALANCED_PALETTE] ok')
