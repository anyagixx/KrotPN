#!/usr/bin/env node
/*
 * FILE: scripts/phase78-vpn-device-abuse-alerts-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke verification for Phase-78 VPN Device Abuse Alert Inbox
 *   SCOPE: Backend model/service/API routes, admin UI inbox/archive/actions, confirmation guards, redaction markers, and protected deploy/user frontend surfaces
 *   DEPENDS: M-006, M-024, M-025, M-031, M-076, M-081
 *   LINKS: V-M-081, docs/plans/Phase-78.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository text files for deterministic assertions
 *   assertContains - Fails if a required Phase-78 marker is missing
 *   assertNotContains - Fails if a forbidden secret marker appears in admin UI/API payload code
 *   assertProtectedDiffClean - Fails if Phase-78 touches deploy/runtime/user frontend surfaces
 *   main - Runs Phase-78 static smoke and prints evidence markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-78 VPN device abuse alert inbox verification smoke.
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
    throw new Error(`${label} is missing required Phase-78 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains forbidden Phase-78 marker: ${needle}`)
  }
}

function assertProtectedDiffClean() {
  const protectedPaths = [
    'install.sh',
    'docker-compose.yml',
    'deploy',
    'nginx',
    'frontend/src',
    'telegram-bot',
    'mtproto-runtime',
    'official-mtproxy',
  ]
  for (const protectedPath of protectedPaths) {
    if (!existsSync(join(root, protectedPath))) {
      throw new Error(`Protected Phase-78 surface missing from repository: ${protectedPath}`)
    }
  }

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (diff) {
    throw new Error(`Phase-78 must not change deploy/runtime/user frontend surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE78_STATIC_ASSERTIONS
const servicePath = 'backend/app/vpn/abuse_alerts.py'
const monitorPath = 'backend/app/vpn/handshake_monitor.py'
const adminRouterPath = 'backend/app/admin/router.py'
const apiPath = 'frontend-admin/src/lib/api.ts'
const typesPath = 'frontend-admin/src/types/index.ts'
const usersPath = 'frontend-admin/src/pages/Users.tsx'
const migrationPath = 'backend/alembic/versions/phase78_vpn_device_abuse_alerts.py'
const backendTestPath = 'backend/tests/test_vpn_device_abuse_alerts.py'

const service = read(servicePath)
const monitor = read(monitorPath)
const adminRouter = read(adminRouterPath)
const api = read(apiPath)
const types = read(typesPath)
const users = read(usersPath)
const migration = read(migrationPath)
const backendTest = read(backendTestPath)

for (const [label, source] of [
  [servicePath, service],
  [monitorPath, monitor],
  [adminRouterPath, adminRouter],
  [apiPath, api],
  [typesPath, types],
  [usersPath, users],
  [migrationPath, migration],
  [backendTestPath, backendTest],
]) {
  assertContains(source, 'START_MODULE_CONTRACT', label)
  assertContains(source, 'Phase-78', label)
}

assertContains(service, 'class VPNDeviceAbuseAlert(SQLModel, table=True)', servicePath)
assertContains(service, 'create_device_abuse_alert', servicePath)
assertContains(service, 'list_device_abuse_alerts', servicePath)
assertContains(service, 'resolve_device_abuse_alert', servicePath)
assertContains(service, 'rotate_device_for_alert', servicePath)
assertContains(service, 'block_device_for_alert', servicePath)
assertContains(service, '[M-081][create_device_abuse_alert][ALERT_CREATED]', servicePath)
assertContains(service, '[M-081][create_device_abuse_alert][ALERT_DEDUPED]', servicePath)
assertContains(service, '[M-081][list_device_abuse_alerts][ALERT_LIST]', servicePath)
assertContains(service, '[M-081][get_device_abuse_alert][ALERT_DETAIL]', servicePath)
assertContains(service, '[M-081][resolve_device_abuse_alert][ALERT_RESOLVED]', servicePath)
assertContains(service, '[M-081][rotate_device_for_alert][CONFIRM_ROTATE_DEVICE]', servicePath)
assertContains(service, '[M-081][block_device_for_alert][CONFIRM_BLOCK_DEVICE]', servicePath)
assertContains(service, '[M-081][vpn_device_abuse_alert][REDACTION_GUARD]', servicePath)

assertContains(monitor, 'create_device_abuse_alert(self.session, event)', monitorPath)
assertContains(adminRouter, '@router.get("/vpn/abuse/alerts")', adminRouterPath)
assertContains(adminRouter, '@router.get("/vpn/abuse/alerts/{alert_id}")', adminRouterPath)
assertContains(adminRouter, '@router.post("/vpn/abuse/alerts/{alert_id}/resolve")', adminRouterPath)
assertContains(adminRouter, '@router.post("/vpn/abuse/alerts/{alert_id}/rotate-device")', adminRouterPath)
assertContains(adminRouter, '@router.post("/vpn/abuse/alerts/{alert_id}/block-device")', adminRouterPath)
assertContains(adminRouter, 'VPNDeviceAbuseAlertActionRequest', adminRouterPath)
assertContains(adminRouter, '_safe_vpn_device_abuse_alert_audit_details', adminRouterPath)

assertContains(api, 'getVPNDeviceAbuseAlerts', apiPath)
assertContains(api, 'getVPNDeviceAbuseAlert', apiPath)
assertContains(api, 'resolveVPNDeviceAbuseAlert', apiPath)
assertContains(api, 'rotateVPNDeviceAbuseAlert', apiPath)
assertContains(api, 'blockVPNDeviceAbuseAlert', apiPath)
assertContains(types, 'export interface AdminVPNDeviceAbuseAlert', typesPath)
assertContains(types, 'export interface AdminVPNDeviceAbuseAlertListResponse', typesPath)
assertContains(users, 'data-phase78-vpn-abuse="[FrontendAdmin][phase78][VPN_DEVICE_ABUSE_ALERT_INBOX]"', usersPath)
assertContains(users, 'data-phase78-alert-detail="[M-081][ALERT_DETAIL_DRAWER]"', usersPath)
assertContains(users, 'data-phase78-confirmation="[DeviceAdminControl][phase78][VPN_ALERT_CONFIRMATION_GUARDS]"', usersPath)
assertContains(users, 'data-phase78-alert-action-scope="[DeviceAdminControl][phase78][ONE_DEVICE_ONLY]"', usersPath)
assertContains(users, 'vpnAbuseOpenCount', usersPath)
assertContains(users, 'vpnAbuseArchivedAlerts', usersPath)
assertContains(users, 'runConfirmedVPNAlertAction', usersPath)

assertContains(migration, 'vpn_device_abuse_alerts', migrationPath)
assertContains(migration, 'phase78_vpn_device_abuse_alerts', migrationPath)
assertContains(backendTest, 'test_confirmed_abuse_event_creates_and_dedupes_open_alert', backendTestPath)
assertContains(backendTest, 'test_rotate_and_block_alert_actions_require_confirmation_and_target_one_device', backendTestPath)

const redactedSources = [
  [adminRouterPath, adminRouter],
  [usersPath, users],
]
for (const [label, source] of redactedSources) {
  assertNotContains(source, 'private_key_enc"', label)
  assertNotContains(source, 'preshared_key_enc"', label)
  assertNotContains(source, '[Interface]\\n', label)
}

assertProtectedDiffClean()
// END_BLOCK_PHASE78_STATIC_ASSERTIONS

console.log('[M-081][phase78][VPN_DEVICE_ABUSE_ALERT_INBOX] ok')
console.log('[M-081][phase78][VPN_DEVICE_ABUSE_ALERT_ARCHIVE] ok')
console.log('[M-081][phase78][ONE_DEVICE_ALERT_ACTIONS] ok')
console.log('[M-081][phase78][CONFIRMATION_GUARDS] ok')
console.log('[M-081][phase78][REDACTION_GUARD] ok')
console.log('[M-081][phase78][PROTECTED_SURFACES_UNCHANGED] ok')
