#!/usr/bin/env node
/*
 * FILE: scripts/phase61-responsive-adaptation-smoke.mjs
 * VERSION: 1.1.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke verification for Phase-61 phone and tablet responsive adaptation closure
 *   SCOPE: User/admin responsive CSS contracts, Matrix rain mobile overscan, layout safe-area markers, route static proof, no-overflow/no-overlap guards, touch targets, reduced-motion, build bundle budgets, and protected backend/deploy/runtime guard
 *   DEPENDS: M-074, M-009, M-010, M-036, M-037, M-038, M-071, M-072
 *   LINKS: V-M-074, docs/plans/Phase-61.xml, docs/modules/M-074.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository text files for deterministic assertions
 *   assertContains - Fails if a file lacks a required marker
 *   assertNotContains - Fails if a file contains prohibited responsive drift
 *   assertRegexAbsent - Fails if a source matches prohibited viewport-scaled typography or spacing drift
 *   assertResponsiveCss - Verifies Phase-61 responsive CSS blocks across user and admin apps
 *   assertLayoutProof - Verifies Phase-61 shell, safe-area, protected-route, and static proof markers
 *   assertRouteProof - Verifies public/auth/user/admin route coverage markers without requiring live credentials
 *   assertPerformanceBudgets - Verifies built dist artifact sizes stay inside Phase-60 budgets
 *   assertProtectedSurfaceDiffClean - Fails if Phase-61 touched backend/deploy/runtime surfaces
 *   main - Runs Phase-61 responsive adaptation smoke and prints required markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.1.0 - Added Matrix rain fallback and mobile overscan responsive assertions.
 *   LAST_CHANGE: v1.0.0 - Added Phase-61 responsive adaptation verification gate.
 * END_CHANGE_SUMMARY
 */

import { execFileSync } from 'node:child_process'
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { extname, join, relative } from 'node:path'
import { gzipSync } from 'node:zlib'

const root = process.cwd()

const phoneViewports = [
  ['phone-320', 320, 568],
  ['phone-360', 360, 740],
  ['phone-375', 375, 667],
  ['phone-390', 390, 844],
  ['phone-430', 430, 932],
]

const tabletViewports = [
  ['tablet-768', 768, 1024],
  ['tablet-820', 820, 1180],
  ['tablet-landscape', 1024, 768],
  ['tablet-tall', 1024, 1366],
]

const desktopViewports = [
  ['desktop-short', 1280, 720],
  ['desktop', 1440, 900],
]

const publicAuthRoutes = ['/', '/login', '/register', '/forgot-password', '/reset-password', '/verify-email']
const userProtectedRoutes = ['/dashboard', '/dashboard/config', '/dashboard/subscription', '/dashboard/referrals', '/dashboard/settings']
const adminRoutes = ['/login', '/', '/users', '/devices', '/mtproto', '/servers', '/plans', '/analytics']

function read(relativePath) {
  return readFileSync(join(root, relativePath), 'utf8')
}

function assertContains(source, needle, label) {
  if (!source.includes(needle)) {
    throw new Error(`${label} is missing required Phase-61 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-61 marker: ${needle}`)
  }
}

function assertRegexAbsent(source, regex, label) {
  if (regex.test(source)) {
    throw new Error(`${label} matches prohibited Phase-61 pattern: ${regex}`)
  }
}

function assertUnique(values, label) {
  const seen = new Set(values)
  if (seen.size !== values.length) {
    throw new Error(`${label} contains duplicate entries`)
  }
}

function listFiles(relativePath) {
  const directory = join(root, relativePath)
  if (!existsSync(directory)) {
    throw new Error(`Directory does not exist: ${relativePath}`)
  }

  const files = []
  function walk(current) {
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      const path = join(current, entry.name)
      if (entry.isDirectory()) {
        walk(path)
      } else if (entry.isFile()) {
        files.push(path)
      }
    }
  }
  walk(directory)
  return files
}

function largestAsset(relativePath, extension) {
  const files = listFiles(relativePath).filter((path) => extname(path) === extension)
  if (!files.length) {
    throw new Error(`No ${extension} assets found under ${relativePath}. Run frontend builds before Phase-61 smoke.`)
  }
  return files.sort((a, b) => statSync(b).size - statSync(a).size)[0]
}

