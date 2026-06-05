#!/usr/bin/env node
/*
 * FILE: scripts/phase79-cyber-title-and-mtproto-promo-safe-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: SCRIPT
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke for Phase-79 cyber title styling and promo-safe MTProto anti-abuse policy
 *   SCOPE: Auth title markers, CDN-free title font stack, reduced-motion safeguards, promo-sharing admin copy,
 *          observe-only MTProto abuse thresholds, manual-only alert enforcement, promotion tag independence,
 *          and protected deploy/runtime topology guard
 *   DEPENDS: M-073, M-071, M-056, M-060, M-058, M-059
 *   LINKS: V-M-073, V-M-071, V-M-056, V-M-060, V-M-058, V-M-059, docs/plans/Phase-79.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository files for deterministic static assertions
 *   assertContains - Fails on missing required Phase-79 marker
 *   assertAbsent - Fails on forbidden marker
 *   assertProtectedRuntimeDiffClean - Guards install/deploy/runtime topology from Phase-79 drift
 *   main - Runs Phase-79 static assertions and prints verification markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-79 cyber title and promo-safe MTProto static gate
 * END_CHANGE_SUMMARY
 */

import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const root = process.cwd()

// START_BLOCK_SMOKE_HELPERS
function read(relativePath) {
  return readFileSync(join(root, relativePath), 'utf8')
}

function assertContains(text, marker, path) {
  if (!text.includes(marker)) {
    throw new Error(`Missing Phase-79 marker in ${path}: ${marker}`)
  }
}

function assertAbsent(text, marker, path) {
  if (text.includes(marker)) {
    throw new Error(`Forbidden Phase-79 marker in ${path}: ${marker}`)
  }
}

function assertProtectedRuntimeDiffClean() {
  const protectedPaths = [
    'install.sh',
    'docker-compose.yml',
    'nginx',
    'deploy',
    'deploy/mtproto-de-compose.yml',
    '.env.example',
    'mtproto-runtime',
    'official-mtproxy',
    'telegram-bot',
  ]

  for (const protectedPath of protectedPaths) {
    if (!existsSync(join(root, protectedPath))) {
      throw new Error(`Protected Phase-79 surface missing: ${protectedPath}`)
    }
  }

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  const violations = diff.split('\n').map((line) => line.trim()).filter(Boolean)
  if (violations.length) {
    throw new Error(`Phase-79 must not change deploy/install/runtime topology: ${violations.join(', ')}`)
  }
}
// END_BLOCK_SMOKE_HELPERS

// START_BLOCK_PHASE79_STATIC_ASSERTIONS
const cssPath = 'frontend/src/index.css'
const loginPath = 'frontend/src/pages/Login.tsx'
const registerPath = 'frontend/src/pages/Register.tsx'
const forgotPath = 'frontend/src/pages/ForgotPassword.tsx'
const resetPath = 'frontend/src/pages/ResetPassword.tsx'
const verifyPath = 'frontend/src/pages/VerifyEmail.tsx'
const landingPath = 'frontend/src/pages/Landing.tsx'
const analyticsPath = 'backend/app/mtproto/analytics_service.py'
const analyticsTestPath = 'backend/tests/test_mtproto_analytics_service.py'
const alertsPath = 'backend/app/mtproto/admin_alerts.py'
const alertsTestPath = 'backend/tests/test_mtproto_admin_alerts.py'
const adminUiPath = 'frontend-admin/src/pages/MTProtoAnalytics.tsx'
const promotionTagPath = 'backend/app/mtproto/promotion_tag.py'

const css = read(cssPath)
const landing = read(landingPath)
const analytics = read(analyticsPath)
const analyticsTests = read(analyticsTestPath)
const alerts = read(alertsPath)
const alertsTests = read(alertsTestPath)
const adminUi = read(adminUiPath)
const promotionTag = read(promotionTagPath)

for (const path of [loginPath, registerPath, forgotPath, resetPath, verifyPath]) {
  const source = read(path)
  assertContains(source, 'Кибернетический Протокол Навигации', path)
}
assertAbsent(landing, 'Кибернетический Протокол Навигации', landingPath)

