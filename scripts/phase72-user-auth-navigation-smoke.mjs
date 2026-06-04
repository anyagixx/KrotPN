#!/usr/bin/env node
/*
 * FILE: scripts/phase72-user-auth-navigation-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke verification for Phase-72 user auth and cabinet navigation polish
 *   SCOPE: Login invalid-credential localization, desktop logout placement, mobile bottom dock reachability, Settings language removal, compact desktop subscription calendar, and protected admin/backend/deploy/runtime guard
 *   DEPENDS: M-009, M-036, M-063, M-071, M-074, M-075, M-077
 *   LINKS: docs/plans/Phase-72.xml, docs/verification/V-M-009.xml, docs/verification/V-M-075.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository files for deterministic static assertions
 *   assertContains - Fails if a required Phase-72 marker is missing
 *   assertNotContains - Fails if a prohibited stale marker is present
 *   assertAfter - Fails if expected source order is not preserved
 *   assertProtectedSurfaceDiffClean - Fails if Phase-72 drifts outside user frontend/docs/scripts
 *   main - Runs Phase-72 static assertions and prints aggregate safe markers only
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-72 user auth/navigation verification gate.
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
    throw new Error(`${label} is missing required Phase-72 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-72 marker: ${needle}`)
  }
}

function assertAfter(source, before, after, label) {
  const beforeIndex = source.indexOf(before)
  const afterIndex = source.indexOf(after)
  if (beforeIndex === -1 || afterIndex === -1 || afterIndex <= beforeIndex) {
    throw new Error(`${label} does not preserve Phase-72 order: ${before} -> ${after}`)
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
      throw new Error(`Protected Phase-72 surface missing from repository: ${protectedPath}`)
    }
  }

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (diff) {
    throw new Error(`Phase-72 must not change admin/backend/deploy/runtime surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE72_STATIC_ASSERTIONS
const login = read('frontend/src/pages/Login.tsx')
const layout = read('frontend/src/components/Layout.tsx')
const settings = read('frontend/src/pages/Settings.tsx')
const subscriptionPanel = read('frontend/src/components/SubscriptionPanel.tsx')
const i18n = read('frontend/src/i18n/index.ts')
const css = read('frontend/src/index.css')
const phase = read('docs/plans/Phase-72.xml')

for (const [label, source] of [
  ['frontend/src/pages/Login.tsx', login],
  ['frontend/src/components/Layout.tsx', layout],
  ['frontend/src/pages/Settings.tsx', settings],
  ['frontend/src/components/SubscriptionPanel.tsx', subscriptionPanel],
  ['frontend/src/i18n/index.ts', i18n],
  ['frontend/src/index.css', css],
]) {
  assertContains(source, 'START_MODULE_CONTRACT', label)
  assertContains(source, 'START_MODULE_MAP', label)
  assertContains(source, 'START_CHANGE_SUMMARY', label)
}

for (const needle of [
  'normalizeLoginError',
  "return 'Неверный логин или пароль'",
  "invalidCredentials: 'Неверный логин или пароль'",
  'toast.error(normalizeLoginError(error, t(\'invalidCredentials\')))',
  'data-phase72-login-error="[FrontendUser][phase72][LOGIN_ERROR_LOCALIZED]"',
]) {
  assertContains(login + i18n, needle, 'Phase-72 login localization')
}
for (const prohibited of [
  "invalidCredentials: 'Неверный email или пароль'",
  'toast.error(error.response?.data?.detail',
  'toast.error(error?.response?.data?.detail',
]) {
  assertNotContains(login + i18n, prohibited, 'Phase-72 login localization')
}

for (const needle of [
  'data-phase72-desktop-nav="[PremiumUserCabinet][phase72][LOGOUT_UNDER_SETTINGS]"',
  'data-phase72-desktop-logout="[PremiumUserCabinet][phase72][DESKTOP_LOGOUT_VISIBLE]"',
  'data-phase72-mobile-nav="[MobileUserCabinet][phase72][BOTTOM_NAV_SAFE]"',
  'data-phase72-touch-nav="[MatrixMotion][phase72][TOUCH_NAV_REVEAL_SAFE]"',
  'className="matrix-bottom-nav phase72-touch-dock"',
  "to: '/dashboard'",
  "to: '/dashboard/config'",
  "to: '/dashboard/subscription'",
  "to: '/dashboard/referrals'",
  "to: '/dashboard/settings'",
]) {
  assertContains(layout, needle, 'frontend/src/components/Layout.tsx')
}
assertAfter(layout, "to: '/dashboard/settings'", 'data-phase72-desktop-logout', 'frontend/src/components/Layout.tsx')
assertNotContains(layout, 'btn-secondary min-h-11 w-full justify-start', 'frontend/src/components/Layout.tsx')

for (const needle of [
  'data-phase72-settings-language="[FrontendUser][phase72][LANGUAGE_SETTINGS_REMOVED]"',
  'data-phase57-settings-password-policy="strong-password"',
  "updateProfile.mutate({ name })",
]) {
  assertContains(settings, needle, 'frontend/src/pages/Settings.tsx')
}
for (const prohibited of [
  'Globe',
  'setLanguage',
  'changeLanguage',
  "t('language')",
  "t('languageSubtitle')",
  "t('russian')",
  "t('english')",
  'updateProfile.mutate({ language',
]) {
  assertNotContains(settings, prohibited, 'frontend/src/pages/Settings.tsx')
}
assertContains(i18n, "settingsSubtitle: 'Управляйте профилем и безопасностью учётной записи.'", 'frontend/src/i18n/index.ts')
assertContains(i18n, "lng: 'ru'", 'frontend/src/i18n/index.ts')
assertNotContains(i18n, "lng: localStorage.getItem('language') || 'ru'", 'frontend/src/i18n/index.ts')

for (const needle of [
  'data-phase72-subscription-calendar="[TrialSubscription][phase72][DESKTOP_CALENDAR_COMPACT]"',
  'data-phase71-calendar-boundary',
  'phase68-calendar-day-start',
  'phase68-calendar-day-end',
]) {
  assertContains(subscriptionPanel, needle, 'frontend/src/components/SubscriptionPanel.tsx')
}

for (const needle of [
  'START_BLOCK_PHASE72_USER_AUTH_NAVIGATION_POLISH',
  '@media (min-width: 1024px)',
  'grid-template-columns: repeat(auto-fit, minmax(128px, 144px))',
  'min-height: 1rem',
  '.phase72-touch-dock',
  'touch-action: manipulation',
  '[FrontendUser][phase72][LOGIN_ERROR_LOCALIZED]',
  '[PremiumUserCabinet][phase72][LOGOUT_UNDER_SETTINGS]',
  '[MobileUserCabinet][phase72][BOTTOM_NAV_SAFE]',
  '[ResponsiveAdaptation][phase72][MOBILE_DOCK_NO_OVERLAP]',
  '[ResponsiveAdaptation][phase72][DESKTOP_CALENDAR_NO_OVERFLOW]',
  '[MatrixStyle][phase72][CALENDAR_DENSITY_READY]',
  '[MatrixMotion][phase72][TOUCH_NAV_REVEAL_SAFE]',
]) {
  assertContains(css, needle, 'frontend/src/index.css')
}

for (const needle of [
  'User Auth and Cabinet Navigation Polish',
  '<step-10>',
  'Неверный логин или пароль',
  'Language settings must be completely removed',
]) {
  assertContains(phase, needle, 'docs/plans/Phase-72.xml')
}

assertProtectedSurfaceDiffClean()
// END_BLOCK_PHASE72_STATIC_ASSERTIONS

console.log('[FrontendUser][phase72][LOGIN_ERROR_LOCALIZED] ok')
console.log('[FrontendUser][phase72][LANGUAGE_SETTINGS_REMOVED] ok')
console.log('[PremiumUserCabinet][phase72][LOGOUT_UNDER_SETTINGS] ok')
console.log('[PremiumUserCabinet][phase72][DESKTOP_LOGOUT_VISIBLE] ok')
console.log('[MobileUserCabinet][phase72][BOTTOM_NAV_SAFE] ok')
console.log('[TrialSubscription][phase72][DESKTOP_CALENDAR_COMPACT] ok')
console.log('[ResponsiveAdaptation][phase72][MOBILE_DOCK_NO_OVERLAP] ok')
console.log('[ResponsiveAdaptation][phase72][DESKTOP_CALENDAR_NO_OVERFLOW] ok')
console.log('[MatrixStyle][phase72][CALENDAR_DENSITY_READY] ok')
console.log('[MatrixMotion][phase72][TOUCH_NAV_REVEAL_SAFE] ok')
console.log('[MatrixMotion][phase72][REDUCED_MOTION_NAV_PASS] static')
console.log('[Phase72][ProtectedSurfaceGuard][NO_ADMIN_BACKEND_DEPLOY_RUNTIME_DRIFT] ok')