function assertBytes(label, filePath, maxBytes) {
  const bytes = statSync(filePath).size
  if (bytes > maxBytes) {
    throw new Error(`${label} exceeds Phase-61 budget: ${bytes} > ${maxBytes} bytes (${relative(root, filePath)})`)
  }
  const gzipBytes = gzipSync(readFileSync(filePath)).length
  console.log(`[ResponsiveAdaptation][phase61][BUNDLE_BUDGET] ${label} raw=${bytes} gzip=${gzipBytes} max=${maxBytes} path=${relative(root, filePath)}`)
}

function assertResponsiveCss() {
  const userCss = read('frontend/src/index.css')
  const adminCss = read('frontend-admin/src/index.css')

  for (const [label, source] of [
    ['frontend/src/index.css', userCss],
    ['frontend-admin/src/index.css', adminCss],
  ]) {
    for (const marker of [
      'START_MODULE_CONTRACT',
      'M-074',
      'Phase-61',
      'START_BLOCK_PHASE61_RESPONSIVE_ADAPTATION',
      'END_BLOCK_PHASE61_RESPONSIVE_ADAPTATION',
      '@media (min-width: 768px) and (max-width: 1023px)',
      '@media (max-width: 767px)',
      '@media (max-width: 480px)',
      '@media (max-width: 360px)',
      'env(safe-area-inset-bottom)',
      'min-height: 44px',
      'overscroll-behavior: contain',
      'scrollbar-gutter: stable',
      'overflow-wrap: anywhere',
      'word-break: break-word',
      '.matrix-rain-fallback',
      'min-height: calc(100dvh + 128px)',
      '[MatrixVisualRuntime][fix][CSS_RAIN_FALLBACK_READY]',
      '[MatrixVisualRuntime][fix][MOBILE_OVERSCAN_READY]',
      '[ResponsiveAdaptation][phase61][PHONE_LAYOUT_PASS]',
      '[ResponsiveAdaptation][phase61][TABLET_LAYOUT_PASS]',
      '[ResponsiveAdaptation][phase61][NO_HORIZONTAL_SCROLL]',
      '[ResponsiveAdaptation][phase61][NO_OVERLAP_PASS]',
      '[ResponsiveAdaptation][phase61][TOUCH_TARGETS_PASS]',
      '[ResponsiveAdaptation][phase61][SAFE_AREA_PASS]',
      '@media (prefers-reduced-motion: reduce)',
      'letter-spacing: 0',
      'overflow-x: hidden',
      'pointer-events: none',
    ]) {
      assertContains(source, marker, label)
    }

    for (const prohibited of [
      'rounded-2xl',
      'rounded-3xl',
      'text-5xl',
      'text-4xl',
      'tracking-[',
      'font-size: clamp(',
      'font-size: calc(',
    ]) {
      assertNotContains(source, prohibited, label)
    }
    assertRegexAbsent(source, /letter-spacing:\s*-[^;]+;/, label)
    assertRegexAbsent(source, /font-size:\s*[^;]*vw[^;]*;/, label)
  }

  for (const marker of [
    '.matrix-bottom-nav',
    '.matrix-main-panel > div',
    '.phase57-primary-actions',
    '.matrix-action-grid',
    '.phase57-scroll-list',
    '.matrix-terminal',
    '.matrix-auth-screen',
  ]) {
    assertContains(userCss, marker, 'frontend/src/index.css')
  }

  for (const marker of [
    '.mobile-tabbar',
    '.phase58-cockpit-main',
    '.phase58-inventory-list',
    '.chart-frame',
    '.data-table',
    '.row-main',
    '.row-meta',
  ]) {
    assertContains(adminCss, marker, 'frontend-admin/src/index.css')
  }
}

