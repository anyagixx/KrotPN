#!/usr/bin/env node
/*
 * FILE: scripts/phase80-manual-mtproto-proxy-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke verification for Phase-80 Manual External MTProto Proxy Pool
 *   SCOPE: Backend models/service/API, owner response source fields, admin UI controls,
 *          frontend owner telemetry copy, backend tests, migration, redaction, and protected deploy/runtime guard
 *   DEPENDS: M-045, M-047, M-082
 *   LINKS: V-M-082, docs/plans/Phase-80.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository text files for deterministic assertions
 *   assertContains - Fails if a required Phase-80 marker is missing
 *   assertAbsent - Fails if a forbidden admin marker appears
 *   assertProtectedRuntimeDiffClean - Fails if Phase-80 touches deploy/runtime topology
 *   main - Runs Phase-80 static smoke and prints evidence markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-80 manual external MTProto proxy pool smoke.
 * END_CHANGE_SUMMARY
 */

import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const root = process.cwd()

// START_BLOCK_PHASE80_SMOKE_HELPERS
function read(relativePath) {
  return readFileSync(join(root, relativePath), 'utf8')
}

function assertContains(source, needle, label) {
  if (!source.includes(needle)) {
    throw new Error(`${label} is missing required Phase-80 marker: ${needle}`)
  }
}

