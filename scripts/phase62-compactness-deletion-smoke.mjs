#!/usr/bin/env node
/*
 * FILE: scripts/phase62-compactness-deletion-smoke.mjs
 * VERSION: 1.1.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke verification for Phase-62 compactness and deletion audit with Phase-67 splash supersession awareness
 *   SCOPE: User/public/admin folded secondary surfaces, Phase-67 splash public replacement, preserved primary workflows, bounded admin inventories, redaction/confirmation invariants, responsive compaction markers, and protected backend/deploy/runtime guard
 *   DEPENDS: M-075, M-076, M-038, M-073, M-074
 *   LINKS: V-M-075, V-M-076, docs/plans/Phase-62.xml, docs/modules/M-075.xml, docs/modules/M-076.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository files for deterministic static assertions
 *   assertContains - Fails if a file lacks a required marker
 *   assertNotContains - Fails if a file contains a prohibited marker
 *   assertAtLeast - Fails if a repeated marker count is below the required threshold
 *   assertProtectedSurfaceDiffClean - Fails if Phase-62 touched backend/deploy/runtime/install surfaces
 *   main - Runs Phase-62 compactness/deletion audit checks and prints required verification markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.1.0 - Accepted Phase-67 splash-only public route while preserving public/auth clarity markers.
 *   LAST_CHANGE: v1.0.0 - Added Phase-62 compactness/deletion audit smoke gate.
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
    throw new Error(`${label} is missing required Phase-62 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-62 marker: ${needle}`)
  }
}

function assertAtLeast(source, needle, minimum, label) {
  const count = source.split(needle).length - 1
  if (count < minimum) {
    throw new Error(`${label} expected at least ${minimum} occurrences of ${needle}, got ${count}`)
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
    'telegram-bot',
  ]

  for (const protectedPath of protectedPaths) {
    if (!existsSync(join(root, protectedPath))) {
      throw new Error(`Protected Phase-62 surface missing from repository: ${protectedPath}`)
    }
  }

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (diff) {
    throw new Error(`Phase-62 must not change backend/deploy/runtime/install surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE62_STATIC_ASSERTIONS
const userCss = read('frontend/src/index.css')
const adminCss = read('frontend-admin/src/index.css')
const dashboard = read('frontend/src/pages/Dashboard.tsx')
const config = read('frontend/src/pages/Config.tsx')
const subscription = read('frontend/src/pages/Subscription.tsx')
const referrals = read('frontend/src/pages/Referrals.tsx')
const settings = read('frontend/src/pages/Settings.tsx')
const landing = read('frontend/src/pages/Landing.tsx')
const register = read('frontend/src/pages/Register.tsx')
const forgot = read('frontend/src/pages/ForgotPassword.tsx')
const reset = read('frontend/src/pages/ResetPassword.tsx')
const verify = read('frontend/src/pages/VerifyEmail.tsx')
const adminDashboard = read('frontend-admin/src/pages/Dashboard.tsx')
const adminUsers = read('frontend-admin/src/pages/Users.tsx')
const adminDevices = read('frontend-admin/src/pages/Devices.tsx')
const adminMtproto = read('frontend-admin/src/pages/MTProto.tsx')
const adminMtprotoAnalytics = read('frontend-admin/src/pages/MTProtoAnalytics.tsx')
const adminServers = read('frontend-admin/src/pages/Servers.tsx')
const adminPlans = read('frontend-admin/src/pages/Plans.tsx')
const adminAnalytics = read('frontend-admin/src/pages/Analytics.tsx')

for (const [label, source] of [
  ['frontend/src/index.css', userCss],
  ['frontend-admin/src/index.css', adminCss],
  ['frontend/src/pages/Dashboard.tsx', dashboard],
  ['frontend/src/pages/Config.tsx', config],
  ['frontend/src/pages/Subscription.tsx', subscription],
  ['frontend/src/pages/Landing.tsx', landing],
  ['frontend-admin/src/pages/MTProtoAnalytics.tsx', adminMtprotoAnalytics],
  ['frontend-admin/src/pages/Servers.tsx', adminServers],
]) {
  assertContains(source, 'START_MODULE_CONTRACT', label)
  assertContains(source, 'START_MODULE_MAP', label)
  assertContains(source, 'START_CHANGE_SUMMARY', label)
  assertContains(source, 'Phase-62', label)
}

for (const [label, source] of [
  ['frontend/src/pages/Dashboard.tsx', dashboard],
  ['frontend/src/pages/Config.tsx', config],
  ['frontend/src/pages/Subscription.tsx', subscription],
]) {
  assertContains(source, 'data-phase62-user-surface=', label)
  assertContains(source, 'data-phase62-collapse=', label)
  assertContains(source, '[CompactDeletionAudit][phase62][PRIMARY_WORKFLOWS_PRESERVED]', label)
}

assertContains(userCss, 'START_BLOCK_PHASE62_COMPACTNESS_DELETION_AUDIT', 'frontend/src/index.css')
assertContains(userCss, '.phase62-secondary-fold', 'frontend/src/index.css')
assertContains(userCss, '.phase62-inline-details', 'frontend/src/index.css')
assertContains(userCss, '.phase62-public-fold', 'frontend/src/index.css')
assertContains(userCss, 'min-height: 44px', 'frontend/src/index.css')
assertContains(userCss, '[CompactDeletionAudit][phase62][RESPONSIVE_COMPACTNESS_PRESERVED]', 'frontend/src/index.css')
assertAtLeast(dashboard + config + subscription + landing, 'data-phase62-collapse=', 5, 'user/public folded surfaces')

for (const needle of [
  'data-phase57-primary-actions-reachable="true"',
  'data-phase57-primary-action="vpn-config"',
  'data-phase57-primary-action="subscription"',
  'data-phase57-primary-action="mtproto-copy"',
  'data-phase57-config-actions="qr-download-copy"',
  'data-phase57-raw-config="collapsed"',
  'data-phase57-subscription-countdown="server-derived"',
  'data-phase57-subscription-calendar="active-range"',
  'billingApi.createPayment(planId)',
  'tg://proxy?',
  'https://t.me/proxy?',
]) {
  assertContains(dashboard + config + subscription, needle, 'preserved user workflows')
}

assertContains(landing, 'data-phase62-public-auth="[CompactDeletionAudit][phase62][PUBLIC_AUTH_CLARITY_PRESERVED]"', 'frontend/src/pages/Landing.tsx')
assertContains(landing, 'data-phase56-email-proof-copy=', 'frontend/src/pages/Landing.tsx')
assertContains(landing, 'data-phase67-splash-route="[PremiumPublicSite][phase67][SPLASH_REDIRECT_READY]"', 'frontend/src/pages/Landing.tsx')
assertContains(register, 'папку «Спам»', 'frontend/src/pages/Register.tsx')
assertContains(register, 'passwordPolicyExample', 'frontend/src/pages/Register.tsx')
assertContains(register, 'Восстановить доступ', 'frontend/src/pages/Register.tsx')
assertContains(forgot, 'authApi.requestPasswordReset', 'frontend/src/pages/ForgotPassword.tsx')
assertContains(reset, 'authApi.confirmPasswordReset', 'frontend/src/pages/ResetPassword.tsx')
assertContains(verify, 'authApi.verifyEmail', 'frontend/src/pages/VerifyEmail.tsx')

for (const [label, source] of [
  ['frontend-admin/src/pages/MTProtoAnalytics.tsx', adminMtprotoAnalytics],
  ['frontend-admin/src/pages/Servers.tsx', adminServers],
]) {
  assertContains(source, 'data-phase62-admin-surface=', label)
  assertContains(source, 'data-phase62-collapse=', label)
}

assertContains(adminCss, 'START_BLOCK_PHASE62_COMPACTNESS_DELETION_AUDIT', 'frontend-admin/src/index.css')
assertContains(adminCss, '.phase62-admin-fold', 'frontend-admin/src/index.css')
assertContains(adminCss, '[CompactDeletionAudit][phase62][ADMIN_INVENTORIES_BOUNDED]', 'frontend-admin/src/index.css')
assertContains(adminServers, 'data-phase62-bounded="[CompactDeletionAudit][phase62][ADMIN_INVENTORIES_BOUNDED]"', 'frontend-admin/src/pages/Servers.tsx')
assertContains(adminMtprotoAnalytics, '[CompactDeletionAudit][phase62][EMERGENCY_CONTROLS_PRESERVED]', 'frontend-admin/src/pages/MTProtoAnalytics.tsx')
assertContains(adminMtprotoAnalytics, '[M-058][admin_mtproto_analytics_ui][ALERT_ARCHIVE]', 'frontend-admin/src/pages/MTProtoAnalytics.tsx')
assertContains(adminMtprotoAnalytics, '[M-058][phase54_mtproto_analytics][PROMOTION_TAG_REDACTED]', 'frontend-admin/src/pages/MTProtoAnalytics.tsx')

for (const [label, source] of [
  ['frontend-admin/src/pages/Dashboard.tsx', adminDashboard],
  ['frontend-admin/src/pages/Users.tsx', adminUsers],
  ['frontend-admin/src/pages/Devices.tsx', adminDevices],
  ['frontend-admin/src/pages/MTProto.tsx', adminMtproto],
  ['frontend-admin/src/pages/Servers.tsx', adminServers],
  ['frontend-admin/src/pages/Plans.tsx', adminPlans],
  ['frontend-admin/src/pages/Analytics.tsx', adminAnalytics],
]) {
  assertContains(source, 'data-phase58-route=', label)
  assertContains(source, 'min-w-0', label)
}
assertContains(adminMtprotoAnalytics, 'data-phase54-mtproto-analytics="compact"', 'frontend-admin/src/pages/MTProtoAnalytics.tsx')
assertContains(adminMtprotoAnalytics, 'data-phase58-runtime-readonly="[PremiumAdminCockpit][phase58][ANALYTICS_RUNTIME_READONLY]"', 'frontend-admin/src/pages/MTProtoAnalytics.tsx')

for (const needle of [
  '[PremiumAdminCockpit][phase58][CONFIRMATION_GUARDS]',
  '[PremiumAdminCockpit][phase58][MTPROTO_REDACTION]',
  '[PremiumAdminCockpit][phase58][TARIFF_ADMIN_GUARD]',
  '[PremiumAdminCockpit][phase58][ANALYTICS_RUNTIME_READONLY]',
]) {
  assertContains(adminDevices + adminMtproto + adminMtprotoAnalytics + adminServers + adminPlans + adminAnalytics, needle, 'preserved admin safeguards')
}

for (const prohibited of [
  'Recent events',
  'unmasked_secret',
  'full_proxy_url',
  'raw_promotion_tag',
  'createPayment(plan.price',
  'Trial на 3',
  'trial на 3',
  'radial-gradient(',
  'font-size: clamp(',
  'font-size: calc(',
]) {
  assertNotContains(userCss + adminCss + dashboard + config + subscription + landing + adminMtprotoAnalytics + adminServers, prohibited, 'Phase-62 compactness surfaces')
}

assertProtectedSurfaceDiffClean()
// END_BLOCK_PHASE62_STATIC_ASSERTIONS

console.log('[CompactDeletionAudit][phase62][USER_SURFACES_INVENTORIED] ok')
console.log('[CompactDeletionAudit][phase62][USER_SURFACES_PRUNED] ok')
console.log('[CompactDeletionAudit][phase62][PRIMARY_WORKFLOWS_PRESERVED] ok')
console.log('[CompactDeletionAudit][phase62][PUBLIC_AUTH_CLARITY_PRESERVED] ok')
console.log('[CompactDeletionAudit][phase62][RESPONSIVE_COMPACTNESS_PRESERVED] ok')
console.log('[CompactDeletionAudit][phase62][ADMIN_SURFACES_INVENTORIED] ok')
console.log('[CompactDeletionAudit][phase62][ADMIN_SURFACES_PRUNED] ok')
console.log('[CompactDeletionAudit][phase62][EMERGENCY_CONTROLS_PRESERVED] ok')
console.log('[CompactDeletionAudit][phase62][REDACTION_CONFIRMATION_PRESERVED] ok')
console.log('[CompactDeletionAudit][phase62][ADMIN_INVENTORIES_BOUNDED] ok')
console.log('[CompactDeletionAudit][phase62][NO_BACKEND_DEPLOY_DRIFT] ok')
