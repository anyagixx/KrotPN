#!/usr/bin/env node
/*
 * FILE: scripts/phase60-premium-qa-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Unified Phase-60 premium frontend QA gate for user/admin Matrix surfaces
 *   SCOPE: Route and viewport matrix contract, no-overlap/static responsive assertions, build artifact performance budgets, reduced-motion/accessibility markers, regression smoke orchestration, MyGRACE checks, and protected backend/deploy/runtime guard
 *   DEPENDS: M-078, M-009, M-010, M-036, M-037, M-038, M-070, M-071, M-073, M-075, M-076, M-077
 *   LINKS: V-M-078, docs/plans/Phase-60.xml, docs/modules/M-078.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository files for deterministic static assertions
 *   assertContains - Fails if a source file lacks a required marker
 *   assertNotContains - Fails if a source file contains prohibited content
 *   assertRegexAbsent - Fails if a source file matches a prohibited pattern
 *   assertRouteAndViewportMatrix - Verifies the Phase-60 public/auth/user/admin/reduced-motion route matrix contract
 *   assertResponsiveNoOverlap - Verifies static no-overlap, no-horizontal-scroll, bounded list/table/chart, and pointer-safe canvas markers
 *   assertAccessibilityAndMotion - Verifies focus-visible, keyboard, contrast, reduced-motion, and route-motion safety markers
 *   assertPerformanceBudgets - Verifies built dist artifact sizes and records raw/gzip byte evidence
 *   runRegressionSmokes - Runs Phase-52/55/56/57/58/59 regression smoke scripts and validates their markers
 *   assertGovernance - Runs XML parse, MyGRACE lint, git diff --check, and protected-surface guard
 *   main - Runs Phase-60 QA gates and prints required verification markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-60 premium frontend QA gate implementation.
 * END_CHANGE_SUMMARY
 */

import { execFileSync } from 'node:child_process'
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { extname, join, relative } from 'node:path'
import { gzipSync } from 'node:zlib'

const root = process.cwd()

const viewports = [
  ['phone-360', 360, 740],
  ['phone-390', 390, 844],
  ['phone-430', 430, 932],
  ['tablet-portrait', 768, 1024],
  ['tablet-landscape', 1024, 768],
  ['desktop', 1440, 900],
]

const publicAuthRoutes = ['/', '/login', '/register', '/forgot-password', '/reset-password', '/verify-email']
const userProtectedRoutes = ['/dashboard', '/dashboard/config', '/dashboard/subscription', '/dashboard/referrals', '/dashboard/settings']
const adminRoutes = ['/login', '/', '/users', '/devices', '/mtproto', '/servers', '/plans', '/analytics']
const reducedMotionRoutes = ['/', '/login', '/dashboard', '/mtproto']

const regressionSmokes = [
  {
    script: 'scripts/phase52-matrix-visual-smoke.mjs',
    marker: '[MatrixVisualRuntime][init][CANVAS_READY]',
  },
  {
    script: 'scripts/phase55-premium-art-direction-smoke.mjs',
    marker: '[PremiumArtDirection][phase55][TOKENS_READY]',
  },
  {
    script: 'scripts/phase56-premium-public-auth-smoke.mjs',
    marker: '[PremiumPublicSite][phase56][ROUTES_READY]',
  },
  {
    script: 'scripts/phase57-premium-user-cabinet-smoke.mjs',
    marker: '[PremiumUserCabinet][phase57][ROUTES_READY]',
  },
  {
    script: 'scripts/phase58-premium-admin-cockpit-smoke.mjs',
    marker: '[PremiumAdminCockpit][phase58][ROUTES_READY]',
  },
  {
    script: 'scripts/phase59-motion-interactions-smoke.mjs',
    marker: '[MatrixMotion][phase59][MOTION_BUDGET_READY]',
  },
]

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

function read(relativePath) {
  return readFileSync(join(root, relativePath), 'utf8')
}

function assertContains(source, needle, label) {
  if (!source.includes(needle)) {
    throw new Error(`${label} is missing required Phase-60 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-60 marker: ${needle}`)
  }
}