for (const marker of [
  'START_BLOCK_PHASE79_CYBER_TITLE',
  '--phase79-cyber-title-pink: #ff36d7',
  '--phase79-cyber-title-font',
  'phase79CyberTitlePulse',
  '[MatrixStyle][phase79][CYBER_TITLE_ACID_PINK]',
  '[PremiumPublicSite][phase79][CYBER_TITLE_POLISHED]',
  'letter-spacing: 0',
  'prefers-reduced-motion',
]) {
  assertContains(css, marker, cssPath)
}
const phase79CssBlock = css.slice(css.indexOf('START_BLOCK_PHASE79_CYBER_TITLE'), css.indexOf('END_BLOCK_PHASE79_CYBER_TITLE'))
assertAbsent(phase79CssBlock, 'http://', cssPath)
assertAbsent(phase79CssBlock, 'https://', cssPath)
assertAbsent(phase79CssBlock, '@import', cssPath)

for (const marker of [
  '_recent_ip_observation_concurrency',
  'timedelta(minutes=15)',
  '_recent_ip_observation_concurrency(events, end=end)',
  '[M-056][detect_abuse_signals][OBSERVE_ONLY]',
  '[M-056][detect_abuse_signals][ALERT_HANDOFF]',
]) {
  assertContains(analytics, marker, analyticsPath)
}
for (const marker of [
  'test_promo_proxy_sharing_many_ips_over_time_stays_observe_only',
  'test_hard_concurrent_multi_ip_activity_creates_alert_only',
  'alerts["open_count"] == 0',
  'assignment.status.value == "active"',
]) {
  assertContains(analyticsTests, marker, analyticsTestPath)
}

const createAlertBlock = alerts.slice(alerts.indexOf('START_BLOCK_CREATE_ALERT'), alerts.indexOf('END_BLOCK_CREATE_ALERT'))
assertAbsent(createAlertBlock, 'MTProtoAssignmentStatus.DISABLED', alertsPath)
assertAbsent(createAlertBlock, 'MTProtoBlockedIP(', alertsPath)
assertContains(alerts, '[M-060][create_abuse_alert][ALERT_CREATED]', alertsPath)
assertContains(alertsTests, 'MTProtoAssignmentStatus.ACTIVE', alertsTestPath)
assertContains(alertsTests, 'blocked_result.scalars().all() == []', alertsTestPath)

for (const marker of [
  'Обычное расшаривание MTProto proxy для промо разрешено',
  'Автоблокировок нет, решение принимает только администратор',
  '[M-058][admin_mtproto_analytics_ui][ALERT_REVIEW]',
  '[M-058][admin_mtproto_analytics_ui][ALERT_ARCHIVE]',
]) {
  assertContains(adminUi, marker, adminUiPath)
}
assertAbsent(adminUi, '<h3 className="text-sm font-semibold text-white">Signals</h3>', adminUiPath)
assertAbsent(adminUi, 'https://t.me/proxy?', adminUiPath)
assertAbsent(adminUi, 'tg://proxy?server=', adminUiPath)

for (const marker of [
  'validate_promotion_tag',
  '[M-059][promotion_tag_state][REDACTED_STATE]',
  'masked_tag',
]) {
  assertContains(promotionTag, marker, promotionTagPath)
}

assertProtectedRuntimeDiffClean()
console.log('[MatrixStyle][phase79][CYBER_TITLE_ACID_PINK] pass')
console.log('[PremiumPublicSite][phase79][CYBER_TITLE_POLISHED] pass')
console.log('[M-056][phase79][PROMO_SHARING_OBSERVE_ONLY] pass')
console.log('[M-060][phase79][MANUAL_ENFORCEMENT_ONLY] pass')
console.log('[M-058][phase79][PROMO_SAFE_ALERT_COPY] pass')
console.log('[M-059][phase79][PROMOTION_TAG_INDEPENDENT] pass')
console.log('phase79 cyber title and mtproto promo-safe smoke: ok')
// END_BLOCK_PHASE79_STATIC_ASSERTIONS
