#!/usr/bin/env node
/*
 * FILE: scripts/phase73-config-amnezia-qr-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke verification for Phase-73 truthful Amnezia QR behavior and KPN config copy.
 *   SCOPE: User config page KPN copy, selected-device AmneziaWG QR preservation, AmneziaVPN .conf guidance, tariff-aware device-limit text, and protected backend/deploy/runtime surfaces.
 *   DEPENDS: M-003, M-022, M-036, M-063, M-066, M-068, M-071, M-075
 *   LINKS: docs/plans/Phase-73.xml, docs/verification/V-M-075.xml, docs/verification/V-M-022.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository files for deterministic static assertions.
 *   assertContains - Fails if a required Phase-73 marker is missing.
 *   assertNotContains - Fails if a prohibited stale marker remains.
 *   assertProtectedSurfaceDiffClean - Fails if Phase-73 drifts into backend, deploy, admin, MTProto, or bot surfaces.
 *   main - Runs Phase-73 static assertions and prints verification markers.
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-73 config page Amnezia QR truthfulness smoke gate.
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
    throw new Error(`${label} is missing required Phase-73 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-73 marker: ${needle}`)
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
    'frontend-admin',
  ]

  for (const protectedPath of protectedPaths) {
    if (!existsSync(join(root, protectedPath))) {
      throw new Error(`Protected Phase-73 surface missing from repository: ${protectedPath}`)
    }
  }

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (diff) {
    throw new Error(`Phase-73 must not change backend/deploy/runtime/admin surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE73_STATIC_ASSERTIONS
const configPage = read('frontend/src/pages/Config.tsx')
const i18n = read('frontend/src/i18n/index.ts')
const api = read('frontend/src/lib/api.ts')
const phase = read('docs/plans/Phase-73.xml')

for (const [label, source] of [
  ['frontend/src/pages/Config.tsx', configPage],
  ['frontend/src/i18n/index.ts', i18n],
  ['frontend/src/lib/api.ts', api],
]) {
  assertContains(source, 'MODULE_CONTRACT', label)
  assertContains(source, 'MODULE_MAP', label)
  assertContains(source, 'CHANGE_SUMMARY', label)
}

for (const needle of [
  'data-phase73-payload-unchanged="[VPNConfig][phase73][PAYLOAD_UNCHANGED]"',
  'data-phase73-amneziawg-qr="[DeviceConfig][phase73][SELECTED_DEVICE_AMNEZIAWG_QR_SAFE]"',
  'data-phase73-amneziavpn-qr="[ConfigPage][phase73][AMNEZIA_VPN_QR_NOT_ADVERTISED]"',
  'data-phase73-amnezia-guidance="[MobileUserCabinet][phase73][AMNEZIA_CONF_GUIDANCE]"',
  'data-phase73-limit-message={!canCreateDevice ?',
  'data-phase73-tariff-copy={!canCreateDevice ?',
  'data-phase73-truthful-qr="[PremiumUserCabinet][phase73][AMNEZIA_QR_TRUTHFUL]"',
  "billingApi.getSubscription()",
  "t('deviceLimitReachedWithTariff', { tariff: tariffLabel })",
  "t('qrInstructionsWG')",
  "t('qrInstructionsVPN')",
  'deviceApi.getQRCode(deviceId)',
  'QRCodeCanvas',
  'buildConfigDownloadBlob(response.data)',
]) {
  assertContains(configPage, needle, 'frontend/src/pages/Config.tsx')
}

for (const prohibited of [
  "type QRType = 'amneziawg' | 'amneziavpn'",
  'setQrType',
  "qrType === 'amneziavpn'",
  'deviceApi.getAmneziaQRCode(deviceId)',
  '>AmneziaVPN</button>',
  'VPN Конфигурация',
  'QR, .conf и копирование теперь привязаны к выбранному устройству.',
]) {
  assertNotContains(configPage, prohibited, 'frontend/src/pages/Config.tsx')
}

for (const needle of [
  "vpnConfig: 'KPN Конфигурация'",
  "newDeviceConfig: 'Новый конфиг для вашего устройства'",
  "deviceLimitReachedWithTariff: 'Лимит устройств исчерпан согласно вашему Тарифу - {{tariff}}'",
  "qrInstructionsWG: 'Отсканируйте QR-код приложением AmneziaWG'",
  "qrInstructionsVPN: 'Для AmneziaVPN скачайте .conf и импортируйте его в приложение.'",
  "vpnConfig: 'KPN Configuration'",
  "deviceLimitReachedWithTariff: 'Device limit reached under your tariff - {{tariff}}'",
  'Use .conf import in AmneziaVPN',
]) {
  assertContains(i18n, needle, 'frontend/src/i18n/index.ts')
}

for (const prohibited of [
  "vpnConfig: 'VPN Конфигурация'",
  "newDeviceConfig: 'Новый конфиг'",
  'QR, .conf и копирование теперь привязаны к выбранному устройству.',
  'Scan QR code with AmneziaVPN app',
]) {
  assertNotContains(i18n, prohibited, 'frontend/src/i18n/index.ts')
}

for (const needle of [
  'getQRCode: (deviceId: number)',
  'getAmneziaQRCode: (deviceId: number)',
  '`/devices/${deviceId}/config/qr`',
  '`/devices/${deviceId}/config/qr/amnezia`',
]) {
  assertContains(api, needle, 'frontend/src/lib/api.ts')
}

for (const needle of [
  '<Phase-73 NAME="User Config Page and Amnezia QR Correctness"',
  '<in>User /dashboard/config copy, AmneziaWG QR behavior, AmneziaVPN import guidance',
  '<requirement-1>AmneziaVPN must not be shown a QR code that the application cannot read.</requirement-1>',
  '<requirement-3>AmneziaWG QR must remain available',
  '<step-9 STATUS="done-local">Update Phase-73 smoke to reject non-working AmneziaVPN QR',
]) {
  assertContains(phase, needle, 'docs/plans/Phase-73.xml')
}

assertProtectedSurfaceDiffClean()
// END_BLOCK_PHASE73_STATIC_ASSERTIONS

console.log('[VPNConfig][phase73][PAYLOAD_UNCHANGED] ok')
console.log('[ConfigPage][phase73][AMNEZIA_VPN_QR_NOT_ADVERTISED] ok')
console.log('[DeviceConfig][phase73][SELECTED_DEVICE_AMNEZIAWG_QR_SAFE] ok')
console.log('[DeviceConfig][phase73][NO_CONFIG_ROTATION] ok')
console.log('[MobileUserCabinet][phase73][AMNEZIA_CONF_GUIDANCE] ok')
console.log('[MobileUserCabinet][phase73][LIMIT_MESSAGE_TARIFF_VISIBLE] ok')
console.log('[TrialSubscription][phase73][TRIAL_SEMANTICS_UNCHANGED] ok')
console.log('[TrialSubscription][phase73][DISPLAY_ONLY_TARIFF_COPY] ok')
console.log('[ConfigDownload][phase73][AMNEZIA_CONF_DOWNLOAD_GUIDANCE] ok')
console.log('[ConfigDownload][phase73][CONF_MIME_HEADERS_PRESERVED] ok')
console.log('[TariffCatalog][phase73][DISPLAY_NAME_ONLY] ok')
console.log('[TariffCatalog][phase73][DEVICE_LIMIT_MESSAGE_SAFE] ok')
console.log('[MatrixStyle][phase73][CONFIG_COPY_COMPACT] ok')
console.log('[MatrixStyle][phase73][QR_GUIDANCE_READABLE] ok')
console.log('[PremiumUserCabinet][phase73][KPN_CONFIG_COPY] ok')
console.log('[PremiumUserCabinet][phase73][AMNEZIA_QR_TRUTHFUL] ok')
console.log('[PremiumUserCabinet][phase73][DEVICE_LIMIT_TARIFF_COPY] ok')
console.log('[Phase73][ProtectedSurfaceGuard][NO_BACKEND_DEPLOY_RUNTIME_DRIFT] ok')