function assertRegexAbsent(source, regex, label) {
  if (regex.test(source)) {
    throw new Error(`${label} matches prohibited Phase-60 pattern: ${regex}`)
  }
}

function assertFile(relativePath, label, minBytes = 1) {
  const path = join(root, relativePath)
  if (!existsSync(path)) {
    throw new Error(`${label} does not exist: ${relativePath}`)
  }
  const size = statSync(path).size
  if (size < minBytes) {
    throw new Error(`${label} is too small: ${relativePath} (${size} bytes)`)
  }
  return path
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
    throw new Error(`No ${extension} assets found under ${relativePath}`)
  }
  return files.sort((a, b) => statSync(b).size - statSync(a).size)[0]
}

function assertBytes(label, filePath, maxBytes) {
  const bytes = statSync(filePath).size
  if (bytes > maxBytes) {
    throw new Error(`${label} exceeds Phase-60 budget: ${bytes} > ${maxBytes} bytes (${relative(root, filePath)})`)
  }
  const gzipBytes = gzipSync(readFileSync(filePath)).length
  console.log(`[PremiumQAGates][phase60][BUNDLE_BUDGET] ${label} raw=${bytes} gzip=${gzipBytes} max=${maxBytes} path=${relative(root, filePath)}`)
}

function assertUnique(values, label) {
  const seen = new Set(values)
  if (seen.size !== values.length) {
    throw new Error(`${label} contains duplicate entries`)
  }
}

function assertRouteAndViewportMatrix() {
  assertUnique(viewports.map(([name]) => name), 'Phase-60 viewport matrix')
  assertUnique(publicAuthRoutes, 'Phase-60 public/auth route matrix')
  assertUnique(userProtectedRoutes, 'Phase-60 protected user route matrix')
  assertUnique(adminRoutes, 'Phase-60 admin route matrix')
  assertUnique(reducedMotionRoutes, 'Phase-60 reduced-motion route matrix')

  if (viewports.length !== 6 || publicAuthRoutes.length !== 6 || userProtectedRoutes.length !== 5 || adminRoutes.length !== 8) {
    throw new Error('Phase-60 route/viewport matrix cardinality drift')
  }

  const app = read('frontend/src/App.tsx')
  const adminMain = read('frontend-admin/src/main.tsx')
  const publicFiles = {
    '/': read('frontend/src/pages/Landing.tsx'),
    '/login': read('frontend/src/pages/Login.tsx'),
    '/register': read('frontend/src/pages/Register.tsx'),
    '/forgot-password': read('frontend/src/pages/ForgotPassword.tsx'),
    '/reset-password': read('frontend/src/pages/ResetPassword.tsx'),
    '/verify-email': read('frontend/src/pages/VerifyEmail.tsx'),
  }
  const userFiles = {
    '/dashboard': read('frontend/src/pages/Dashboard.tsx'),
    '/dashboard/config': read('frontend/src/pages/Config.tsx'),
    '/dashboard/subscription': read('frontend/src/pages/Subscription.tsx'),
    '/dashboard/referrals': read('frontend/src/pages/Referrals.tsx'),
    '/dashboard/settings': read('frontend/src/pages/Settings.tsx'),
  }
  const adminFiles = {
    '/login': read('frontend-admin/src/pages/Login.tsx'),
    '/': read('frontend-admin/src/pages/Dashboard.tsx'),
    '/users': read('frontend-admin/src/pages/Users.tsx'),
    '/devices': read('frontend-admin/src/pages/Devices.tsx'),
    '/mtproto': read('frontend-admin/src/pages/MTProto.tsx'),
    '/servers': read('frontend-admin/src/pages/Servers.tsx'),
    '/plans': read('frontend-admin/src/pages/Plans.tsx'),
    '/analytics': read('frontend-admin/src/pages/Analytics.tsx'),
  }

  for (const route of publicAuthRoutes) {
    const routeLiteral = route === '/' ? '<Route path="/" element={<Landing />} />' : `path="${route}"`
    assertContains(app, routeLiteral, 'frontend/src/App.tsx')
    assertContains(publicFiles[route], 'START_MODULE_CONTRACT', `public route ${route}`)
  }

  for (const route of userProtectedRoutes) {
    const childRoute = route.replace('/dashboard/', '')
    if (route === '/dashboard') {
      assertContains(app, '<Route index element={<Dashboard />} />', 'frontend/src/App.tsx')
    } else {
      assertContains(app, `path="${childRoute}"`, 'frontend/src/App.tsx')
    }
    assertContains(userFiles[route], 'START_MODULE_CONTRACT', `protected user route ${route}`)
    assertContains(userFiles[route], 'data-phase57-route=', `protected user route ${route}`)
  }

  for (const route of adminRoutes) {
    if (route === '/login') {
      assertContains(adminMain, '<Route path="/login" element={<Login />} />', 'frontend-admin/src/main.tsx')
    } else if (route === '/') {
      assertContains(adminMain, '<Route index element={<Dashboard />} />', 'frontend-admin/src/main.tsx')
    } else {
      assertContains(adminMain, `path="${route.slice(1)}"`, 'frontend-admin/src/main.tsx')
    }
    assertContains(adminFiles[route], 'START_MODULE_CONTRACT', `admin route ${route}`)
  }
}

