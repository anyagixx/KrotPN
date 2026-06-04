#!/usr/bin/env node
/*
 * FILE: scripts/phase70-config-qr-parity-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke verification for Phase-70 VPN QR payload parity and compact config page safety
 *   SCOPE: Backend QR helper, frontend QR rendering settings, CLI qrencode payload source, removed raw/diagnostics panels, no secret output, and protected deploy/runtime surfaces
 *   DEPENDS: M-003, M-022, M-066, M-075, M-036, M-009, M-071
 *   LINKS: docs/plans/Phase-70.xml, docs/verification/V-M-003.xml, docs/verification/V-M-075.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository files for deterministic static assertions
 *   assertContains - Fails if required source marker is missing
 *   assertNotContains - Fails if prohibited source marker is present
 *   assertProtectedSurfaceDiffClean - Fails if deploy/install/runtime/admin surfaces drift during Phase-70
 *   main - Runs Phase-70 static smoke assertions and prints aggregate markers only
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-70 config QR parity and compact config page smoke gate.
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
    throw new Error(`${label} is missing required Phase-70 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-70 marker: ${needle}`)
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
      throw new Error(`Protected Phase-70 surface missing from repository: ${protectedPath}`)
    }
  }

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (diff) {
    throw new Error(`Phase-70 must not change deploy/install/runtime/admin surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE70_STATIC_ASSERTIONS
const router = read('backend/app/vpn/router.py')
const routerTests = read('backend/tests/test_vpn_router_compat.py')
const configPage = read('frontend/src/pages/Config.tsx')
const api = read('frontend/src/lib/api.ts')
const createClient = read('deploy/create-client.sh')

for (const [label, source] of [
  ['backend/app/vpn/router.py', router],
  ['backend/tests/test_vpn_router_compat.py', routerTests],
  ['frontend/src/pages/Config.tsx', configPage],
  ['frontend/src/lib/api.ts', api],
]) {
  assertContains(source, 'MODULE_CONTRACT', label)
  assertContains(source, 'MODULE_MAP', label)
  assertContains(source, 'CHANGE_SUMMARY', label)
}

for (const needle of [
  'CONFIG_QR_ERROR_CORRECTION_LABEL = "M"',
  'CONFIG_QR_ERROR_CORRECTION = qrcode.constants.ERROR_CORRECT_M',
  'CONFIG_QR_BOX_SIZE = 8',
  'CONFIG_QR_BORDER = 4',
  'def build_config_qr_png(',
  'error_correction=CONFIG_QR_ERROR_CORRECTION',
  '[M-003][build_config_qr_png][QR_PAYLOAD_RENDERED]',
  'build_config_qr_png(config.config, route_label="config")',
  'build_config_qr_png(json.dumps(amnezia_config), route_label="config_amnezia")',
]) {
  assertContains(router, needle, 'backend/app/vpn/router.py')
}
assertNotContains(router, 'ERROR_CORRECT_H', 'backend/app/vpn/router.py')
assertNotContains(router, 'box_size=15', 'backend/app/vpn/router.py')

for (const needle of [
  'test_config_json_download_and_qr_payloads_stay_in_parity',
  'test_amnezia_qr_wraps_exact_config_payload_without_changing_config_text',
  'test_config_qr_builder_uses_lighter_settings_without_payload_change',
  'assert config_response.json()["config"] == expected_payload',
  'assert download_response.content == expected_payload.encode("utf-8")',
  'assert SpyQRCode.instances[-1].payload == expected_payload',
  'assert payload["containers"][0]["config_data"] == StubConfigVPNService.config_text',
]) {
  assertContains(routerTests, needle, 'backend/tests/test_vpn_router_compat.py')
}

for (const needle of [
  "const QR_ERROR_CORRECTION_LEVEL = 'M' as const",
  'const QR_CANVAS_SIZE = 224',
  'const QR_INCLUDE_MARGIN = true',
  'data-phase70-qr-parity="frontend-config-payload"',
  'data-phase70-qr-lightweight="level-m-margin"',
  'level={QR_ERROR_CORRECTION_LEVEL}',
  'includeMargin={QR_INCLUDE_MARGIN}',
  'CONFIG_DOWNLOAD_MIME_TYPE',
  'buildConfigDownloadBlob',
  'buildConfigDownloadFilename',
  'data-phase57-config-actions="qr-download-copy"',
  'data-phase57-device-list="scroll-safe"',
]) {
  assertContains(configPage, needle, 'frontend/src/pages/Config.tsx')
}

for (const prohibited of [
  'level="H"',
  'includeMargin={false}',
  'data-phase57-raw-config="collapsed"',
  'data-phase62-collapse="config-diagnostics"',
  'config-diagnostics',
  'data-phase57-raw-config',
]) {
  assertNotContains(configPage, prohibited, 'frontend/src/pages/Config.tsx')
}

assertContains(api, "CONFIG_DOWNLOAD_MIME_TYPE = 'application/octet-stream'", 'frontend/src/lib/api.ts')
assertContains(api, "api.get('/vpn/config/download'", 'frontend/src/lib/api.ts')
assertContains(api, "api.get('/vpn/config/qr'", 'frontend/src/lib/api.ts')
assertContains(createClient, 'qrencode -t ansiutf8 < "$OUTPUT_PATH"', 'deploy/create-client.sh')
assertContains(createClient, 'qrencode -o "$PNG_PATH" < "$OUTPUT_PATH"', 'deploy/create-client.sh')

assertProtectedSurfaceDiffClean()
// END_BLOCK_PHASE70_STATIC_ASSERTIONS

console.log('[Phase70][ConfigQR][PAYLOAD_PARITY_CONTRACT] ok')
console.log('[Phase70][ConfigQR][LIGHTER_RENDER_SETTINGS] ok')
console.log('[Phase70][ConfigPage][COMPACT_WORKFLOW_PRESERVED] ok')
console.log('[Phase70][ProtectedSurfaceGuard][NO_DEPLOY_RUNTIME_DRIFT] ok')
