#!/usr/bin/env node
/*
 * FILE: scripts/phase77-subscription-mobile-polish-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke verification for Phase-77 subscription calendar and mobile dock polish
 *   SCOPE: Active-until subscription copy, clickable config guidance, green/cyan/red calendar markers, fixed mobile bottom navigation, mobile scroll-safety CSS, and protected admin/backend/deploy/runtime guard
 *   DEPENDS: M-009, M-036, M-063, M-071, M-074, M-075, M-077
 *   LINKS: docs/plans/Phase-77.xml, docs/verification/V-M-009.xml, docs/verification/V-M-036.xml, docs/verification/V-M-063.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository files for deterministic static assertions
 *   assertContains - Fails if a required Phase-77 marker is missing
 *   assertNotContains - Fails if a prohibited stale marker is present
 *   assertProtectedSurfaceDiffClean - Fails if Phase-77 touches protected surfaces
 *   main - Runs Phase-77 static assertions and emits redacted pass markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.1 - Added mobile regression guards for MTProto secret touch-scroll and route-transform-safe bottom dock.
 *   LAST_CHANGE: v1.0.0 - Added Phase-77 subscription/mobile polish verification gate.
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
    throw new Error(`${label} is missing required Phase-77 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-77 marker: ${needle}`)
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
      throw new Error(`Protected Phase-77 surface missing from repository: ${protectedPath}`)
    }
  }

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (diff) {
    throw new Error(`Phase-77 must not change admin/backend/deploy/runtime surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE77_STATIC_ASSERTIONS
const subscriptionPanel = read('frontend/src/components/SubscriptionPanel.tsx')
const dashboard = read('frontend/src/pages/Dashboard.tsx')
const layout = read('frontend/src/components/Layout.tsx')
const css = read('frontend/src/index.css')
const i18n = read('frontend/src/i18n/index.ts')
const phase = read('docs/plans/Phase-77.xml')
const verificationIndex = read('docs/verification-index.xml')

for (const [label, source] of [
  ['frontend/src/components/SubscriptionPanel.tsx', subscriptionPanel],
  ['frontend/src/pages/Dashboard.tsx', dashboard],
  ['frontend/src/components/Layout.tsx', layout],
  ['frontend/src/index.css', css],
  ['frontend/src/i18n/index.ts', i18n],
]) {
  assertContains(source, 'START_MODULE_CONTRACT', label)
  assertContains(source, 'START_MODULE_MAP', label)
  assertContains(source, 'START_CHANGE_SUMMARY', label)
}

for (const needle of [
  "subscriptionDescriptionActive: 'Доступ активен до: {{date}}'",
  "subscriptionDescriptionActive: 'Access is active until: {{date}}'",
  "const activeUntil = formatDateTime(subscription.active_until || subscription.expires_at, locale)",
  "t('subscriptionDescriptionActive', { date: activeUntil })",
  "subscription?.is_active ? 'mt-2 text-xs muted' : 'mt-2 text-sm muted'",
]) {
  assertContains(subscriptionPanel + i18n, needle, 'Phase-77 active-until copy')
}
assertNotContains(subscriptionPanel + i18n, 'Доступ активен. Таймер обновляется автоматически.', 'Phase-77 active-until copy')

for (const needle of [
  'renderConfigGuidance',
  'to="/dashboard/config"',
  'className="phase77-config-link font-extrabold"',
  'data-phase77-config-link="[FrontendUser][phase77][CONFIG_GUIDANCE_LINK]"',
  "renderConfigGuidance(' уже доступен. Таймер на 4 дня стартует после первого подключения.')",
]) {
  assertContains(subscriptionPanel, needle, 'Phase-77 config guidance link')
}

for (const needle of [
  'phase77-calendar-day-start',
  'phase77-calendar-day-today',
  'phase77-calendar-day-end',
  "data-phase77-calendar-marker={day.rangeEnd ? 'range-end-red' : day.rangeStart ? 'range-start-green' : day.today ? 'today-cyan' : undefined}",
  'matrixCalendarStartPulse',
  'matrixCalendarTodayPulse',
  'matrixCalendarEndPulse',
  '[TrialSubscription][phase77][CALENDAR_MARKERS_READY]',
]) {
  assertContains(subscriptionPanel + css, needle, 'Phase-77 calendar markers')
}

for (const needle of [
  'data-phase77-mobile-shell="[MobileUserCabinet][phase77][TOUCH_SCROLL_SAFE]"',
  'data-phase77-scroll-surface="[ResponsiveAdaptation][phase77][MOBILE_SCROLL_SURFACE_SAFE]"',
  'data-phase77-mobile-nav="[MobileUserCabinet][phase77][BOTTOM_NAV_ALWAYS_VISIBLE]"',
  'data-mobile-dock-fix="[MobileUserCabinet][fix][MOBILE_DOCK_VIEWPORT_FIXED]"',
  'data-mobile-scroll-fix="[MobileUserCabinet][fix][MTPROTO_SECRET_SCROLL_PASSIVE]"',
  'phase77-mobile-scroll-content',
  'matrix-terminal matrix-mtproto-secret',
  '.matrix-bottom-nav',
  '.matrix-terminal.matrix-mtproto-secret',
  'bottom: max(0.5rem, env(safe-area-inset-bottom))',
  'pointer-events: auto',
  'touch-action: manipulation',
  'overflow: visible',
  'touch-action: pan-y',
  'overscroll-behavior: auto',
  '-webkit-overflow-scrolling: touch',
  '-webkit-overflow-scrolling: auto',
  '.matrix-visual-content.motion-route-enter',
  'animation: none;',
  'transform: none;',
  '[ResponsiveAdaptation][phase77][MOBILE_DOCK_FIXED_SAFE]',
  '[MobileUserCabinet][fix][MTPROTO_SECRET_SCROLL_PASSIVE]',
  '[MobileUserCabinet][fix][MOBILE_DOCK_VIEWPORT_FIXED]',
  '[MatrixMotion][fix][MOBILE_ROUTE_TRANSFORM_OFF]',
]) {
  assertContains(dashboard + layout + css, needle, 'Phase-77 mobile dock and scroll')
}

for (const needle of [
  'User Subscription Calendar and Mobile Dock Polish',
  'Phase-77-Verification',
  'M-009,M-036,M-063,M-071,M-074,M-075,M-077',
]) {
  assertContains(phase + verificationIndex, needle, 'Phase-77 MyGRACE artifacts')
}

assertProtectedSurfaceDiffClean()
// END_BLOCK_PHASE77_STATIC_ASSERTIONS

console.log('[TrialSubscription][phase77][ACTIVE_UNTIL_COPY] ok')
console.log('[FrontendUser][phase77][CONFIG_GUIDANCE_LINK] ok')
console.log('[TrialSubscription][phase77][CALENDAR_MARKERS_READY] ok')
console.log('[MobileUserCabinet][phase77][BOTTOM_NAV_ALWAYS_VISIBLE] ok')
console.log('[ResponsiveAdaptation][phase77][MOBILE_SCROLL_SURFACE_SAFE] ok')
console.log('[ResponsiveAdaptation][phase77][MOBILE_DOCK_FIXED_SAFE] ok')
console.log('[MobileUserCabinet][fix][MTPROTO_SECRET_SCROLL_PASSIVE] ok')
console.log('[MobileUserCabinet][fix][MOBILE_DOCK_VIEWPORT_FIXED] ok')
console.log('[MatrixMotion][fix][MOBILE_ROUTE_TRANSFORM_OFF] ok')
console.log('[MatrixMotion][phase77][NO_SCROLL_HIJACK] static')
console.log('[Phase77][ProtectedSurfaceGuard][NO_ADMIN_BACKEND_DEPLOY_RUNTIME_DRIFT] ok')
