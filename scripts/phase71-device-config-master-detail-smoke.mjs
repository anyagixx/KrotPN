#!/usr/bin/env node
/*
 * FILE: scripts/phase71-device-config-master-detail-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke verification for Phase-71 per-device config retrieval API and compact master-detail user config UX
 *   SCOPE: Backend read-only selected-device endpoints, frontend API methods, /dashboard/config master-detail markers, QR close/icon polish, calendar boundary pulse, Phase-72 language-settings removal compatibility, i18n cleanup, and protected deploy/runtime surfaces
 *   DEPENDS: M-022, M-066, M-075, M-036, M-063, M-071, M-077, M-080, M-009, M-074
 *   LINKS: docs/plans/Phase-71.xml, docs/verification/V-M-022.xml, docs/verification/V-M-075.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository files for deterministic static assertions
 *   assertContains - Fails if a required source marker is missing
 *   assertNotContains - Fails if a prohibited source marker is present
 *   assertProtectedSurfaceDiffClean - Fails if deploy/install/runtime/admin surfaces drift during Phase-71
 *   main - Runs Phase-71 static assertions and prints aggregate markers only
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.2 - Accepted Phase-72 removal of visible language settings from Settings.
 *   LAST_CHANGE: v1.0.1 - Decoupled Phase-71 smoke from planning-only status text.
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
    throw new Error(`${label} is missing required Phase-71 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-71 marker: ${needle}`)
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
    'mtproto-runtime',
    'official-mtproxy',
    'telegram-bot',
    'frontend-admin',
  ]

  for (const protectedPath of protectedPaths) {
    if (!existsSync(join(root, protectedPath))) {
      throw new Error(`Protected Phase-71 surface missing from repository: ${protectedPath}`)
    }
  }

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (diff) {
    throw new Error(`Phase-71 must not change deploy/install/runtime/admin surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE71_STATIC_ASSERTIONS
const devicesRouter = read('backend/app/devices/router.py')
const deviceTests = read('backend/tests/test_device_api.py')
const api = read('frontend/src/lib/api.ts')
const configPage = read('frontend/src/pages/Config.tsx')
const layout = read('frontend/src/components/Layout.tsx')
const subscriptionPanel = read('frontend/src/components/SubscriptionPanel.tsx')
const settings = read('frontend/src/pages/Settings.tsx')
const i18n = read('frontend/src/i18n/index.ts')
const css = read('frontend/src/index.css')
const phase = read('docs/plans/Phase-71.xml')

for (const [label, source] of [
  ['backend/app/devices/router.py', devicesRouter],
  ['backend/tests/test_device_api.py', deviceTests],
  ['frontend/src/lib/api.ts', api],
  ['frontend/src/pages/Config.tsx', configPage],
  ['frontend/src/components/Layout.tsx', layout],
  ['frontend/src/components/SubscriptionPanel.tsx', subscriptionPanel],
  ['frontend/src/pages/Settings.tsx', settings],
  ['frontend/src/i18n/index.ts', i18n],
  ['frontend/src/index.css', css],
]) {
  assertContains(source, 'MODULE_CONTRACT', label)
  assertContains(source, 'MODULE_MAP', label)
  assertContains(source, 'CHANGE_SUMMARY', label)
}

for (const needle of [
  'async def get_device_config(',
  'async def download_device_config(',
  'async def get_device_config_qr(',
  'async def get_device_config_qr_amnezia(',
  'await vpn.get_device_client(int(device.id))',
  'build_config_download_response(config.config, filename)',
  'build_config_qr_png(config.config, route_label="device_config")',
  'build_config_qr_png(json.dumps(amnezia_config), route_label="device_config_amnezia")',
  '[M-022][get_device_config][DEVICE_CONFIG_READ]',
  '[M-022][download_device_config][DEVICE_CONFIG_DOWNLOAD]',
  '[M-022][get_device_config_qr][DEVICE_CONFIG_QR]',
]) {
  assertContains(devicesRouter, needle, 'backend/app/devices/router.py')
}
for (const needle of [
  'test_get_device_config_returns_existing_config_without_rotation',
  'test_device_config_download_uses_mobile_safe_headers',
  'test_device_config_qr_uses_selected_device_payload',
  'test_device_config_amnezia_qr_wraps_selected_device_payload',
  'test_device_config_rejects_blocked_or_missing_device',
  'assert body["device"]["config_version"] == 1',
  'assert response.headers["content-type"] == "application/octet-stream"',
]) {
  assertContains(deviceTests, needle, 'backend/tests/test_device_api.py')
}

for (const needle of [
  'getConfig: (deviceId: number)',
  'downloadConfig: (deviceId: number)',
  'getQRCode: (deviceId: number)',
  'getAmneziaQRCode: (deviceId: number)',
  '`/devices/${deviceId}/config`',
  '`/devices/${deviceId}/config/download`',
]) {
  assertContains(api, needle, 'frontend/src/lib/api.ts')
}

for (const needle of [
  'data-phase71-route="device-master-detail"',
  'data-phase71-device-master-detail="[PremiumUserCabinet][phase71][DEVICE_MASTER_DETAIL_READY]"',
  'data-phase71-selected-device-exports="[PremiumUserCabinet][phase71][SELECTED_DEVICE_EXPORTS_SAFE]"',
  'data-phase71-sticky-actions="[ResponsiveAdaptation][phase71][MOBILE_STICKY_ACTIONS_SAFE]"',
  'data-phase71-secondary-actions="[PremiumUserCabinet][phase71][DESTRUCTIVE_ACTIONS_SECONDARY]"',
  'data-phase71-qr-close="[MatrixMotion][phase71][QR_CLOSE_ICON_SAFE]"',
  'deviceApi.getConfig(selectedDevice!.id)',
  'deviceApi.downloadConfig(selectedDevice.id)',
  'deviceApi.getQRCode(deviceId)',
  'deviceApi.getAmneziaQRCode(deviceId)',
  'className="phase71-icon-close motion-interactive"',
  'QRCodeCanvas',
  "const QR_ERROR_CORRECTION_LEVEL = 'M' as const",
  'const QR_CANVAS_SIZE = 224',
  'const QR_INCLUDE_MARGIN = true',
  'data-phase70-qr-parity="frontend-config-payload"',
  'data-phase70-qr-lightweight="level-m-margin"',
  'to="/dashboard/subscription"',
]) {
  assertContains(configPage, needle, 'frontend/src/pages/Config.tsx')
}

for (const prohibited of [
  'Device-bound список',
  'Отсканируйте QR-код приложением AmneziaVPN',
  'btn-secondary motion-interactive px-3 py-2',
  'data-phase57-raw-config',
  'config-diagnostics',
]) {
  assertNotContains(configPage, prohibited, 'frontend/src/pages/Config.tsx')
}

for (const needle of [
  "t('personalCabinet')",
  'phase68-shell-logo',
]) {
  assertContains(layout, needle, 'frontend/src/components/Layout.tsx')
}

for (const needle of [
  'data-phase71-calendar-boundary',
  'phase68-calendar-day-start',
  'phase68-calendar-day-end',
  "t('subscriptionDescriptionActive')",
  "t('subscriptionCalendar')",
]) {
  assertContains(subscriptionPanel, needle, 'frontend/src/components/SubscriptionPanel.tsx')
}
assertNotContains(subscriptionPanel, 'Оставшееся время рассчитано backend по серверному времени.', 'frontend/src/components/SubscriptionPanel.tsx')

for (const needle of [
  "t('settingsSubtitle')",
  "t('accountBasics')",
  "t('passwordSecurityHint')",
  "t('passwordTooWeak'",
]) {
  assertContains(settings, needle, 'frontend/src/pages/Settings.tsx')
}
assertContains(settings, 'data-phase72-settings-language="[FrontendUser][phase72][LANGUAGE_SETTINGS_REMOVED]"', 'frontend/src/pages/Settings.tsx')
for (const prohibited of [
  "t('languageSubtitle')",
  "t('language')",
  "t('russian')",
  "t('english')",
  'setLanguage',
  'changeLanguage',
]) {
  assertNotContains(settings, prohibited, 'frontend/src/pages/Settings.tsx')
}

for (const needle of [
  'subscriptionDescriptionActive',
  'personalCabinet',
  'settingsSubtitle',
  'devicesListTitle',
  'deviceSecondaryActions',
  'qrServerUnavailable',
  'Use .conf import in AmneziaVPN',
]) {
  assertContains(i18n, needle, 'frontend/src/i18n/index.ts')
}
assertNotContains(i18n, 'Scan QR code with AmneziaVPN app', 'frontend/src/i18n/index.ts')

for (const needle of [
  'START_BLOCK_PHASE71_DEVICE_CONFIG_MASTER_DETAIL',
  '.phase71-config-master-detail',
  '.phase71-device-row-selected',
  '.phase71-sticky-actions',
  '.phase71-device-menu',
  '.phase71-icon-close',
  '@keyframes matrixCalendarBoundaryPulse',
  '[MatrixMotion][phase71][CALENDAR_BOUNDARY_PULSE_SAFE]',
  '[MatrixMotion][phase71][QR_CLOSE_ICON_SAFE]',
  '[VisibleLogo][phase71][FRAMELESS_USER_LOGO]',
]) {
  assertContains(css, needle, 'frontend/src/index.css')
}

for (const needle of [
  '<step-16>',
  'Device Config Retrieval API and Config Page Master-Detail UX',
  'DEVICE_MASTER_DETAIL_READY',
]) {
  assertContains(phase, needle, 'docs/plans/Phase-71.xml')
}

assertProtectedSurfaceDiffClean()
// END_BLOCK_PHASE71_STATIC_ASSERTIONS

console.log('[M-022][phase71][READ_ONLY_DEVICE_CONFIG_API] ok')
console.log('[M-066][phase71][DEVICE_DOWNLOAD_HEADERS_SAFE] ok')
console.log('[PremiumUserCabinet][phase71][DEVICE_MASTER_DETAIL_READY] ok')
console.log('[PremiumUserCabinet][phase71][SELECTED_DEVICE_EXPORTS_SAFE] ok')
console.log('[PremiumUserCabinet][phase71][DESTRUCTIVE_ACTIONS_SECONDARY] ok')
console.log('[ResponsiveAdaptation][phase71][MOBILE_STICKY_ACTIONS_SAFE] ok')
console.log('[MatrixMotion][phase71][QR_CLOSE_ICON_SAFE] ok')
console.log('[MatrixMotion][phase71][CALENDAR_BOUNDARY_PULSE_SAFE] ok')
console.log('[VisibleLogo][phase71][FRAMELESS_USER_LOGO] ok')
console.log('[Phase71][ProtectedSurfaceGuard][NO_DEPLOY_RUNTIME_DRIFT] ok')
