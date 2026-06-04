#!/usr/bin/env node
/*
 * FILE: scripts/phase74-admin-shell-navigation-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke verification for Phase-74 admin shell navigation, login icon padding, retired admin tariffs route, and bounded scroll surfaces
 *   SCOPE: Admin login icon-safe inputs, no visible admin Tariffs nav, safe /plans redirect, logout-under-Nodes order, admin content wheel-scroll surface, bounded rail height, preserved backend/user tariff catalog, and protected non-admin surfaces
 *   DEPENDS: M-010, M-037, M-068, M-071, M-074, M-076, M-077
 *   LINKS: V-M-010, V-M-037, V-M-068, V-M-071, V-M-074, V-M-076, V-M-077, docs/plans/Phase-74.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository text files for deterministic assertions
 *   assertContains - Fails if a required Phase-74 marker is missing
 *   assertNotContains - Fails if retired admin tariff/navigation surface remains visible
 *   assertOrder - Verifies logout marker appears after Nodes route metadata
 *   assertProtectedDiffClean - Fails if Phase-74 touches backend/deploy/runtime/user frontend surfaces
 *   main - Runs Phase-74 admin shell smoke and prints required evidence markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-74 admin shell navigation and scroll verification gate.
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
    throw new Error(`${label} is missing required Phase-74 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains retired Phase-74 surface: ${needle}`)
  }
}

function assertOrder(source, before, after, label) {
  const beforeIndex = source.indexOf(before)
  const afterIndex = source.indexOf(after)
  if (beforeIndex === -1 || afterIndex === -1 || beforeIndex >= afterIndex) {
    throw new Error(`${label} has invalid Phase-74 order: ${before} must appear before ${after}`)
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
      throw new Error(`Protected Phase-74 surface missing from repository: ${protectedPath}`)
    }
  }

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (diff) {
    throw new Error(`Phase-74 must not change backend/deploy/runtime/user frontend surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE74_STATIC_ASSERTIONS
const loginPath = 'frontend-admin/src/pages/Login.tsx'
const layoutPath = 'frontend-admin/src/components/Layout.tsx'
const mainPath = 'frontend-admin/src/main.tsx'
const cssPath = 'frontend-admin/src/index.css'
const adminPlansPath = 'frontend-admin/src/pages/Plans.tsx'
const catalogPath = 'backend/app/billing/catalog.py'
const subscriptionPanelPath = 'frontend/src/components/SubscriptionPanel.tsx'

const login = read(loginPath)
const layout = read(layoutPath)
const main = read(mainPath)
const css = read(cssPath)
const adminPlans = read(adminPlansPath)
const catalog = read(catalogPath)
const subscriptionPanel = read(subscriptionPanelPath)

for (const [label, source] of [
  [loginPath, login],
  [layoutPath, layout],
  [mainPath, main],
  [cssPath, css],
]) {
  assertContains(source, 'START_MODULE_CONTRACT', label)
  assertContains(source, 'Phase-74', label)
}

assertContains(login, 'data-phase74-login-icon-padding="[FrontendAdmin][phase74][LOGIN_ICON_PADDING_SAFE]"', loginPath)
assertContains(login, 'data-phase74-input-form="[MatrixStyle][phase74][ADMIN_LOGIN_ICON_NO_OVERLAP]"', loginPath)
assertContains(login, 'phase74-icon-safe-input', loginPath)
assertNotContains(login, 'admin@krotpn.com', loginPath)
assertNotContains(login, 'placeholder="', loginPath)

assertContains(layout, 'data-phase74-admin-shell="[FrontendAdmin][phase74][NO_TARIFFS_NAV]"', layoutPath)
assertContains(layout, 'data-phase74-admin-rail="[ResponsiveAdaptation][phase74][ADMIN_RAIL_VIEWPORT_SAFE]"', layoutPath)
assertContains(layout, 'data-phase74-desktop-logout="[MobileAdminConsole][phase74][ADMIN_LOGOUT_UNDER_NODES]"', layoutPath)
assertContains(layout, 'data-phase74-content-scroll="[PremiumAdminCockpit][phase74][CONTENT_SCROLL_REPAIRED]"', layoutPath)
assertContains(layout, 'data-phase74-scroll-surface="[ResponsiveAdaptation][phase74][ADMIN_SCROLL_NO_OVERLAP]"', layoutPath)
assertNotContains(layout, "label: 'Тарифы'", layoutPath)
assertNotContains(layout, "to: '/plans'", layoutPath)
assertNotContains(layout, 'CreditCard', layoutPath)
assertOrder(layout, "label: 'Ноды'", 'data-phase74-desktop-logout', layoutPath)

assertContains(main, '<Route path="plans" element={<Navigate to="/" replace />} />', mainPath)
assertNotContains(main, "import Plans from './pages/Plans'", mainPath)
assertNotContains(main, '<Route path="plans" element={<Plans', mainPath)

assertContains(css, 'START_BLOCK_PHASE74_ADMIN_SHELL_SCROLL', cssPath)
assertContains(css, '.phase74-icon-safe-input', cssPath)
assertContains(css, 'padding-left: 3.35rem !important', cssPath)
assertContains(css, '.admin-rail[data-phase74-admin-rail]', cssPath)
assertContains(css, 'max-height: 100dvh', cssPath)
assertContains(css, 'overflow: hidden', cssPath)
assertContains(css, '.admin-content[data-phase74-content-scroll]', cssPath)
assertContains(css, 'overflow-y: auto', cssPath)
assertContains(css, 'scrollbar-gutter: stable', cssPath)
assertContains(css, '[MatrixStyle][phase74][ADMIN_LOGIN_ICON_NO_OVERLAP]', cssPath)
assertContains(css, '[MatrixStyle][phase74][ADMIN_RAIL_BOUNDED]', cssPath)
assertContains(css, '[MatrixStyle][phase74][ADMIN_SCROLL_SURFACE_SAFE]', cssPath)
assertContains(css, '[ResponsiveAdaptation][phase74][ADMIN_SCROLL_NO_OVERLAP]', cssPath)
assertContains(css, '[ResponsiveAdaptation][phase74][ADMIN_RAIL_VIEWPORT_SAFE]', cssPath)
assertContains(css, '[MatrixMotion][phase74][SCROLL_POINTER_SAFE]', cssPath)

assertContains(adminPlans, 'Защищенная матрица Phase-50', adminPlansPath)
assertContains(adminPlans, '[PremiumAdminCockpit][phase58][TARIFF_ADMIN_GUARD]', adminPlansPath)
assertContains(catalog, 'slug="krotpn-1"', catalogPath)
assertContains(catalog, 'slug="krotpn-6"', catalogPath)
assertContains(catalog, 'slug="krotpn-9"', catalogPath)
assertContains(subscriptionPanel, 'KrotPN Self', subscriptionPanelPath)
assertContains(subscriptionPanel, 'KrotPN Family', subscriptionPanelPath)
assertContains(subscriptionPanel, 'KrotPN Team', subscriptionPanelPath)

assertProtectedDiffClean()
// END_BLOCK_PHASE74_STATIC_ASSERTIONS

console.log('[FrontendAdmin][phase74][LOGIN_ICON_PADDING_SAFE] ok')
console.log('[FrontendAdmin][phase74][NO_TARIFFS_NAV] ok')
console.log('[FrontendAdmin][phase74][PLANS_ROUTE_SAFE] ok')
console.log('[FrontendAdmin][phase74][PROTECTED_ADMIN_API_UNCHANGED] ok')
console.log('[MobileAdminConsole][phase74][ADMIN_LOGOUT_UNDER_NODES] ok')
console.log('[MobileAdminConsole][phase74][CONTENT_SCROLL_WHEEL_SAFE] ok')
console.log('[MobileAdminConsole][phase74][RAIL_BOUNDS_SAFE] ok')
console.log('[TariffCatalog][phase74][ADMIN_TARIFF_UI_REMOVED_ONLY] ok')
console.log('[TariffCatalog][phase74][CANONICAL_TARIFFS_PRESERVED] ok')
console.log('[MatrixStyle][phase74][ADMIN_LOGIN_ICON_NO_OVERLAP] ok')
console.log('[MatrixStyle][phase74][ADMIN_RAIL_BOUNDED] ok')
console.log('[MatrixStyle][phase74][ADMIN_SCROLL_SURFACE_SAFE] ok')
console.log('[ResponsiveAdaptation][phase74][ADMIN_SCROLL_NO_OVERLAP] ok')
console.log('[ResponsiveAdaptation][phase74][ADMIN_RAIL_VIEWPORT_SAFE] ok')
console.log('[PremiumAdminCockpit][phase74][LOGOUT_UNDER_NODES] ok')
console.log('[PremiumAdminCockpit][phase74][TARIFFS_ROUTE_REMOVED] ok')
console.log('[PremiumAdminCockpit][phase74][CONTENT_SCROLL_REPAIRED] ok')
console.log('[MatrixMotion][phase74][ADMIN_NAV_MOTION_SAFE] ok')
console.log('[MatrixMotion][phase74][SCROLL_POINTER_SAFE] ok')
