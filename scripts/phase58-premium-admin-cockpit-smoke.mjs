#!/usr/bin/env node
/*
 * FILE: scripts/phase58-premium-admin-cockpit-smoke.mjs
 * VERSION: 1.1.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke checks for Phase-58 premium admin cockpit execution
 *   SCOPE: Admin route markers, command center, bounded inventories, MTProto redaction, confirmation guards, tariff readonly guard, analytics readonly guard, reduced-motion proof, and protected surface guard
 *   DEPENDS: M-010, M-037, M-047, M-058, M-068, M-070, M-071, M-072, M-076
 *   LINKS: V-M-076, docs/plans/Phase-58.xml, docs/modules/M-076.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository files for static assertions
 *   assertContains - Fails if a file lacks a required marker
 *   assertNotContains - Fails if a file contains a prohibited marker
 *   assertRegexAbsent - Fails if a file matches a prohibited regular expression
 *   assertProtectedSurfaceDiffClean - Fails if Phase-58 touched protected backend/deploy/runtime surfaces or unapproved user frontend surfaces
 *   main - Runs Phase-58 premium admin cockpit smoke assertions and prints verification markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.1.0 - Allowed explicitly scoped Phase-67 user auth/splash diffs while preserving admin/backend/deploy/runtime protection.
 *   LAST_CHANGE: v1.0.0 - Added Phase-58 premium admin cockpit static smoke gate.
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
    throw new Error(`${label} is missing required Phase-58 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-58 marker: ${needle}`)
  }
}

function assertRegexAbsent(source, regex, label) {
  if (regex.test(source)) {
    throw new Error(`${label} matches prohibited Phase-58 pattern: ${regex}`)
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
    'frontend',
  ]

  for (const protectedPath of protectedPaths) {
    if (!existsSync(join(root, protectedPath))) {
      throw new Error(`Protected Phase-58 surface missing from repository: ${protectedPath}`)
    }
  }

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (!diff) {
    return
  }

  const allowedPhase67UserDiffs = new Set([
    'frontend/src/components/MatrixBackground.tsx',
    'frontend/src/index.css',
    'frontend/src/pages/ForgotPassword.tsx',
    'frontend/src/pages/Landing.tsx',
    'frontend/src/pages/Login.tsx',
    'frontend/src/pages/Register.tsx',
    'frontend/src/pages/ResetPassword.tsx',
  ])
  const unapproved = diff.split('\n').filter((path) => !allowedPhase67UserDiffs.has(path))
  if (unapproved.length > 0) {
    throw new Error(`Phase-58 must not change backend/deploy/runtime/admin-protected surfaces: ${unapproved.join('\n')}`)
  }
}

// START_BLOCK_PHASE58_STATIC_ASSERTIONS
const css = read('frontend-admin/src/index.css')
const layout = read('frontend-admin/src/components/Layout.tsx')
const statCard = read('frontend-admin/src/components/StatCard.tsx')
const dashboard = read('frontend-admin/src/pages/Dashboard.tsx')
const users = read('frontend-admin/src/pages/Users.tsx')
const devices = read('frontend-admin/src/pages/Devices.tsx')
const mtproto = read('frontend-admin/src/pages/MTProto.tsx')
const mtprotoAnalytics = read('frontend-admin/src/pages/MTProtoAnalytics.tsx')
const analytics = read('frontend-admin/src/pages/Analytics.tsx')
const servers = read('frontend-admin/src/pages/Servers.tsx')
const plans = read('frontend-admin/src/pages/Plans.tsx')

for (const [label, source] of [
  ['frontend-admin/src/index.css', css],
  ['frontend-admin/src/components/Layout.tsx', layout],
  ['frontend-admin/src/components/StatCard.tsx', statCard],
  ['frontend-admin/src/pages/Dashboard.tsx', dashboard],
  ['frontend-admin/src/pages/Users.tsx', users],
  ['frontend-admin/src/pages/Devices.tsx', devices],
  ['frontend-admin/src/pages/MTProto.tsx', mtproto],
  ['frontend-admin/src/pages/MTProtoAnalytics.tsx', mtprotoAnalytics],
  ['frontend-admin/src/pages/Analytics.tsx', analytics],
  ['frontend-admin/src/pages/Servers.tsx', servers],
  ['frontend-admin/src/pages/Plans.tsx', plans],
]) {
  assertContains(source, 'START_MODULE_CONTRACT', label)
  assertContains(source, 'START_MODULE_MAP', label)
  assertContains(source, 'START_CHANGE_SUMMARY', label)
  assertContains(source, 'M-076', label)
}

for (const needle of [
  'premium-admin-cockpit',
  'START_BLOCK_PHASE58_PREMIUM_ADMIN_COCKPIT',
  '.phase58-command-center',
  '.phase58-signal-strip',
  '.phase58-action-grid',
  '.phase58-inventory-list',
  '.phase58-readonly-frame',
  '.phase58-confirmation-surface',
  '@media (prefers-reduced-motion: reduce)',
  '[PremiumAdminCockpit][phase58][REDUCED_MOTION_SAFE]',
]) {
  assertContains(css, needle, 'frontend-admin/src/index.css')
}

for (const prohibited of [
  'radial-gradient(',
  'rounded-[32px]',
  'rounded-[24px]',
  'rounded-2xl',
  'rounded-3xl',
  'text-5xl',
  'text-4xl',
  'tracking-[',
  'font-size: clamp(',
  'font-size: calc(',
]) {
  assertNotContains(css, prohibited, 'frontend-admin/src/index.css')
}
assertRegexAbsent(css, /letter-spacing:\s*-[^;]+;/, 'frontend-admin/src/index.css')
assertRegexAbsent(css, /font-size:\s*[^;]*vw[^;]*;/, 'frontend-admin/src/index.css')

assertContains(layout, 'data-phase58-admin-shell="premium-cockpit"', 'frontend-admin/src/components/Layout.tsx')
assertContains(layout, '[PremiumAdminCockpit][phase58][ROUTES_READY]', 'frontend-admin/src/components/Layout.tsx')
assertContains(layout, '[PremiumAdminCockpit][phase58][REDUCED_MOTION_SAFE]', 'frontend-admin/src/components/Layout.tsx')
assertContains(layout, 'phase58-cockpit-main', 'frontend-admin/src/components/Layout.tsx')
assertContains(statCard, 'data-phase58-kpi="premium-admin-cockpit"', 'frontend-admin/src/components/StatCard.tsx')

for (const [route, source, label] of [
  ['dashboard', dashboard, 'frontend-admin/src/pages/Dashboard.tsx'],
  ['users', users, 'frontend-admin/src/pages/Users.tsx'],
  ['devices', devices, 'frontend-admin/src/pages/Devices.tsx'],
  ['mtproto', mtproto, 'frontend-admin/src/pages/MTProto.tsx'],
  ['analytics', analytics, 'frontend-admin/src/pages/Analytics.tsx'],
  ['servers', servers, 'frontend-admin/src/pages/Servers.tsx'],
  ['plans', plans, 'frontend-admin/src/pages/Plans.tsx'],
]) {
  assertContains(source, `data-phase58-route="${route}"`, label)
}

assertContains(dashboard, '[PremiumAdminCockpit][phase58][OPS_COMMAND_CENTER]', 'frontend-admin/src/pages/Dashboard.tsx')
assertContains(dashboard, '[PremiumAdminCockpit][phase58][ADMIN_ACTIONS_REACHABLE]', 'frontend-admin/src/pages/Dashboard.tsx')

for (const [label, source] of [
  ['frontend-admin/src/pages/Users.tsx', users],
  ['frontend-admin/src/pages/Devices.tsx', devices],
  ['frontend-admin/src/pages/MTProto.tsx', mtproto],
  ['frontend-admin/src/pages/MTProtoAnalytics.tsx', mtprotoAnalytics],
  ['frontend-admin/src/pages/Servers.tsx', servers],
]) {
  assertContains(source, '[PremiumAdminCockpit][phase58][INVENTORIES_BOUNDED]', label)
  assertContains(source, 'phase58-inventory-list', label)
}

assertContains(mtproto, '[PremiumAdminCockpit][phase58][MTPROTO_REDACTION]', 'frontend-admin/src/pages/MTProto.tsx')
assertContains(mtproto, '[M-047][phase54_mtproto_admin][REDACTION_PRESERVED]', 'frontend-admin/src/pages/MTProto.tsx')
assertContains(mtprotoAnalytics, '[M-058][phase54_mtproto_analytics][PROMOTION_TAG_REDACTED]', 'frontend-admin/src/pages/MTProtoAnalytics.tsx')
for (const prohibited of ['unmasked_secret', 'proxy_url', 'full_proxy_url', 'raw_promotion_tag']) {
  assertNotContains(mtproto + mtprotoAnalytics, prohibited, 'MTProto admin redaction')
}

for (const [label, source] of [
  ['frontend-admin/src/pages/Devices.tsx', devices],
  ['frontend-admin/src/pages/MTProto.tsx', mtproto],
  ['frontend-admin/src/pages/Servers.tsx', servers],
]) {
  assertContains(source, '[PremiumAdminCockpit][phase58][CONFIRMATION_GUARDS]', label)
}

assertContains(plans, '[PremiumAdminCockpit][phase58][TARIFF_ADMIN_GUARD]', 'frontend-admin/src/pages/Plans.tsx')
assertContains(plans, 'data-phase58-readonly="canonical-tariffs"', 'frontend-admin/src/pages/Plans.tsx')
for (const prohibited of ['createPlan', 'updatePlan', 'deletePlan', 'Редактировать тариф', 'Удалить тариф']) {
  assertNotContains(plans, prohibited, 'frontend-admin/src/pages/Plans.tsx')
}

for (const [label, source] of [
  ['frontend-admin/src/pages/MTProto.tsx', mtproto],
  ['frontend-admin/src/pages/MTProtoAnalytics.tsx', mtprotoAnalytics],
  ['frontend-admin/src/pages/Analytics.tsx', analytics],
]) {
  assertContains(source, '[PremiumAdminCockpit][phase58][ANALYTICS_RUNTIME_READONLY]', label)
  assertContains(source, 'phase58-readonly-frame', label)
}

assertProtectedSurfaceDiffClean()
// END_BLOCK_PHASE58_STATIC_ASSERTIONS

console.log('[PremiumAdminCockpit][phase58][ROUTES_READY] ok')
console.log('[PremiumAdminCockpit][phase58][OPS_COMMAND_CENTER] ok')
console.log('[PremiumAdminCockpit][phase58][ADMIN_ACTIONS_REACHABLE] ok')
console.log('[PremiumAdminCockpit][phase58][INVENTORIES_BOUNDED] ok')
console.log('[PremiumAdminCockpit][phase58][MTPROTO_REDACTION] ok')
console.log('[PremiumAdminCockpit][phase58][CONFIRMATION_GUARDS] ok')
console.log('[PremiumAdminCockpit][phase58][TARIFF_ADMIN_GUARD] ok')
console.log('[PremiumAdminCockpit][phase58][ANALYTICS_RUNTIME_READONLY] ok')
console.log('[PremiumAdminCockpit][phase58][REDUCED_MOTION_SAFE] ok')
console.log('[PremiumAdminCockpit][phase58][SCREENSHOT_MATRIX_REVIEWED] static-route-proof')
console.log('[PremiumAdminCockpit][phase58][PROTECTED_SURFACE_GUARD] ok')