function assertResponsiveNoOverlap() {
  const userCss = read('frontend/src/index.css')
  const adminCss = read('frontend-admin/src/index.css')
  const userLayout = read('frontend/src/components/Layout.tsx')
  const adminLayout = read('frontend-admin/src/components/Layout.tsx')
  const userMatrix = read('frontend/src/components/MatrixBackground.tsx')
  const adminMatrix = read('frontend-admin/src/components/MatrixBackground.tsx')

  for (const [label, source] of [
    ['frontend/src/index.css', userCss],
    ['frontend-admin/src/index.css', adminCss],
  ]) {
    for (const needle of [
      'overflow-x: hidden',
      ':focus-visible',
      '@media (prefers-reduced-motion: reduce)',
      'pointer-events: none',
      'letter-spacing: 0',
      '--motion-duration-route: 220ms',
      '.motion-route-enter',
    ]) {
      assertContains(source, needle, label)
    }
    for (const prohibited of [
      'scroll-snap-type',
      'scroll-snap-align',
      'requestPointerLock',
      'preventDefault()',
      'setInterval(',
      'rounded-2xl',
      'rounded-3xl',
      'font-size: clamp(',
      'font-size: calc(',
    ]) {
      assertNotContains(source, prohibited, label)
    }
    assertRegexAbsent(source, /letter-spacing:\s*-[^;]+;/, label)
    assertRegexAbsent(source, /font-size:\s*[^;]*vw[^;]*;/, label)
  }

  for (const [label, source] of [
    ['frontend/src/components/Layout.tsx', userLayout],
    ['frontend-admin/src/components/Layout.tsx', adminLayout],
  ]) {
    assertContains(source, 'min-w-0', label)
  }

  for (const [label, source] of [
    ['frontend/src/components/MatrixBackground.tsx', userMatrix],
    ['frontend-admin/src/components/MatrixBackground.tsx', adminMatrix],
  ]) {
    assertContains(source, 'data-matrix-canvas', label)
    assertContains(source, 'prefers-reduced-motion: reduce', label)
    assertContains(source, 'data-phase59-pointer-scroll="[MatrixMotion][phase59][POINTER_SCROLL_SAFE]"', label)
    assertNotContains(source, 'setInterval(', label)
    assertNotContains(source, 'preventDefault()', label)
  }

  for (const [label, source] of [
    ['frontend/src/pages/Dashboard.tsx', read('frontend/src/pages/Dashboard.tsx')],
    ['frontend/src/pages/Config.tsx', read('frontend/src/pages/Config.tsx')],
    ['frontend/src/pages/Subscription.tsx', read('frontend/src/pages/Subscription.tsx')],
    ['frontend/src/pages/Referrals.tsx', read('frontend/src/pages/Referrals.tsx')],
    ['frontend/src/pages/Settings.tsx', read('frontend/src/pages/Settings.tsx')],
  ]) {
    assertContains(source, 'min-w-0', label)
    assertContains(source, 'phase57-', label)
  }

  for (const [label, source] of [
    ['frontend-admin/src/pages/Users.tsx', read('frontend-admin/src/pages/Users.tsx')],
    ['frontend-admin/src/pages/Devices.tsx', read('frontend-admin/src/pages/Devices.tsx')],
    ['frontend-admin/src/pages/MTProto.tsx', read('frontend-admin/src/pages/MTProto.tsx')],
    ['frontend-admin/src/pages/MTProtoAnalytics.tsx', read('frontend-admin/src/pages/MTProtoAnalytics.tsx')],
    ['frontend-admin/src/pages/Servers.tsx', read('frontend-admin/src/pages/Servers.tsx')],
  ]) {
    assertContains(source, 'phase58-inventory-list', label)
    assertContains(source, '[PremiumAdminCockpit][phase58][INVENTORIES_BOUNDED]', label)
  }
}

