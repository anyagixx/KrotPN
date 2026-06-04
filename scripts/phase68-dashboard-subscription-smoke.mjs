#!/usr/bin/env node
/*
 * FILE: scripts/phase68-dashboard-subscription-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke verification for Phase-68 dashboard subscription merge and cabinet compaction
 *   SCOPE: Dashboard MTProto-first layout, shared subscription panel, tariff display aliases, compact calendar, frameless shell logo, config page pruning, i18n-backed pending copy, and protected surface guard
 *   DEPENDS: M-075, M-036, M-045, M-063, M-068, M-071, M-074, M-077, M-080, M-009
 *   LINKS: V-M-075, V-M-036, V-M-045, V-M-063, V-M-068, V-M-071, V-M-074, V-M-077, V-M-080, V-M-009, docs/plans/Phase-68.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository files for static assertions
 *   assertContains - Fails if a file lacks a required marker
 *   assertNotContains - Fails if a file contains prohibited Phase-68 content
 *   assertProtectedSurfaceDiffClean - Fails if Phase-68 touched backend/deploy/runtime surfaces
 *   main - Runs Phase-68 static assertions and prints required verification markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.1 - Aligned pending-first-connection copy assertion with i18n-backed SubscriptionPanel rendering.
 *   LAST_CHANGE: v1.0.0 - Added Phase-68 dashboard subscription merge smoke gate.
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
    throw new Error(`${label} is missing required Phase-68 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-68 marker: ${needle}`)
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
      throw new Error(`Protected Phase-68 surface missing from repository: ${protectedPath}`)
    }
  }

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (diff) {
    throw new Error(`Phase-68 must not change backend/deploy/runtime/install surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE68_STATIC_ASSERTIONS
const css = read('frontend/src/index.css')
const layout = read('frontend/src/components/Layout.tsx')
const dashboard = read('frontend/src/pages/Dashboard.tsx')
const subscription = read('frontend/src/pages/Subscription.tsx')
const subscriptionPanel = read('frontend/src/components/SubscriptionPanel.tsx')
const config = read('frontend/src/pages/Config.tsx')
const i18n = read('frontend/src/i18n/index.ts')

for (const [label, source] of [
  ['frontend/src/index.css', css],
  ['frontend/src/components/Layout.tsx', layout],
  ['frontend/src/pages/Dashboard.tsx', dashboard],
  ['frontend/src/pages/Subscription.tsx', subscription],
  ['frontend/src/components/SubscriptionPanel.tsx', subscriptionPanel],
  ['frontend/src/pages/Config.tsx', config],
]) {
  assertContains(source, 'START_MODULE_CONTRACT', label)
  assertContains(source, 'START_MODULE_MAP', label)
  assertContains(source, 'START_CHANGE_SUMMARY', label)
}

for (const needle of [
  'data-phase68-dashboard="mtproto-subscription-compact"',
  'data-phase68-mtproto-card="primary-first"',
  '<SubscriptionPanel compact />',
  'Ваш бесплатный постоянный',
  'Telegram MTProto',
  'MTPROTO_STATUS_REFRESH_MS = 30000',
  'tg://proxy?',
  'https://t.me/proxy?',
  'Ссылка',
  'Сервер',
  'Порт',
  'Секрет',
]) {
  assertContains(dashboard, needle, 'frontend/src/pages/Dashboard.tsx')
}

for (const prohibited of [
  'data-phase57-command-center="true"',
  'data-phase57-dashboard-signal-strip="true"',
  'phase62-secondary-fold',
  'Индивидуальный Telegram proxy готов к использованию.',
  'Личный proxy',
  'Трафик, сервер и устройства',
]) {
  assertNotContains(dashboard, prohibited, 'frontend/src/pages/Dashboard.tsx')
}

for (const needle of [
  'data-phase68-dashboard-subscription="merged"',
  'data-phase57-subscription-countdown="server-derived"',
  'data-phase53-tariff-catalog="canonical-three-plans"',
  'data-phase57-tariff-catalog="canonical-three-plans"',
  'data-phase45-subscription-calendar="true"',
  'data-phase57-subscription-calendar="active-range"',
  'data-phase68-subscription-calendar="compact-cross-month"',
  'phase68-calendar-months',
  'KrotPN Self',
  'KrotPN Family',
  'KrotPN Team',
  'Персональный тариф',
  'Тариф для семьи',
  'Тариф для команды',
  'billingApi.createPayment(planId)',
  'User,',
  'Users,',
  'Briefcase,',
  "t('subscriptionDescriptionPending')",
]) {
  assertContains(subscriptionPanel, needle, 'frontend/src/components/SubscriptionPanel.tsx')
}
assertContains(i18n, 'Конфиг уже доступен. Таймер на 4 дня стартует после первого подключения.', 'frontend/src/i18n/index.ts')

for (const slug of ['krotpn-1', 'krotpn-6', 'krotpn-9']) {
  assertContains(subscriptionPanel, slug, 'frontend/src/components/SubscriptionPanel.tsx')
}

for (const prohibited of [
  'Детали тарифа',
  'Три тарифа KrotPN',
  'Оплата создается backend',
  'Trial начнется после первого VPN подключения',
  'handshake',
  'Календарь доступа',
  'Активные даты',
  'createPayment(plan.price',
  'createPayment({',
]) {
  assertNotContains(subscriptionPanel, prohibited, 'frontend/src/components/SubscriptionPanel.tsx')
}

assertContains(subscription, 'data-phase68-subscription-route="compatibility-wrapper"', 'frontend/src/pages/Subscription.tsx')
assertContains(subscription, '<SubscriptionPanel />', 'frontend/src/pages/Subscription.tsx')

for (const needle of [
  'phase68-shell-logo',
  'data-phase68-user-shell-logo="frameless"',
  '.phase68-shell-logo .phase63-brand-mark',
  'START_BLOCK_PHASE68_DASHBOARD_SUBSCRIPTION_COMPACTION',
  '.phase68-plan-grid',
  '.phase68-calendar-months',
  '[Phase68][DashboardSubscription][COMPACT_MERGE_READY]',
  '[VisibleBrandLogo][phase68][FRAMELESS_USER_SHELL_LOGO]',
]) {
  assertContains(layout + css, needle, 'frontend user layout/css')
}

for (const needle of [
  'data-phase57-config-workflow="qr-download-copy-device"',
  'data-phase57-config-actions="qr-download-copy"',
  'data-phase57-device-list="scroll-safe"',
  'CONFIG_DOWNLOAD_MIME_TYPE',
  'buildConfigDownloadBlob',
  'buildConfigDownloadFilename',
  'handleDownload',
  'handleCopy',
  'handleCreateDevice',
  'QRCodeCanvas',
]) {
  assertContains(config, needle, 'frontend/src/pages/Config.tsx')
}

for (const prohibited of [
  'data-phase57-raw-config="collapsed"',
  'data-phase62-collapse="config-diagnostics"',
  'Raw config fallback',
  'Диагностика конфига',
  'showRawConfig',
]) {
  assertNotContains(config, prohibited, 'frontend/src/pages/Config.tsx')
}

assertProtectedSurfaceDiffClean()
// END_BLOCK_PHASE68_STATIC_ASSERTIONS

console.log('[Phase68][DashboardSubscription][MTPROTO_FIRST_READY] ok')
console.log('[Phase68][DashboardSubscription][COMPACT_MERGE_READY] ok')
console.log('[Phase68][DashboardSubscription][TARIFF_ALIASES_READY] ok')
console.log('[Phase68][DashboardSubscription][CROSS_MONTH_CALENDAR_READY] ok')
console.log('[VisibleBrandLogo][phase68][FRAMELESS_USER_SHELL_LOGO] ok')
console.log('[Phase68][ConfigCompaction][RAW_DIAGNOSTICS_REMOVED] ok')
console.log('[Phase68][ProtectedSurfaceGuard][NO_BACKEND_DEPLOY_DRIFT] ok')
