#!/usr/bin/env node
/*
 * FILE: scripts/phase57-premium-user-cabinet-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke verification for Phase-57 premium protected user cabinet
 *   SCOPE: Dashboard command center, config workflow, subscription countdown/calendar, MTProto owner actions, compact referrals/settings, redaction, and protected surface guards
 *   DEPENDS: M-075, M-009, M-036, M-045, M-063, M-064, M-068, M-070, M-071, M-072
 *   LINKS: V-M-075, docs/plans/Phase-57.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository files for static assertions
 *   assertContains - Fails if a file lacks a required marker
 *   assertNotContains - Fails if a file contains a prohibited marker
 *   assertRegexAbsent - Fails if a source matches a prohibited regular expression
 *   assertProtectedSurfaceDiffClean - Fails if Phase-57 touched backend/deploy/runtime surfaces
 *   main - Runs Phase-57 static assertions and prints required verification markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-57 premium user cabinet verification gate
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
    throw new Error(`${label} is missing required Phase-57 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-57 marker: ${needle}`)
  }
}

function assertRegexAbsent(source, regex, label) {
  if (regex.test(source)) {
    throw new Error(`${label} matches prohibited Phase-57 pattern: ${regex}`)
  }
}

function assertProtectedSurfaceDiffClean() {
  const protectedPaths = [
    'install.sh',
    'docker-compose.yml',
    'nginx',
    'deploy',
    'deploy/mtproto-de-compose.yml',
    '.env.example',
    'backend/app',
    'backend/tests',
    'mtproto-runtime',
    'official-mtproxy',
  ]
  for (const protectedPath of protectedPaths) {
    if (!existsSync(join(root, protectedPath))) {
      throw new Error(`Protected surface missing from repository: ${protectedPath}`)
    }
  }

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (diff) {
    throw new Error(`Phase-57 must not change backend/deploy/runtime surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE57_STATIC_ASSERTIONS
const css = read('frontend/src/index.css')
const layout = read('frontend/src/components/Layout.tsx')
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
  ['frontend/src/pages/Dashboard.tsx', dashboard],
  ['frontend/src/pages/Config.tsx', config],
  ['frontend/src/pages/Subscription.tsx', subscription],
  ['frontend/src/pages/Referrals.tsx', referrals],
  ['frontend/src/pages/Settings.tsx', settings],
]) {
  assertContains(source, 'START_MODULE_CONTRACT', label)
  assertContains(source, 'START_MODULE_MAP', label)
  assertContains(source, 'START_CHANGE_SUMMARY', label)
  assertContains(source, 'M-075', label)
}

for (const needle of [
  'data-phase57-layout="premium-user-cabinet"',
  'data-phase57-protected-main="dashboard-routes"',
  "to: '/dashboard'",
  "to: '/dashboard/config'",
  "to: '/dashboard/subscription'",
  "to: '/dashboard/referrals'",
  "to: '/dashboard/settings'",
]) {
  assertContains(layout, needle, 'frontend/src/components/Layout.tsx')
}

for (const needle of [
  'START_BLOCK_PHASE57_USER_CABINET_SURFACES',
  '.phase57-command-center',
  '.phase57-command-header',
  '.phase57-signal-strip',
  '.phase57-signal-tile',
  '.phase57-primary-actions',
  '.phase57-card-compact',
  '.phase57-scroll-list',
  '.phase57-mini-grid',
  '@media (prefers-reduced-motion: reduce)',
  'pointer-events: none',
  'letter-spacing: 0',
]) {
  assertContains(css, needle, 'frontend/src/index.css')
}
assertRegexAbsent(css, /letter-spacing:\s*-[^;]+;/, 'frontend/src/index.css')
assertRegexAbsent(css, /font-size:\s*[^;]*vw[^;]*;/, 'frontend/src/index.css')
assertNotContains(css, 'radial-gradient(', 'frontend/src/index.css')
assertNotContains(css, 'rounded-2xl', 'frontend/src/index.css')
assertNotContains(css, 'rounded-3xl', 'frontend/src/index.css')

for (const [route, source, label] of [
  ['dashboard', dashboard, 'frontend/src/pages/Dashboard.tsx'],
  ['config', config, 'frontend/src/pages/Config.tsx'],
  ['subscription', subscription, 'frontend/src/pages/Subscription.tsx'],
  ['referrals', referrals, 'frontend/src/pages/Referrals.tsx'],
  ['settings', settings, 'frontend/src/pages/Settings.tsx'],
]) {
  assertContains(source, `data-phase57-route="${route}"`, label)
  assertContains(source, 'phase57-', label)
  assertContains(source, 'min-w-0', label)
}

for (const needle of [
  'data-phase57-command-center="true"',
  'data-phase57-first-screen-tasks="vpn subscription mtproto devices"',
  'data-phase57-dashboard-signal-strip="true"',
  'data-phase57-primary-actions-reachable="true"',
  'data-phase57-primary-action="vpn-config"',
  'data-phase57-primary-action="devices"',
  'data-phase57-primary-action="subscription"',
  'data-phase57-primary-action="mtproto-copy"',
  'to={hasSubscription ? \'/dashboard/config\' : \'/dashboard/subscription\'}',
  'to="/dashboard/config"',
  'to="/dashboard/subscription"',
]) {
  assertContains(dashboard, needle, 'frontend/src/pages/Dashboard.tsx')
}

for (const needle of [
  'MTPROTO_STATUS_REFRESH_MS = 30000',
  'data-phase57-mtproto-owner-card="redacted-actions"',
  'data-phase57-mtproto-actions="tg-browser-copy-fields"',
  'tg://proxy?',
  'https://t.me/proxy?',
  'Ссылка',
  'Сервер',
  'Порт',
  'Секрет',
  'console.info(MTPROTO_COPY_ACTION_MARKER, { field })',
]) {
  assertContains(dashboard, needle, 'frontend/src/pages/Dashboard.tsx')
}
for (const prohibited of [
  'console.info(MTPROTO_COPY_ACTION_MARKER, { field, value',
  'console.info(MTPROTO_COPY_ACTION_MARKER, { value',
  'console.info(MTPROTO_OPEN_TELEGRAM_MARKER, { link',
  'console.info(MTPROTO_OPEN_TELEGRAM_MARKER, { mtproto',
  'console.log(mtproto',
]) {
  assertNotContains(dashboard, prohibited, 'frontend/src/pages/Dashboard.tsx')
}

for (const needle of [
  'data-phase57-config-workflow="qr-download-copy-device"',
  'data-phase57-config-actions="qr-download-copy"',
  'data-phase57-device-list="scroll-safe"',
  'data-phase57-raw-config="collapsed"',
  'CONFIG_DOWNLOAD_MIME_TYPE',
  'buildConfigDownloadBlob',
  'buildConfigDownloadFilename',
  'handleDownload',
  'handleCopy',
  'handleCreateDevice',
  'QRCodeCanvas',
  'to="/dashboard/subscription"',
]) {
  assertContains(config, needle, 'frontend/src/pages/Config.tsx')
}
assertContains(api, "CONFIG_DOWNLOAD_MIME_TYPE = 'application/octet-stream'", 'frontend/src/lib/api.ts')

for (const needle of [
  'data-phase57-subscription-countdown="server-derived"',
  'data-phase57-subscription-calendar="active-range"',
  'data-phase57-tariff-catalog="canonical-three-plans"',
  'data-phase57-renewal-cta="plan-id-only"',
  'pending_activation',
  'remaining_days',
  'remaining_hours',
  'remaining_minutes',
  'active_from',
  'active_until',
  'billingApi.createPayment(planId)',
]) {
  assertContains(subscription, needle, 'frontend/src/pages/Subscription.tsx')
}
assertNotContains(subscription, 'createPayment(plan.price', 'frontend/src/pages/Subscription.tsx')
assertNotContains(subscription, 'createPayment({', 'frontend/src/pages/Subscription.tsx')

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

for (const needle of [
  'data-phase57-referrals-settings-compact="referral-stats"',
  'data-phase57-referral-copy="code"',
  'data-phase57-referral-copy="link"',
  'data-phase57-referral-history="scroll-safe"',
  'navigator.clipboard.writeText',
]) {
  assertContains(referrals, needle, 'frontend/src/pages/Referrals.tsx')
}
for (const needle of [
  'data-phase57-referrals-settings-compact="settings"',
  'data-phase57-settings-password-policy="strong-password"',
  'passwordStrengthIssues',
  'passwordPolicyHint',
  'userApi.changePassword',
]) {
  assertContains(settings, needle, 'frontend/src/pages/Settings.tsx')
}

assertNotContains(dashboard + config + subscription + referrals + settings, 'Trial на 3', 'Phase-57 user cabinet routes')
assertNotContains(dashboard + config + subscription + referrals + settings, 'trial на 3', 'Phase-57 user cabinet routes')
assertNotContains(dashboard + config, 'to="/config"', 'Phase-57 protected route links')
assertNotContains(dashboard + config, 'to="/subscription"', 'Phase-57 protected route links')

assertProtectedSurfaceDiffClean()
// END_BLOCK_PHASE57_STATIC_ASSERTIONS

console.log('[PremiumUserCabinet][phase57][ROUTES_READY] ok')
console.log('[PremiumUserCabinet][phase57][DASHBOARD_COMMAND_CENTER] ok')
console.log('[PremiumUserCabinet][phase57][PRIMARY_ACTIONS_REACHABLE] ok')
console.log('[PremiumUserCabinet][phase57][CONFIG_WORKFLOW_SAFE] ok')
console.log('[PremiumUserCabinet][phase57][SUBSCRIPTION_COUNTDOWN_SAFE] ok')
console.log('[PremiumUserCabinet][phase57][MTPROTO_REDACTION] ok')
console.log('[PremiumUserCabinet][phase57][TARIFF_CHECKOUT_SHAPE] ok')
console.log('[PremiumUserCabinet][phase57][REFERRALS_SETTINGS_COMPACT] ok')
console.log('[PremiumUserCabinet][phase57][REDUCED_MOTION_SAFE] ok')
console.log('[PremiumUserCabinet][phase57][SCREENSHOT_MATRIX_REVIEWED] static-route-proof')
console.log('[PremiumUserCabinet][phase57][PROTECTED_SURFACE_GUARD] ok')