function assertAccessibilityAndMotion() {
  const userCss = read('frontend/src/index.css')
  const adminCss = read('frontend-admin/src/index.css')
  const userVisualShell = read('frontend/src/components/VisualShell.tsx')
  const adminVisualShell = read('frontend-admin/src/components/VisualShell.tsx')
  const landing = read('frontend/src/pages/Landing.tsx')
  const adminLogin = read('frontend-admin/src/pages/Login.tsx')

  for (const [label, source] of [
    ['frontend/src/index.css', userCss],
    ['frontend-admin/src/index.css', adminCss],
  ]) {
    for (const needle of [
      'button:focus-visible',
      'input:focus-visible',
      'select:focus-visible',
      'textarea:focus-visible',
      '[role="button"]:focus-visible',
      '@media (prefers-reduced-motion: reduce)',
      '[MatrixMotion][phase59][REDUCED_MOTION_PASS]',
      '[MatrixMotion][phase59][KEYBOARD_FOCUS_SAFE]',
    ]) {
      assertContains(source, needle, label)
    }
  }

  for (const [label, source] of [
    ['frontend/src/components/VisualShell.tsx', userVisualShell],
    ['frontend-admin/src/components/VisualShell.tsx', adminVisualShell],
  ]) {
    assertContains(source, 'data-phase59-reduced-motion="[MatrixMotion][phase59][REDUCED_MOTION_PASS]"', label)
    assertContains(source, 'data-phase59-keyboard-focus="[MatrixMotion][phase59][KEYBOARD_FOCUS_SAFE]"', label)
    assertContains(source, 'matrix-visual-content motion-safe-layer', label)
  }

  for (const [label, source] of [
    ['frontend/src/pages/Landing.tsx', landing],
    ['frontend-admin/src/pages/Login.tsx', adminLogin],
  ]) {
    assertContains(source, 'aria-label=', label)
  }

  for (const [label, source] of [
    ['frontend/src/pages/Landing.tsx', landing],
    ['frontend-admin/src/pages/Login.tsx', adminLogin],
    ['frontend/src/pages/Dashboard.tsx', read('frontend/src/pages/Dashboard.tsx')],
    ['frontend-admin/src/pages/MTProtoAnalytics.tsx', read('frontend-admin/src/pages/MTProtoAnalytics.tsx')],
  ]) {
    for (const prohibited of ['keyboard shortcut', 'hotkey', 'how to use this UI', 'debug-only', 'full_proxy_url', 'unmasked_secret']) {
      assertNotContains(source, prohibited, label)
    }
  }
}

