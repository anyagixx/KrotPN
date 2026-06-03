#!/usr/bin/env node
/*
 * FILE: scripts/phase55-premium-art-direction-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static and screenshot-artifact smoke checks for Phase-55 premium Matrix art direction
 *   SCOPE: Shared user/admin premium tokens, balanced palette, compact density, logo asset rules, reduced-motion policy, screenshot artifact proof, and protected deploy surfaces
 *   DEPENDS: M-038, M-069, M-070, M-071, M-072
 *   LINKS: V-M-072, docs/plans/Phase-55.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository text files for static assertions
 *   assertContains - Fails if a file lacks a required marker
 *   assertNotContains - Fails if a file contains a prohibited marker
 *   assertRegexAbsent - Fails if a file matches a prohibited regular expression
 *   assertPngDimensions - Validates screenshot PNG signature, dimensions, and nontrivial byte size
 *   assertLogoAssets - Validates prepared logo asset availability and public favicon/email-logo assets
 *   assertProtectedDeployDiffClean - Fails if Phase-55 touched deploy/install surfaces
 *   main - Runs Phase-55 premium art-direction smoke assertions and prints verification markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-55 premium Matrix art-direction verification gate
 * END_CHANGE_SUMMARY
 */

import { execFileSync } from 'node:child_process'
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'

const root = process.cwd()
const screenshotArg = process.argv.find((arg) => arg.startsWith('--expect-screenshots='))
const screenshotDir = screenshotArg ? resolve(screenshotArg.split('=')[1]) : null
const logoDir = process.env.KROTPN_LOGO_DIR || '/home/truffle/Загрузки/ДЛЯ КРОТА/logos'

function read(relativePath) {
  return readFileSync(join(root, relativePath), 'utf8')
}

function assertContains(source, needle, label) {
  if (!source.includes(needle)) {
    throw new Error(`${label} is missing required Phase-55 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-55 marker: ${needle}`)
  }
}

function assertRegexAbsent(source, regex, label) {
  if (regex.test(source)) {
    throw new Error(`${label} matches prohibited Phase-55 pattern: ${regex}`)
  }
}

function assertFile(path, label, minBytes = 1) {
  if (!existsSync(path)) {
    throw new Error(`${label} does not exist: ${path}`)
  }
  const size = statSync(path).size
  if (size < minBytes) {
    throw new Error(`${label} is too small: ${path} (${size} bytes)`)
  }
}

function assertPngDimensions(path, expectedWidth, expectedHeight) {
  assertFile(path, 'Phase-55 screenshot', 10000)
  const bytes = readFileSync(path)
  const signature = bytes.subarray(0, 8).toString('hex')
  if (signature !== '89504e470d0a1a0a') {
    throw new Error(`Phase-55 screenshot is not a PNG: ${path}`)
  }
  const width = bytes.readUInt32BE(16)
  const height = bytes.readUInt32BE(20)
  if (width !== expectedWidth || height !== expectedHeight) {
    throw new Error(`Phase-55 screenshot dimensions drift: ${path} expected ${expectedWidth}x${expectedHeight}, got ${width}x${height}`)
  }
}

function assertLogoAssets() {
  assertFile(join(root, 'frontend/public/favicon.ico'), 'user favicon', 1000)
  assertFile(join(root, 'frontend-admin/public/favicon.ico'), 'admin favicon', 1000)
  assertFile(join(root, 'frontend/public/brand/email-logo.png'), 'email logo', 1000)

  assertFile(logoDir, 'operator logo source directory')
  const preparedLogoNames = new Set(readdirSync(logoDir))
  for (const required of ['32x32.png', '64x64.png', '128x128.png', '256x256.png', '512x512.png', '1024x1024.png']) {
    if (!preparedLogoNames.has(required)) {
      throw new Error(`Prepared logo source asset is missing: ${required}`)
    }
  }
}

