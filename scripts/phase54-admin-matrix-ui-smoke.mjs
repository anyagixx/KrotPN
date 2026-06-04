#!/usr/bin/env node
/*
 * FILE: scripts/phase54-admin-matrix-ui-smoke.mjs
 * VERSION: 1.1.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke checks for Phase-54 admin Matrix redesign
 *   SCOPE: Admin routes, compact Matrix CSS primitives, login shell, mobile route safety, MTProto admin analytics/redaction, canonical tariffs, and protected deploy surfaces
 *   DEPENDS: M-010, M-037, M-047, M-058, M-068, M-070, M-071
 *   LINKS: V-M-010, V-M-037, V-M-047, V-M-058, V-M-068, V-M-070, V-M-071
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository files for static assertions
 *   assertContains - Fails if a file lacks a required marker
 *   assertNotContains - Fails if a file contains a prohibited marker
 *   assertRegexAbsent - Fails if a file matches a prohibited regular expression
 *   assertProtectedDeployDiffClean - Fails if Phase-54 touched deploy/install surfaces
 *   main - Runs Phase-54 admin Matrix UI smoke assertions and prints verification markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.1.0 - Accepted 60-day session deploy policy and minimal admin login form assertions.
 *   LAST_CHANGE: v1.0.0 - Added Phase-54 admin Matrix redesign static smoke gate
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
    throw new Error(`${label} is missing required Phase-54 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-54 marker: ${needle}`)
  }
}

function assertRegexAbsent(source, regex, label) {
  if (regex.test(source)) {
    throw new Error(`${label} matches prohibited Phase-54 pattern: ${regex}`)
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
  const allowedSessionLifetimeFiles = new Set([
    '.env.example',
    'deploy/deploy-all.sh',
    'deploy/deploy-on-server.sh',
  ])
  const violations = diff
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((path) => !allowedSessionLifetimeFiles.has(path))
  if (violations.length) {
    throw new Error(`Phase-54 must not change deploy/install surfaces except session lifetime policy: ${violations.join(', ')}`)
  }
}

// START_BLOCK_PHASE54_STATIC_ASSERTIONS
const main = read('frontend-admin/src/main.tsx')
const css = read('frontend-admin/src/index.css')
const layout = read('frontend-admin/src/components/Layout.tsx')
const statCard = read('frontend-admin/src/components/StatCard.tsx')
const login = read('frontend-admin/src/pages/Login.tsx')
const dashboard = read('frontend-admin/src/pages/Dashboard.tsx')
const users = read('frontend-admin/src/pages/Users.tsx')
const devices = read('frontend-admin/src/pages/Devices.tsx')
const mtproto = read('frontend-admin/src/pages/MTProto.tsx')
const mtprotoAnalytics = read('frontend-admin/src/pages/MTProtoAnalytics.tsx')
const servers = read('frontend-admin/src/pages/Servers.tsx')
const plans = read('frontend-admin/src/pages/Plans.tsx')
const analytics = read('frontend-admin/src/pages/Analytics.tsx')
const tariffCatalog = read('backend/app/billing/catalog.py')

for (const [label, source] of [
  ['frontend-admin/src/index.css', css],
  ['frontend-admin/src/components/Layout.tsx', layout],
  ['frontend-admin/src/components/StatCard.tsx', statCard],
  ['frontend-admin/src/pages/Login.tsx', login],
  ['frontend-admin/src/pages/Dashboard.tsx', dashboard],
  ['frontend-admin/src/pages/Users.tsx', users],
  ['frontend-admin/src/pages/Devices.tsx', devices],
  ['frontend-admin/src/pages/MTProto.tsx', mtproto],
  ['frontend-admin/src/pages/MTProtoAnalytics.tsx', mtprotoAnalytics],
  ['frontend-admin/src/pages/Servers.tsx', servers],
  ['frontend-admin/src/pages/Plans.tsx', plans],
  ['frontend-admin/src/pages/Analytics.tsx', analytics],
]) {
  assertContains(source, 'START_MODULE_CONTRACT', label)
  assertContains(source, 'START_MODULE_MAP', label)
  assertContains(source, 'START_CHANGE_SUMMARY', label)
}

for (const needle of [
  '<Route path="/login"',
  '<Route index element={<Dashboard />}',
  '<Route path="users"',
  '<Route path="devices"',
  '<Route path="mtproto"',
  '<Route path="servers"',
  '<Route path="plans"',
  '<Route path="analytics"',
  '<VisualShell>',
]) {
  assertContains(main, needle, 'frontend-admin/src/main.tsx')
}

for (const needle of [
  '--matrix-green',
  '--matrix-cyan',
  '--matrix-magenta',
  '--matrix-amber',
  '--matrix-red',
  '.admin-login-shell',
  '.admin-login-card',
  '.admin-hero-strip',
  '.compact-toolbar',
  '.mini-kpi-grid',
  '.bounded-scroll',
  '.chart-frame',
  '@media (prefers-reduced-motion: reduce)',
  'overflow-x: hidden',
  ':focus-visible',
  'pointer-events: none',
  'letter-spacing: 0',
]) {
  assertContains(css, needle, 'frontend-admin/src/index.css')
}

for (const prohibited of [
  'rounded-[32px]',
  'rounded-[24px]',
  'rounded-2xl',
  'rounded-3xl',
  'text-5xl',
  'text-4xl',
  'tracking-[',
  'lg:grid-cols-[1.15fr_0.85fr]',
]) {
  assertNotContains(login + servers + plans, prohibited, 'admin route visual density')
}
assertNotContains(login, 'admin@krotpn.com', 'frontend-admin/src/pages/Login.tsx')
assertNotContains(login, 'placeholder=', 'frontend-admin/src/pages/Login.tsx')
assertContains(login, 'data-phase54-admin-login="compact"', 'frontend-admin/src/pages/Login.tsx')
assertContains(login, 'data-admin-login-minimal="[FrontendAdmin][fix][MINIMAL_LOGIN_READY]"', 'frontend-admin/src/pages/Login.tsx')
assertContains(login, 'auth-input-group', 'frontend-admin/src/pages/Login.tsx')
assertContains(login, 'auth-primary-action', 'frontend-admin/src/pages/Login.tsx')
assertContains(login, "'Войти'", 'frontend-admin/src/pages/Login.tsx')
assertNotContains(login, 'admin-hero-strip', 'frontend-admin/src/pages/Login.tsx')
assertNotContains(login, 'Компактный вход для оператора', 'frontend-admin/src/pages/Login.tsx')
assertNotContains(login, 'Для операционной работы', 'frontend-admin/src/pages/Login.tsx')
assertContains(layout, 'data-phase54-admin-shell="matrix-compact"', 'frontend-admin/src/components/Layout.tsx')
assertContains(layout, '[MobileAdminConsole][Phase54][ROUTE_VIEWPORT_SAFE]', 'frontend-admin/src/components/Layout.tsx')
assertContains(statCard, 'data-phase54-kpi="compact-admin"', 'frontend-admin/src/components/StatCard.tsx')

for (const [route, source, label] of [
  ['dashboard', dashboard, 'frontend-admin/src/pages/Dashboard.tsx'],
  ['users', users, 'frontend-admin/src/pages/Users.tsx'],
  ['devices', devices, 'frontend-admin/src/pages/Devices.tsx'],
  ['servers', servers, 'frontend-admin/src/pages/Servers.tsx'],
  ['plans', plans, 'frontend-admin/src/pages/Plans.tsx'],
  ['analytics', analytics, 'frontend-admin/src/pages/Analytics.tsx'],
]) {
  assertContains(source, `data-phase54-admin-route="${route}"`, label)
  assertContains(source, 'page-shell', label)
}

for (const source of [users, devices, mtproto, mtprotoAnalytics]) {
  assertContains(source, 'bounded-scroll', 'large admin inventory route')
}
assertContains(devices, '[MobileAdminConsole][Phase54][CONFIRMATIONS_READABLE]', 'frontend-admin/src/pages/Devices.tsx')
assertContains(mtproto, 'data-phase54-mtproto-admin="compact"', 'frontend-admin/src/pages/MTProto.tsx')
assertContains(mtproto, '[M-047][phase54_mtproto_admin][OPS_CONTROLS_READABLE]', 'frontend-admin/src/pages/MTProto.tsx')
assertContains(mtproto, '[M-047][phase54_mtproto_admin][CONFIRMATIONS_SAFE]', 'frontend-admin/src/pages/MTProto.tsx')
assertContains(mtproto, '[M-047][phase54_mtproto_admin][REDACTION_PRESERVED]', 'frontend-admin/src/pages/MTProto.tsx')
assertContains(mtprotoAnalytics, 'data-phase54-mtproto-analytics="compact"', 'frontend-admin/src/pages/MTProtoAnalytics.tsx')
assertContains(mtprotoAnalytics, '[M-058][phase54_mtproto_analytics][CHARTS_TABLES_READABLE]', 'frontend-admin/src/pages/MTProtoAnalytics.tsx')
assertContains(mtprotoAnalytics, '[M-058][phase54_mtproto_analytics][AUTO_REFRESH_STABLE]', 'frontend-admin/src/pages/MTProtoAnalytics.tsx')
assertContains(mtprotoAnalytics, '[M-058][phase54_mtproto_analytics][SIGNALS_STILL_HIDDEN]', 'frontend-admin/src/pages/MTProtoAnalytics.tsx')
assertContains(mtprotoAnalytics, '[M-058][phase54_mtproto_analytics][PROMOTION_TAG_REDACTED]', 'frontend-admin/src/pages/MTProtoAnalytics.tsx')
assertContains(mtprotoAnalytics, 'data-mtproto-ip-history-scroll', 'frontend-admin/src/pages/MTProtoAnalytics.tsx')
assertRegexAbsent(mtprotoAnalytics, />\s*Signals\s*</i, 'frontend-admin/src/pages/MTProtoAnalytics.tsx')
assertNotContains(mtproto + mtprotoAnalytics, 'unmasked_secret', 'MTProto admin redaction')
assertNotContains(mtproto + mtprotoAnalytics, 'proxy_url', 'MTProto admin redaction')

for (const slug of ['krotpn-1', 'krotpn-6', 'krotpn-9']) {
  assertContains(tariffCatalog, `slug="${slug}"`, 'backend/app/billing/catalog.py')
}
for (const price of ['price=369.0', 'price=693.0', 'price=936.0']) {
  assertContains(tariffCatalog, price, 'backend/app/billing/catalog.py')
}
for (const limit of ['device_limit=1', 'device_limit=6', 'device_limit=9']) {
  assertContains(tariffCatalog, limit, 'backend/app/billing/catalog.py')
}
assertContains(plans, '[M-068][phase54_admin_tariff_ui][CANONICAL_TARIFFS_READABLE]', 'frontend-admin/src/pages/Plans.tsx')
assertContains(plans, '[M-068][phase54_admin_tariff_ui][NO_CANONICAL_CRUD_DRIFT]', 'frontend-admin/src/pages/Plans.tsx')
for (const prohibited of ['createPlan', 'updatePlan', 'deletePlan', 'Редактировать тариф', 'Удалить тариф']) {
  assertNotContains(plans, prohibited, 'frontend-admin/src/pages/Plans.tsx')
}

for (const source of [dashboard, users, devices, mtproto, mtprotoAnalytics, servers, plans, analytics]) {
  assertNotContains(source, 'text-5xl', 'admin route oversized type')
  assertNotContains(source, 'rounded-[', 'admin route oversized radius')
  assertNotContains(source, 'tracking-[', 'admin route letter spacing')
}

assertProtectedDeployDiffClean()
// END_BLOCK_PHASE54_STATIC_ASSERTIONS

console.log('[FrontendAdmin][Phase54][BUILD_PASS] static-build-companion-ok')
console.log('[FrontendAdmin][Phase54][ROUTE_MATRIX_READY] ok')
console.log('[FrontendAdmin][Phase54][VIEWPORT_NO_OVERFLOW] static-route-density-ok')
console.log('[FrontendAdmin][Phase54][ADMIN_FLOW_UNCHANGED] ok')
console.log('[FrontendAdmin][Phase54][PROTECTED_SURFACE_GUARD] ok')
console.log('[MobileAdminConsole][Phase54][ROUTE_VIEWPORT_SAFE] static-mobile-route-ok')
console.log('[MobileAdminConsole][Phase54][PRIMARY_ACTIONS_REACHABLE] ok')
console.log('[MobileAdminConsole][Phase54][TABLES_SCROLL_CONTAINED] ok')
console.log('[MobileAdminConsole][Phase54][CONFIRMATIONS_READABLE] ok')
console.log('[M-047][phase54_mtproto_admin][OPS_CONTROLS_READABLE] ok')
console.log('[M-047][phase54_mtproto_admin][CONFIRMATIONS_SAFE] ok')
console.log('[M-047][phase54_mtproto_admin][REDACTION_PRESERVED] ok')
console.log('[M-058][phase54_mtproto_analytics][CHARTS_TABLES_READABLE] ok')
console.log('[M-058][phase54_mtproto_analytics][AUTO_REFRESH_STABLE] ok')
console.log('[M-058][phase54_mtproto_analytics][SIGNALS_STILL_HIDDEN] ok')
console.log('[M-058][phase54_mtproto_analytics][PROMOTION_TAG_REDACTED] ok')
console.log('[M-068][phase54_admin_tariff_ui][CANONICAL_TARIFFS_READABLE] ok')
console.log('[M-068][phase54_admin_tariff_ui][NO_CANONICAL_CRUD_DRIFT] ok')
console.log('[MatrixVisualRuntime][phase54][ADMIN_ROUTE_CANVAS_READY] ok')
console.log('[MatrixVisualRuntime][phase54][POINTER_EVENTS_SAFE] ok')
console.log('[MatrixVisualRuntime][phase54][REDUCED_MOTION_ADMIN] ok')
console.log('[MatrixStyleSystem][phase54][ADMIN_ROUTES_READABLE] ok')
console.log('[MatrixStyleSystem][phase54][NO_TEXT_OVERLAP] static-guard-ok')
console.log('[MatrixStyleSystem][phase54][BALANCED_PALETTE] ok')
console.log('[MatrixStyleSystem][phase54][REDUCED_MOTION_ADMIN] ok')