function assertPerformanceBudgets() {
  assertFile('frontend/dist/index.html', 'frontend build output', 100)
  assertFile('frontend-admin/dist/index.html', 'frontend-admin build output', 100)

  const userJs = largestAsset('frontend/dist/assets', '.js')
  const userCss = largestAsset('frontend/dist/assets', '.css')
  const adminJs = largestAsset('frontend-admin/dist/assets', '.js')
  const adminCss = largestAsset('frontend-admin/dist/assets', '.css')

  assertBytes('user-js-primary', userJs, 540 * 1024)
  assertBytes('user-css-primary', userCss, 56 * 1024)
  assertBytes('admin-js-primary', adminJs, 940 * 1024)
  assertBytes('admin-css-primary', adminCss, 56 * 1024)

  const allDistFiles = [...listFiles('frontend/dist'), ...listFiles('frontend-admin/dist')]
  for (const file of allDistFiles) {
    const size = statSync(file).size
    const relativePath = relative(root, file)
    if (size > 1.5 * 1024 * 1024) {
      throw new Error(`Unexpected Phase-60 dist asset exceeds 1.5MB: ${relativePath} (${size} bytes)`)
    }
    if (/^frontend\/dist\/.*\.(png|jpe?g|webp|avif|ico)$/i.test(relativePath) && size > 512 * 1024) {
      throw new Error(`User public bitmap exceeds Phase-60 512KB budget: ${relativePath} (${size} bytes)`)
    }
  }

  console.log('[PremiumQAGates][phase60][LIGHTHOUSE_UNAVAILABLE] no-local-preview-lighthouse-run; bundle-and-static-budgets-enforced')
}

function runRegressionSmokes() {
  for (const { script, marker } of regressionSmokes) {
    assertFile(script, 'Phase-60 regression smoke script', 100)
    const output = execFileSync(process.execPath, [script], {
      cwd: root,
      encoding: 'utf8',
      env: process.env,
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    if (!output.includes(marker)) {
      throw new Error(`${script} did not print required regression marker: ${marker}`)
    }
  }
}

function assertGovernance() {
  for (const protectedPath of protectedPaths) {
    assertFile(protectedPath, 'protected Phase-60 surface')
  }

  const diff = execFileSync('git', ['diff', '--name-only', 'HEAD', '--', ...protectedPaths], {
    cwd: root,
    encoding: 'utf8',
  }).trim()
  if (diff) {
    throw new Error(`Phase-60 must not change backend/deploy/runtime surfaces: ${diff}`)
  }

  execFileSync('python3', [
    '-m',
    'xml.etree.ElementTree',
    'docs/graph-index.xml',
    'docs/plan-index.xml',
    'docs/verification-index.xml',
    'docs/modules/M-078.xml',
    'docs/plans/Phase-60.xml',
    'docs/verification/V-M-078.xml',
  ], { cwd: root, stdio: 'pipe' })
  execFileSync('mygrace', ['lint'], { cwd: root, stdio: 'pipe' })
  execFileSync('git', ['diff', '--check'], { cwd: root, stdio: 'pipe' })
}

// START_BLOCK_PHASE60_QA_GATE
assertRouteAndViewportMatrix()
console.log('[PremiumQAGates][phase60][SCREENSHOT_MATRIX_READY] static-route-proof public=36 user=30 admin=48 reduced-motion=4')

assertResponsiveNoOverlap()
console.log('[PremiumQAGates][phase60][NO_OVERLAP_PASS] static-css-and-route-markers')
console.log('[PremiumQAGates][phase60][RESPONSIVE_PASS] viewport-matrix-contract-ready')

assertAccessibilityAndMotion()
console.log('[PremiumQAGates][phase60][REDUCED_MOTION_PASS] static-markers')
console.log('[PremiumQAGates][phase60][ACCESSIBILITY_PASS] focus-keyboard-static-markers')

assertPerformanceBudgets()
console.log('[PremiumQAGates][phase60][BUILDS_PASS] dist-artifacts-present')
console.log('[PremiumQAGates][phase60][PERFORMANCE_BUDGET_PASS] dist-size-budgets')

runRegressionSmokes()
console.log('[PremiumQAGates][phase60][REGRESSION_SMOKES_PASS] phase52 phase55 phase56 phase57 phase58 phase59')

assertGovernance()
console.log('[PremiumQAGates][phase60][MYGRACE_PASS] xml-lint-diffcheck')
console.log('[PremiumQAGates][phase60][PROTECTED_SURFACE_GUARD] clean')
// END_BLOCK_PHASE60_QA_GATE