function assertProtectedDeployDiffClean() {
  const protectedPaths = [
    'install.sh',
    'docker-compose.yml',
    'nginx',
    'deploy',
    'deploy/mtproto-de-compose.yml',
    '.env.example',
  ]
  for (const protectedPath of protectedPaths) {
    if (!existsSync(join(root, protectedPath))) {
      throw new Error(`Protected deploy surface missing from repository: ${protectedPath}`)
    }
  }

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (diff) {
    throw new Error(`Phase-55 must not change deploy/install surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE55_STATIC_ASSERTIONS
const userCss = read('frontend/src/index.css')
const adminCss = read('frontend-admin/src/index.css')
const userRuntime = read('frontend/src/components/MatrixBackground.tsx')
const adminRuntime = read('frontend-admin/src/components/MatrixBackground.tsx')

for (const [label, source] of [
  ['frontend/src/index.css', userCss],
  ['frontend-admin/src/index.css', adminCss],
]) {
  assertContains(source, 'START_MODULE_CONTRACT', label)
  assertContains(source, 'M-072', label)
  assertContains(source, 'premium-art-direction', label)
  assertContains(source, 'START_BLOCK_PHASE55_PREMIUM_TOKENS', label)
  assertContains(source, 'END_BLOCK_PHASE55_PREMIUM_TOKENS', label)
  assertContains(source, '--matrix-green', label)
  assertContains(source, '--matrix-cyan', label)
  assertContains(source, '--matrix-magenta', label)
  assertContains(source, '--matrix-amber', label)
  assertContains(source, '--matrix-red', label)
  assertContains(source, '--premium-black', label)
  assertContains(source, '--premium-deep-black', label)
  assertContains(source, '--premium-surface', label)
  assertContains(source, '--premium-surface-strong', label)
  assertContains(source, '--premium-surface-muted', label)
  assertContains(source, '--premium-line-cyan', label)
  assertContains(source, '--premium-line-strong', label)
  assertContains(source, '--premium-focus-ring', label)
  assertContains(source, '--premium-type-display', label)
  assertContains(source, '--premium-type-ui', label)
  assertContains(source, '--premium-type-kpi', label)
  assertContains(source, '--premium-type-data', label)
  assertContains(source, '--premium-font-data', label)
  assertContains(source, '--premium-density-sm', label)
  assertContains(source, '--premium-density-md', label)
  assertContains(source, '--premium-logo-min', label)
  assertContains(source, '--premium-logo-safe-space', label)
  assertContains(source, '--premium-logo-email-size', label)
  assertContains(source, '@media (prefers-reduced-motion: reduce)', label)
  assertContains(source, '.matrix-visual-shell::before', label)
  assertContains(source, '.matrix-canvas', label)
  assertContains(source, '.matrix-scanline-overlay', label)
  assertContains(source, ':focus-visible', label)
  assertContains(source, 'pointer-events: none', label)
  assertContains(source, 'letter-spacing: 0', label)

  for (const prohibited of [
    'radial-gradient(',
    'rounded-[32px]',
    'rounded-[24px]',
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

for (const [label, source] of [
  ['frontend/src/components/MatrixBackground.tsx', userRuntime],
  ['frontend-admin/src/components/MatrixBackground.tsx', adminRuntime],
]) {
  assertContains(source, 'prefers-reduced-motion: reduce', label)
  assertContains(source, 'data-matrix-canvas', label)
  assertContains(source, '[MatrixVisualRuntime][motionPolicy][REDUCED_MOTION]', label)
  assertContains(source, '[MatrixVisualRuntime][fallback][CANVAS_CONTEXT_UNAVAILABLE]', label)
}

assertLogoAssets()
assertProtectedDeployDiffClean()

if (screenshotDir) {
  const screenshots = [
    ['user-login-360x740.png', 360, 740],
    ['user-login-390x844.png', 390, 844],
    ['user-login-430x932.png', 430, 932],
    ['user-login-768x1024.png', 768, 1024],
    ['admin-login-1024x768.png', 1024, 768],
    ['admin-login-1440x900.png', 1440, 900],
    ['user-login-reduced-motion-390x844.png', 390, 844],
    ['admin-login-reduced-motion-390x844.png', 390, 844],
  ]
  for (const [name, width, height] of screenshots) {
    assertPngDimensions(join(screenshotDir, name), width, height)
  }
}
// END_BLOCK_PHASE55_STATIC_ASSERTIONS

console.log('[PremiumArtDirection][phase55][TOKENS_READY] ok')
console.log('[PremiumArtDirection][phase55][BALANCED_PALETTE] ok')
console.log('[PremiumArtDirection][phase55][DENSITY_SAFE] ok')
console.log('[PremiumArtDirection][phase55][LOGO_RULES_READY] ok')
console.log('[PremiumArtDirection][phase55][REDUCED_MOTION_SAFE] ok')
if (screenshotDir) {
  console.log('[PremiumArtDirection][phase55][SCREENSHOT_MATRIX_REVIEWED] ok')
}
console.log('[PremiumArtDirection][phase55][PROTECTED_SURFACE_GUARD] ok')