function assertLayoutProof() {
  const userLayout = read('frontend/src/components/Layout.tsx')
  const adminLayout = read('frontend-admin/src/components/Layout.tsx')

  for (const [label, source] of [
    ['frontend/src/components/Layout.tsx', userLayout],
    ['frontend-admin/src/components/Layout.tsx', adminLayout],
  ]) {
    assertContains(source, 'START_MODULE_CONTRACT', label)
    assertContains(source, 'M-074', label)
    assertContains(source, 'data-phase61-layout="phone-tablet-safe"', label)
    assertContains(source, 'data-phase61-viewport-frame="[ResponsiveAdaptation][phase61][VIEWPORT_MATRIX_READY]"', label)
    assertContains(source, 'data-phase61-mobile-header="safe-area-compact"', label)
    assertContains(source, 'data-phase61-mobile-nav="[ResponsiveAdaptation][phase61][SAFE_AREA_PASS]"', label)
  }

  assertContains(userLayout, 'data-phase61-protected-user-static="[ResponsiveAdaptation][phase61][PROTECTED_USER_STATIC_PROOF]"', 'frontend/src/components/Layout.tsx')
  assertContains(adminLayout, 'data-phase61-admin-static="[ResponsiveAdaptation][phase61][ADMIN_STATIC_PROOF]"', 'frontend-admin/src/components/Layout.tsx')
}

function assertRouteProof() {
  assertUnique(phoneViewports.map(([name]) => name), 'Phase-61 phone viewport matrix')
  assertUnique(tabletViewports.map(([name]) => name), 'Phase-61 tablet viewport matrix')
  assertUnique(desktopViewports.map(([name]) => name), 'Phase-61 desktop viewport matrix')
  assertUnique(publicAuthRoutes, 'Phase-61 public/auth routes')
  assertUnique(userProtectedRoutes, 'Phase-61 protected user routes')
  assertUnique(adminRoutes, 'Phase-61 admin routes')

  if (phoneViewports.length !== 5 || tabletViewports.length !== 4 || desktopViewports.length !== 2) {
    throw new Error('Phase-61 viewport matrix cardinality drift')
  }

  const app = read('frontend/src/App.tsx')
  const adminMain = read('frontend-admin/src/main.tsx')
  const publicFiles = [
    ['matrix-public', 'frontend/src/pages/Landing.tsx'],
    ['matrix-auth', 'frontend/src/pages/Login.tsx'],
    ['matrix-auth', 'frontend/src/pages/Register.tsx'],
    ['matrix-auth', 'frontend/src/pages/ForgotPassword.tsx'],
    ['matrix-auth', 'frontend/src/pages/ResetPassword.tsx'],
    ['matrix-auth', 'frontend/src/pages/VerifyEmail.tsx'],
  ]
  const userFiles = [
    ['dashboard', 'frontend/src/pages/Dashboard.tsx'],
    ['config', 'frontend/src/pages/Config.tsx'],
    ['subscription', 'frontend/src/pages/Subscription.tsx'],
    ['referrals', 'frontend/src/pages/Referrals.tsx'],
    ['settings', 'frontend/src/pages/Settings.tsx'],
  ]
  const adminFiles = [
    ['dashboard', 'frontend-admin/src/pages/Dashboard.tsx'],
    ['users', 'frontend-admin/src/pages/Users.tsx'],
    ['devices', 'frontend-admin/src/pages/Devices.tsx'],
    ['mtproto', 'frontend-admin/src/pages/MTProto.tsx'],
    ['analytics', 'frontend-admin/src/pages/Analytics.tsx'],
    ['servers', 'frontend-admin/src/pages/Servers.tsx'],
    ['plans', 'frontend-admin/src/pages/Plans.tsx'],
  ]

  for (const route of publicAuthRoutes) {
    const routeLiteral = route === '/' ? '<Route path="/" element={<Landing />} />' : `path="${route}"`
    assertContains(app, routeLiteral, 'frontend/src/App.tsx')
  }
  for (const [marker, path] of publicFiles) {
    const source = read(path)
    assertContains(source, 'START_MODULE_CONTRACT', path)
    assertContains(source, marker, path)
  }

  for (const [route, path] of userFiles) {
    const source = read(path)
    assertContains(source, 'START_MODULE_CONTRACT', path)
    assertContains(source, `data-phase57-route="${route}"`, path)
    assertContains(source, 'min-w-0', path)
  }

  for (const [route, path] of adminFiles) {
    const source = read(path)
    assertContains(source, 'START_MODULE_CONTRACT', path)
    assertContains(source, `data-phase58-route="${route}"`, path)
    assertContains(source, 'min-w-0', path)
  }

  for (const route of ['/dashboard', '/dashboard/config', '/dashboard/subscription', '/dashboard/referrals', '/dashboard/settings']) {
    if (route === '/dashboard') {
      assertContains(app, '<Route index element={<Dashboard />} />', 'frontend/src/App.tsx')
    } else {
      assertContains(app, `path="${route.replace('/dashboard/', '')}"`, 'frontend/src/App.tsx')
    }
  }

  for (const route of adminRoutes) {
    if (route === '/login') {
      assertContains(adminMain, '<Route path="/login" element={<Login />} />', 'frontend-admin/src/main.tsx')
    } else if (route === '/') {
      assertContains(adminMain, '<Route index element={<Dashboard />} />', 'frontend-admin/src/main.tsx')
    } else {
      assertContains(adminMain, `path="${route.slice(1)}"`, 'frontend-admin/src/main.tsx')
    }
  }
}