function assertAbsent(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains forbidden Phase-80 marker: ${needle}`)
  }
}

function assertProtectedRuntimeDiffClean() {
  const protectedPaths = [
    'install.sh',
    'docker-compose.yml',
    'deploy',
    'nginx',
    'mtproto-runtime',
    'official-mtproxy',
    'telegram-bot',
  ]

  for (const protectedPath of protectedPaths) {
    if (!existsSync(join(root, protectedPath))) {
      throw new Error(`Protected Phase-80 surface missing: ${protectedPath}`)
    }
  }

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (diff) {
    throw new Error(`Phase-80 must not change deploy/install/runtime topology: ${diff}`)
  }
}
// END_BLOCK_PHASE80_SMOKE_HELPERS

// START_BLOCK_PHASE80_STATIC_ASSERTIONS
const modelPath = 'backend/app/mtproto/models.py'
const servicePath = 'backend/app/mtproto/manual_pool.py'
const ownerRouterPath = 'backend/app/mtproto/router.py'
const schemasPath = 'backend/app/mtproto/schemas.py'
const adminRouterPath = 'backend/app/admin/router.py'
const userApiPath = 'frontend/src/lib/api.ts'
const dashboardPath = 'frontend/src/pages/Dashboard.tsx'
const adminApiPath = 'frontend-admin/src/lib/api.ts'
const adminTypesPath = 'frontend-admin/src/types/index.ts'
const adminPagePath = 'frontend-admin/src/pages/MTProto.tsx'
const testPath = 'backend/tests/test_mtproto_manual_proxy_pool.py'
const migrationPath = 'backend/alembic/versions/phase80_manual_external_mtproto_proxy_pool.py'

const model = read(modelPath)
const service = read(servicePath)
const ownerRouter = read(ownerRouterPath)
const schemas = read(schemasPath)
const adminRouter = read(adminRouterPath)
const userApi = read(userApiPath)
const dashboard = read(dashboardPath)
const adminApi = read(adminApiPath)
const adminTypes = read(adminTypesPath)
const adminPage = read(adminPagePath)
const test = read(testPath)
const migration = read(migrationPath)

for (const [label, source] of [
  [modelPath, model],
  [servicePath, service],
  [ownerRouterPath, ownerRouter],
  [schemasPath, schemas],
  [adminRouterPath, adminRouter],
  [userApiPath, userApi],
  [dashboardPath, dashboard],
  [adminApiPath, adminApi],
  [adminTypesPath, adminTypes],
  [adminPagePath, adminPage],
  [testPath, test],
  [migrationPath, migration],
]) {
  assertContains(source, 'START_MODULE_CONTRACT', label)
}

for (const marker of [
  'class MTProtoManualExternalProxy(SQLModel, table=True)',
  'class MTProtoDeliverySettings(SQLModel, table=True)',
  'MTProtoDeliveryMode',
]) {
  assertContains(model, marker, modelPath)
}

for (const marker of [
  'class MTProtoManualProxyPoolService',
  'encrypt_data(normalized_secret)',
  'decrypt_data(active_proxy.secret_enc)',
  '[M-082][manual_proxy_delivery][AUTOMATIC_PASSTHROUGH]',
  '[M-082][manual_proxy_delivery][OWNER_MANUAL_RESPONSE]',
  'telemetry_available=False',
]) {
  assertContains(service, marker, servicePath)
}

assertContains(ownerRouter, 'build_mtproto_manual_proxy_pool', ownerRouterPath)
assertContains(ownerRouter, '[M-082][get_my_mtproto_proxy][DELIVERY_MODE]', ownerRouterPath)
assertContains(schemas, 'class MTProtoProxySource', schemasPath)
assertContains(schemas, 'browser_link', schemasPath)
assertContains(schemas, 'telemetry_available', schemasPath)

for (const marker of [
  '@router.get("/mtproto/manual-proxies")',
  '@router.post("/mtproto/manual-proxies")',
  '@router.patch("/mtproto/manual-proxies/{proxy_id}")',
  '@router.post("/mtproto/manual-proxies/{proxy_id}/activate")',
  '@router.post("/mtproto/manual-proxies/{proxy_id}/disable")',
  '@router.get("/mtproto/delivery-mode")',
  '@router.put("/mtproto/delivery-mode")',
  '_safe_mtproto_manual_proxy_audit_details',
]) {
  assertContains(adminRouter, marker, adminRouterPath)
}

for (const marker of [
  "source: 'krotpn_auto' | 'manual_external'",
  'telemetry_available: boolean',
  'manual_proxy_name: string | null',
]) {
  assertContains(userApi, marker, userApiPath)
}
assertContains(dashboard, 'data-phase80-manual-external-copy', dashboardPath)
assertContains(dashboard, 'Статистика, health и promo tag state по нему на стороне KrotPN недоступны', dashboardPath)

for (const marker of [
  'AdminMTProtoManualProxy',
  'AdminMTProtoDeliveryModeState',
  'getMTProtoManualProxies',
  'createMTProtoManualProxy',
  'updateMTProtoDeliveryMode',
  'data-phase80-manual-mtproto-pool',
  'data-phase80-redaction',
  'Manual external delivery',
]) {
  assertContains(`${adminTypes}\n${adminApi}\n${adminPage}`, marker, 'frontend-admin Phase-80 surface')
}

for (const marker of [
  'test_automatic_mode_preserves_existing_provisioning_path',
  'test_admin_manual_proxy_create_encrypts_secret_and_redacts_responses',
  'test_manual_mode_owner_response_uses_external_proxy_without_assignment',
  'test_manual_mode_missing_active_proxy_returns_pending_without_secret',
]) {
  assertContains(test, marker, testPath)
}
assertContains(migration, 'mtproto_manual_external_proxies', migrationPath)
assertContains(migration, 'mtproto_delivery_settings', migrationPath)

assertAbsent(adminPage, 'tg://proxy?', adminPagePath)
assertAbsent(adminPage, 'https://t.me/proxy?', adminPagePath)
assertAbsent(adminPage, 'secret=', adminPagePath)
assertProtectedRuntimeDiffClean()
// END_BLOCK_PHASE80_STATIC_ASSERTIONS

console.log('[M-082][phase80][MANUAL_EXTERNAL_POOL] ok')
console.log('[M-082][phase80][DELIVERY_MODE_SELECTOR] ok')
console.log('[M-082][phase80][OWNER_SOURCE_FIELDS] ok')
console.log('[M-082][phase80][ADMIN_REDACTION_GUARD] ok')
console.log('[M-082][phase80][PROTECTED_RUNTIME_UNCHANGED] ok')
