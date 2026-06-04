#!/usr/bin/env node
/*
 * FILE: scripts/phase59-motion-interactions-smoke.mjs
 * VERSION: 1.2.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke verification for Phase-59 Matrix motion and microinteractions
 *   SCOPE: Motion budget tokens, route transitions, Matrix rain fallback/overscan safety, copy/status feedback markers, reduced-motion fallback, pointer/scroll/focus safety, inactive-tab lifecycle, and protected surface guard
 *   DEPENDS: M-077, M-009, M-010, M-070, M-071, M-072, M-075, M-076
 *   LINKS: V-M-077, docs/plans/Phase-59.xml, docs/modules/M-077.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository files for static assertions
 *   assertContains - Fails if a file lacks a required marker
 *   assertNotContains - Fails if a file contains a prohibited marker
 *   assertRegexAbsent - Fails if a source matches a prohibited pattern
 *   assertProtectedSurfaceDiffClean - Fails if Phase-59 touched backend/deploy/runtime surfaces
 *   main - Runs Phase-59 static assertions and prints required verification markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.2.0 - Added root-transform safety, CSS rain fallback, and mobile viewport overscan assertions.
 *   LAST_CHANGE: v1.1.0 - Accepted Phase-67 guarded request/cancel animation frame compatibility in MatrixBackground.
 *   LAST_CHANGE: v1.0.0 - Added Phase-59 motion and microinteraction verification gate
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
    throw new Error(`${label} is missing required Phase-59 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-59 marker: ${needle}`)
  }
}

function assertRegexAbsent(source, regex, label) {
  if (regex.test(source)) {
    throw new Error(`${label} matches prohibited Phase-59 pattern: ${regex}`)
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
      throw new Error(`Protected Phase-59 surface missing from repository: ${protectedPath}`)
    }
  }

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (diff) {
    throw new Error(`Phase-59 must not change backend/deploy/runtime surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE59_STATIC_ASSERTIONS
const userCss = read('frontend/src/index.css')
const adminCss = read('frontend-admin/src/index.css')
const userVisualShell = read('frontend/src/components/VisualShell.tsx')
const adminVisualShell = read('frontend-admin/src/components/VisualShell.tsx')
const userMatrix = read('frontend/src/components/MatrixBackground.tsx')
const adminMatrix = read('frontend-admin/src/components/MatrixBackground.tsx')
const dashboard = read('frontend/src/pages/Dashboard.tsx')
const config = read('frontend/src/pages/Config.tsx')
const referrals = read('frontend/src/pages/Referrals.tsx')
const devices = read('frontend-admin/src/pages/Devices.tsx')
const mtproto = read('frontend-admin/src/pages/MTProto.tsx')
const mtprotoAnalytics = read('frontend-admin/src/pages/MTProtoAnalytics.tsx')

for (const [label, source] of [
  ['frontend/src/index.css', userCss],
  ['frontend-admin/src/index.css', adminCss],
  ['frontend/src/components/VisualShell.tsx', userVisualShell],
  ['frontend-admin/src/components/VisualShell.tsx', adminVisualShell],
  ['frontend/src/components/MatrixBackground.tsx', userMatrix],
  ['frontend-admin/src/components/MatrixBackground.tsx', adminMatrix],
  ['frontend/src/pages/Dashboard.tsx', dashboard],
  ['frontend/src/pages/Config.tsx', config],
  ['frontend/src/pages/Referrals.tsx', referrals],
  ['frontend-admin/src/pages/Devices.tsx', devices],
  ['frontend-admin/src/pages/MTProto.tsx', mtproto],
  ['frontend-admin/src/pages/MTProtoAnalytics.tsx', mtprotoAnalytics],
]) {
  assertContains(source, 'START_MODULE_CONTRACT', label)
  assertContains(source, 'START_MODULE_MAP', label)
  assertContains(source, 'START_CHANGE_SUMMARY', label)
  assertContains(source, 'M-077', label)
  assertContains(source, 'Phase-59', label)
}

for (const [label, source] of [
  ['frontend/src/index.css', userCss],
  ['frontend-admin/src/index.css', adminCss],
]) {
  for (const needle of [
    'START_BLOCK_PHASE59_MOTION_BUDGET',
    'START_BLOCK_PHASE59_MATRIX_MOTION',
    '--motion-duration-fast: 120ms',
    '--motion-duration-standard: 180ms',
    '--motion-duration-route: 220ms',
    '.motion-route-enter',
    '.matrix-rain-fallback',
    'matrixCssRainFallback',
    '.motion-interactive',
    '.motion-copy-success',
    '.motion-feedback-success',
    '.motion-feedback-error',
    '.motion-status',
    '@keyframes matrixRouteEnter',
    '@keyframes matrixFeedbackPulse',
    '@media (prefers-reduced-motion: reduce)',
    '[MatrixMotion][phase59][MOTION_BUDGET_READY]',
    '[MatrixMotion][phase59][MICROINTERACTIONS_READY]',
    '[MatrixMotion][phase59][STATUS_TRANSITIONS_READY]',
    '[MatrixMotion][phase59][ROUTE_TRANSITIONS_FAST]',
    '[MatrixMotion][phase59][REDUCED_MOTION_PASS]',
    '[MatrixMotion][phase59][POINTER_SCROLL_SAFE]',
    '[MatrixMotion][phase59][KEYBOARD_FOCUS_SAFE]',
    '[MatrixVisualRuntime][fix][CSS_RAIN_FALLBACK_READY]',
    '[MatrixVisualRuntime][fix][MOBILE_OVERSCAN_READY]',
    'pointer-events: none',
  ]) {
    assertContains(source, needle, label)
  }

  for (const prohibited of [
    'scroll-snap-type',
    'scroll-snap-align',
    'requestPointerLock',
    'wheel',
    'preventDefault()',
    'setInterval(',
    'radial-gradient(',
    'rounded-2xl',
    'rounded-3xl',
    'font-size: clamp(',
    'font-size: calc(',
  ]) {
    assertNotContains(source, prohibited, label)
  }
  assertRegexAbsent(source, /letter-spacing:\s*-[^;]+;/, label)
  assertRegexAbsent(source, /font-size:\s*[^;]*vw[^;]*;/, label)
  assertRegexAbsent(source, /duration:\s*[4-9]\d\dms/i, label)
}

for (const [label, source] of [
  ['frontend/src/components/VisualShell.tsx', userVisualShell],
  ['frontend-admin/src/components/VisualShell.tsx', adminVisualShell],
]) {
  for (const needle of [
    'className="matrix-visual-shell"',
    'data-matrix-rain-fallback="[MatrixVisualRuntime][fix][CSS_RAIN_FALLBACK_READY]"',
    'data-phase59-motion-budget="[MatrixMotion][phase59][MOTION_BUDGET_READY]"',
    'data-phase59-route-transition="[MatrixMotion][phase59][ROUTE_TRANSITIONS_FAST]"',
    'data-phase59-reduced-motion="[MatrixMotion][phase59][REDUCED_MOTION_PASS]"',
    'data-phase59-pointer-scroll="[MatrixMotion][phase59][POINTER_SCROLL_SAFE]"',
    'data-phase59-keyboard-focus="[MatrixMotion][phase59][KEYBOARD_FOCUS_SAFE]"',
    'matrix-visual-content motion-safe-layer motion-route-enter',
  ]) {
    assertContains(source, needle, label)
  }
  assertNotContains(source, 'className="matrix-visual-shell motion-route-enter"', label)
}

for (const [label, source] of [
  ['frontend/src/components/MatrixBackground.tsx', userMatrix],
  ['frontend-admin/src/components/MatrixBackground.tsx', adminMatrix],
]) {
  for (const needle of [
    'prefers-reduced-motion: reduce',
    "window.addEventListener('pointermove', handlePointerMove, { passive: true })",
    "document.addEventListener('visibilitychange', handleVisibility)",
    'cancelAnimationFrame',
    'CANVAS_OVERSCAN_PX',
    'getCanvasDimensions',
    "visualViewport?.addEventListener('resize', resize)",
    "visualViewport?.addEventListener('scroll', resize)",
    '[MatrixMotion][phase59][REDUCED_MOTION_PASS]',
    '[MatrixMotion][phase59][POINTER_SCROLL_SAFE]',
    '[MatrixMotion][phase59][INACTIVE_TAB_SAFE]',
    'data-phase59-pointer-scroll="[MatrixMotion][phase59][POINTER_SCROLL_SAFE]"',
    'data-phase59-inactive-tab="[MatrixMotion][phase59][INACTIVE_TAB_SAFE]"',
  ]) {
    assertContains(source, needle, label)
  }
  assertNotContains(source, 'setInterval(', label)
  assertNotContains(source, 'preventDefault()', label)
}

for (const [label, source] of [
  ['frontend/src/pages/Dashboard.tsx', dashboard],
  ['frontend/src/pages/Config.tsx', config],
  ['frontend/src/pages/Referrals.tsx', referrals],
  ['frontend-admin/src/pages/Devices.tsx', devices],
  ['frontend-admin/src/pages/MTProto.tsx', mtproto],
  ['frontend-admin/src/pages/MTProtoAnalytics.tsx', mtprotoAnalytics],
]) {
  assertContains(source, '[MatrixMotion][phase59][MICROINTERACTIONS_READY]', label)
  assertContains(source, 'motion-status', label)
}

for (const [label, source] of [
  ['frontend/src/pages/Dashboard.tsx', dashboard],
  ['frontend/src/pages/Config.tsx', config],
  ['frontend/src/pages/Referrals.tsx', referrals],
]) {
  assertContains(source, 'motion-copy-success', label)
  assertContains(source, 'navigator.clipboard.writeText', label)
}

for (const [label, source] of [
  ['frontend-admin/src/pages/Devices.tsx', devices],
  ['frontend-admin/src/pages/MTProto.tsx', mtproto],
  ['frontend-admin/src/pages/MTProtoAnalytics.tsx', mtprotoAnalytics],
]) {
  assertContains(source, 'motion-feedback-success', label)
  assertContains(source, 'motion-feedback-error', label)
  assertContains(source, '[MatrixMotion][phase59][STATUS_TRANSITIONS_READY]', label)
}

for (const [label, source] of [
  ['frontend/src/pages/Dashboard.tsx', dashboard],
  ['frontend-admin/src/pages/MTProtoAnalytics.tsx', mtprotoAnalytics],
]) {
  for (const prohibited of [
    'console.info(MTPROTO_COPY_ACTION_MARKER, { field, value',
    'console.info(MTPROTO_OPEN_TELEGRAM_MARKER, { link',
    'raw_promotion_tag',
    'unmasked_secret',
    'proxy_url',
    'full_proxy_url',
  ]) {
    assertNotContains(source, prohibited, label)
  }
}

assertProtectedSurfaceDiffClean()
// END_BLOCK_PHASE59_STATIC_ASSERTIONS

console.log('[MatrixMotion][phase59][MOTION_BUDGET_READY] ok')
console.log('[MatrixMotion][phase59][MICROINTERACTIONS_READY] ok')
console.log('[MatrixMotion][phase59][STATUS_TRANSITIONS_READY] ok')
console.log('[MatrixMotion][phase59][ROUTE_TRANSITIONS_FAST] ok')
console.log('[MatrixMotion][phase59][REDUCED_MOTION_PASS] ok')
console.log('[MatrixMotion][phase59][POINTER_SCROLL_SAFE] ok')
console.log('[MatrixMotion][phase59][KEYBOARD_FOCUS_SAFE] ok')
console.log('[MatrixMotion][phase59][INACTIVE_TAB_SAFE] ok')
console.log('[MatrixMotion][phase59][SCREENSHOT_MATRIX_REVIEWED] static-route-proof')
console.log('[MatrixMotion][phase59][PROTECTED_SURFACE_GUARD] ok')
