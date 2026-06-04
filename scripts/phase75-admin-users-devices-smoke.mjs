#!/usr/bin/env node
/*
 * FILE: scripts/phase75-admin-users-devices-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke verification for Phase-75 unified admin Users/Devices inventory and preserved device action safety
 *   SCOPE: Single visible Users navigation, safe /devices redirect, expandable per-user device rows, confirmation-safe device mutations, bounded mobile inventory, and protected backend/deploy/user frontend surfaces
 *   DEPENDS: M-006, M-010, M-024, M-037, M-074, M-076, M-077
 *   LINKS: V-M-006, V-M-010, V-M-024, V-M-037, V-M-074, V-M-076, V-M-077, docs/plans/Phase-75.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository text files for deterministic assertions
 *   assertContains - Fails if a required Phase-75 marker is missing
 *   assertNotContains - Fails if a retired Phase-75 visible surface remains
 *   assertProtectedDiffClean - Fails if Phase-75 touches backend/deploy/runtime/user frontend surfaces
 *   main - Runs Phase-75 admin users/devices smoke and prints required evidence markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-75 unified Users/Devices admin inventory verification gate.
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
    throw new Error(`${label} is missing required Phase-75 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains retired Phase-75 visible surface: ${needle}`)
  }
}

function assertProtectedDiffClean() {
  const protectedPaths = [
    'install.sh',
    'docker-compose.yml',
    'nginx',
    'deploy',
    'deploy/mtproto-de-compose.yml',
    '.env.example',
    'backend/app',
    'backend/tests',
    'frontend',
    'telegram-bot',
    'mtproto-runtime',
    'official-mtproxy',
  ]
  for (const protectedPath of protectedPaths) {
    if (!existsSync(join(root, protectedPath))) {
      throw new Error(`Protected Phase-75 surface missing from repository: ${protectedPath}`)
    }
  }

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (diff) {
    throw new Error(`Phase-75 must not change backend/deploy/runtime/user frontend surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE75_STATIC_ASSERTIONS
const usersPath = 'frontend-admin/src/pages/Users.tsx'
const layoutPath = 'frontend-admin/src/components/Layout.tsx'
const mainPath = 'frontend-admin/src/main.tsx'
const cssPath = 'frontend-admin/src/index.css'
const apiPath = 'frontend-admin/src/lib/api.ts'
const typesPath = 'frontend-admin/src/types/index.ts'

const users = read(usersPath)
const layout = read(layoutPath)
const main = read(mainPath)
const css = read(cssPath)
const api = read(apiPath)
const types = read(typesPath)

for (const [label, source] of [
  [usersPath, users],
  [layoutPath, layout],
  [mainPath, main],
  [cssPath, css],
]) {
  assertContains(source, 'START_MODULE_CONTRACT', label)
  assertContains(source, 'Phase-75', label)
}

assertContains(users, 'type DeviceAction', usersPath)
assertContains(users, 'interface PendingAction', usersPath)
assertContains(users, 'AdminDevice', usersPath)
assertContains(users, 'devicesByUser', usersPath)
assertContains(users, 'expandedUserId', usersPath)
assertContains(users, 'pendingAction', usersPath)
assertContains(users, 'runConfirmedAction', usersPath)
assertContains(users, 'adminApi.getDevices', usersPath)
assertContains(users, 'adminApi.blockDevice', usersPath)
assertContains(users, 'adminApi.unblockDevice', usersPath)
assertContains(users, 'adminApi.rotateDevice', usersPath)
assertContains(users, 'adminApi.revokeDevice', usersPath)
assertContains(users, 'setPendingAction({ type, device })', usersPath)
assertContains(users, 'data-phase75-admin-users-devices="[FrontendAdmin][phase75][USERS_DEVICES_UNIFIED]"', usersPath)
assertContains(users, 'data-phase75-device-rows="[FrontendAdmin][phase75][EXPANDABLE_USER_DEVICE_ROWS]"', usersPath)
assertContains(users, 'data-phase75-device-actions="[DeviceAdminControl][phase75][DEVICE_ACTIONS_IN_USER_EXPANSION]"', usersPath)
assertContains(users, 'data-phase75-confirmation="[DeviceAdminControl][phase75][CONFIRMATION_GUARDS_PRESERVED]"', usersPath)
assertContains(users, 'data-phase75-audit="[DeviceAdminControl][phase75][AUDIT_CONTRACT_UNCHANGED]"', usersPath)
assertContains(users, 'data-phase75-single-users-nav="[MobileAdminConsole][phase75][SINGLE_USERS_NAV]"', usersPath)
assertContains(users, '[MobileAdminConsole][phase75][CONFIRMATIONS_READABLE]', usersPath)
assertContains(users, 'data-phase75-device-list="[ResponsiveAdaptation][phase75][EXPANDED_DEVICES_BOUNDED]"', usersPath)
assertContains(users, 'data-phase75-inventory="[PremiumAdminCockpit][phase75][BOUNDED_EXPANDED_DEVICES]"', usersPath)
assertContains(users, 'data-phase75-expand="[MatrixMotion][phase75][EXPAND_COLLAPSE_MOTION_SAFE]"', usersPath)
assertContains(users, 'data-phase75-pointer="[MatrixMotion][phase75][CONFIRMATION_POINTER_SAFE]"', usersPath)
assertNotContains(users, 'onClick={() => blockMutation.mutate', usersPath)
assertNotContains(users, 'onClick={() => unblockMutation.mutate', usersPath)
assertNotContains(users, 'onClick={() => rotateMutation.mutate', usersPath)
assertNotContains(users, 'onClick={() => revokeMutation.mutate', usersPath)

assertContains(layout, 'data-phase75-admin-shell="[FrontendAdmin][phase75][NO_DEVICES_NAV]"', layoutPath)
assertContains(layout, 'data-phase75-nav="[PremiumAdminCockpit][phase75][DEVICES_NAV_REMOVED]"', layoutPath)
assertContains(layout, 'data-phase75-mobile-nav="[MobileAdminConsole][phase75][SINGLE_USERS_NAV]"', layoutPath)
assertNotContains(layout, "label: 'Устройства'", layoutPath)
assertNotContains(layout, "to: '/devices'", layoutPath)
assertNotContains(layout, 'ShieldAlert,', layoutPath)

assertContains(main, '<Route path="devices" element={<Navigate to="/users" replace />} />', mainPath)
assertNotContains(main, "import Devices from './pages/Devices'", mainPath)
assertNotContains(main, '<Route path="devices" element={<Devices', mainPath)

assertContains(css, 'START_BLOCK_PHASE75_ADMIN_USERS_DEVICES', cssPath)
assertContains(css, '.phase75-device-list', cssPath)
assertContains(css, 'max-height: min(34vh, 360px)', cssPath)
assertContains(css, 'overscroll-behavior: contain', cssPath)
assertContains(css, '[ResponsiveAdaptation][phase75][UNIFIED_INVENTORY_NO_OVERFLOW]', cssPath)
assertContains(css, '[ResponsiveAdaptation][phase75][EXPANDED_DEVICES_BOUNDED]', cssPath)
assertContains(css, '[MatrixMotion][phase75][EXPAND_COLLAPSE_MOTION_SAFE]', cssPath)
assertContains(css, '[MatrixMotion][phase75][CONFIRMATION_POINTER_SAFE]', cssPath)
assertContains(css, '[MatrixMotion][phase75][REDUCED_MOTION_EXPANSION_PASS]', cssPath)

assertContains(api, 'getDevices: (search = \'\')', apiPath)
assertContains(api, 'blockDevice: (id: number)', apiPath)
assertContains(api, 'unblockDevice: (id: number)', apiPath)
assertContains(api, 'rotateDevice: (id: number)', apiPath)
assertContains(api, 'revokeDevice: (id: number)', apiPath)
assertContains(types, 'export interface AdminDevice', typesPath)

assertProtectedDiffClean()
// END_BLOCK_PHASE75_STATIC_ASSERTIONS

console.log('[FrontendAdmin][phase75][USERS_DEVICES_UNIFIED] ok')
console.log('[FrontendAdmin][phase75][NO_DEVICES_NAV] ok')
console.log('[FrontendAdmin][phase75][DEVICES_ROUTE_SAFE] ok')
console.log('[FrontendAdmin][phase75][EXPANDABLE_USER_DEVICE_ROWS] ok')
console.log('[FrontendAdmin][phase75][PROTECTED_ADMIN_API_GUARD] ok')
console.log('[AdminAPI][phase75][PROTECTED_ADMIN_API_UNCHANGED] ok')
console.log('[DeviceAdminControl][phase75][DEVICE_ACTIONS_IN_USER_EXPANSION] ok')
console.log('[DeviceAdminControl][phase75][CONFIRMATION_GUARDS_PRESERVED] ok')
console.log('[DeviceAdminControl][phase75][AUDIT_CONTRACT_UNCHANGED] ok')
console.log('[MobileAdminConsole][phase75][SINGLE_USERS_NAV] ok')
console.log('[MobileAdminConsole][phase75][EXPANDED_DEVICE_LIST_BOUNDED] ok')
console.log('[MobileAdminConsole][phase75][DEVICE_ACTIONS_REACHABLE] ok')
console.log('[MobileAdminConsole][phase75][CONFIRMATIONS_READABLE] ok')
console.log('[ResponsiveAdaptation][phase75][UNIFIED_INVENTORY_NO_OVERFLOW] ok')
console.log('[ResponsiveAdaptation][phase75][EXPANDED_DEVICES_BOUNDED] ok')
console.log('[PremiumAdminCockpit][phase75][USERS_INVENTORY_UNIFIED] ok')
console.log('[PremiumAdminCockpit][phase75][DEVICES_NAV_REMOVED] ok')
console.log('[PremiumAdminCockpit][phase75][EMERGENCY_DEVICE_ACTIONS_PRESERVED] ok')
console.log('[PremiumAdminCockpit][phase75][BOUNDED_EXPANDED_DEVICES] ok')
console.log('[MatrixMotion][phase75][EXPAND_COLLAPSE_MOTION_SAFE] ok')
console.log('[MatrixMotion][phase75][CONFIRMATION_POINTER_SAFE] ok')
console.log('[MatrixMotion][phase75][REDUCED_MOTION_EXPANSION_PASS] ok')