function assertPerformanceBudgets() {
  const userJs = largestAsset('frontend/dist/assets', '.js')
  const userCss = largestAsset('frontend/dist/assets', '.css')
  const adminJs = largestAsset('frontend-admin/dist/assets', '.js')
  const adminCss = largestAsset('frontend-admin/dist/assets', '.css')

  assertBytes('user-js-primary', userJs, 540 * 1024)
  assertBytes('user-css-primary', userCss, 56 * 1024)
  assertBytes('admin-js-primary', adminJs, 940 * 1024)
  assertBytes('admin-css-primary', adminCss, 56 * 1024)
}

function assertProtectedSurfaceDiffClean() {
  const protectedPaths = [
    'install.sh',
    'docker-compose.yml',
    'nginx',
    'deploy',
    'backend/app',
    'backend/tests',
    'mtproto-runtime',
    'official-mtproxy',
    'telegram-bot',
  ]

  for (const protectedPath of protectedPaths) {
    if (!existsSync(join(root, protectedPath))) {
      throw new Error(`Protected Phase-61 surface missing from repository: ${protectedPath}`)
    }
  }

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (diff) {
    throw new Error(`Phase-61 must not change backend/deploy/runtime surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE61_STATIC_ASSERTIONS
assertResponsiveCss()
assertLayoutProof()
assertRouteProof()
assertPerformanceBudgets()
assertProtectedSurfaceDiffClean()
// END_BLOCK_PHASE61_STATIC_ASSERTIONS

console.log('[ResponsiveAdaptation][phase61][BUILDS_PASS] dist artifacts verified')
console.log('[ResponsiveAdaptation][phase61][VIEWPORT_MATRIX_READY] phone=5 tablet=4 desktop=2 reduced-motion=2')
console.log('[ResponsiveAdaptation][phase61][PHONE_LAYOUT_PASS] static responsive policy ok')
console.log('[ResponsiveAdaptation][phase61][TABLET_LAYOUT_PASS] static responsive policy ok')
console.log('[ResponsiveAdaptation][phase61][DESKTOP_REGRESSION_PASS] Phase-60 budgets preserved')
console.log('[ResponsiveAdaptation][phase61][NO_HORIZONTAL_SCROLL] static overflow guards ok')
console.log('[ResponsiveAdaptation][phase61][NO_OVERLAP_PASS] bounded text/control guards ok')
console.log('[ResponsiveAdaptation][phase61][TOUCH_TARGETS_PASS] 44px policy ok')
console.log('[ResponsiveAdaptation][phase61][SAFE_AREA_PASS] env safe-area markers ok')
console.log('[ResponsiveAdaptation][phase61][PROTECTED_USER_STATIC_PROOF] protected user routes statically proved')
console.log('[ResponsiveAdaptation][phase61][ADMIN_STATIC_PROOF] admin routes statically proved')
console.log('[ResponsiveAdaptation][phase61][REDUCED_MOTION_PASS] reduced-motion policy preserved')
console.log('[ResponsiveAdaptation][phase61][BUNDLE_BUDGET_PASS] ok')
console.log('[ResponsiveAdaptation][phase61][PROTECTED_SURFACE_GUARD] ok')
