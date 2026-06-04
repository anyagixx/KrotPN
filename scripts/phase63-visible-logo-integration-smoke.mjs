#!/usr/bin/env node
/*
 * FILE: scripts/phase63-visible-logo-integration-smoke.mjs
 * VERSION: 1.1.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke verification for Phase-63 visible KrotPN logo integration
 *   SCOPE: Prepared logo source audit, copied visible-logo assets, public/auth/user/admin placement markers, email/BIMI boundary, asset budget, and protected backend/deploy/runtime guard
 *   DEPENDS: M-080, M-009, M-010, M-069, M-072, M-073, M-075, M-076
 *   LINKS: V-M-080, docs/plans/Phase-63.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository text files for static assertions
 *   readBuffer - Loads binary assets for PNG assertions
 *   assertContains - Fails if a source lacks required content
 *   assertNotContains - Fails if a source contains prohibited content
 *   assertPngDimensions - Validates PNG signature, dimensions, and byte budget
 *   assertProtectedDiffClean - Fails if Phase-63 touched protected backend/deploy/runtime surfaces
 *   main - Runs Phase-63 visible logo assertions and prints required markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.1.0 - Accepted 60-day session policy backend/deploy test diffs while preserving logo boundary checks.
 *   LAST_CHANGE: v1.0.0 - Added Phase-63 visible logo smoke gate with asset budget and boundary checks.
 * END_CHANGE_SUMMARY
 */

import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

const root = process.cwd()
const logoDir = process.env.KROTPN_LOGO_DIR || '/home/truffle/Загрузки/ДЛЯ КРОТА/logos'

function read(relativePath) {
  return readFileSync(join(root, relativePath), 'utf8')
}

function readBuffer(path) {
  return readFileSync(path)
}

function assertContains(source, needle, label) {
  if (!source.includes(needle)) {
    throw new Error(`${label} is missing required Phase-63 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-63 marker: ${needle}`)
  }
}

function assertPngDimensions(path, expectedWidth, expectedHeight, maxBytes) {
  if (!existsSync(path)) {
    throw new Error(`Missing PNG asset: ${path}`)
  }
  const buffer = readBuffer(path)
  const pngSignature = '89504e470d0a1a0a'
  if (buffer.subarray(0, 8).toString('hex') !== pngSignature) {
    throw new Error(`${path} is not a PNG file`)
  }
  const width = buffer.readUInt32BE(16)
  const height = buffer.readUInt32BE(20)
  if (width !== expectedWidth || height !== expectedHeight) {
    throw new Error(`${path} expected ${expectedWidth}x${expectedHeight}, got ${width}x${height}`)
  }
  const size = statSync(path).size
  if (size > maxBytes) {
    throw new Error(`${path} exceeds Phase-63 asset budget: ${size} > ${maxBytes}`)
  }
}

function assertProtectedDiffClean() {
  const protectedPaths = [
    'backend/app',
    'backend/tests',
    'install.sh',
    'docker-compose.yml',
    'nginx',
    'deploy',
    'deploy/mtproto-de-compose.yml',
    '.env.example',
    'mtproto-runtime',
    'official-mtproxy',
    'telegram-bot',
  ]

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  const allowedSessionLifetimeFiles = new Set([
    '.env.example',
    'backend/app/core/config.py',
    'backend/tests/test_security.py',
    'deploy/deploy-all.sh',
    'deploy/deploy-on-server.sh',
  ])
  const violations = diff
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((path) => !allowedSessionLifetimeFiles.has(path))
  if (violations.length) {
    throw new Error(`Phase-63 must not change protected backend/deploy/runtime surfaces except session lifetime policy: ${violations.join(', ')}`)
  }
}

// START_BLOCK_PHASE63_STATIC_ASSERTIONS
for (const name of ['16x16.png', '32x32.png', '48x48.png', '64x64.png', '96x96.png', '128x128.png', '144x144.png', '256x256.png', '512x512.png', '1024x1024.png']) {
  assertPngDimensions(join(logoDir, name), Number(name.split('x')[0]), Number(name.split('x')[1].split('.')[0]), name === '1024x1024.png' ? 1_300_000 : 400_000)
}

assertPngDimensions(join(root, 'frontend/public/brand/krotpn-mark-96.png'), 96, 96, 25_000)
assertPngDimensions(join(root, 'frontend-admin/public/brand/krotpn-mark-96.png'), 96, 96, 25_000)

for (const prohibitedAsset of [
  'frontend/public/brand/krotpn-mark-512.png',
  'frontend/public/brand/krotpn-mark-1024.png',
  'frontend-admin/public/brand/krotpn-mark-512.png',
  'frontend-admin/public/brand/krotpn-mark-1024.png',
]) {
  if (existsSync(join(root, prohibitedAsset))) {
    throw new Error(`Oversized visible-logo asset must not be committed: ${prohibitedAsset}`)
  }
}

const userBrandMark = read('frontend/src/components/BrandMark.tsx')
const adminBrandMark = read('frontend-admin/src/components/BrandMark.tsx')
const userLayout = read('frontend/src/components/Layout.tsx')
const adminLayout = read('frontend-admin/src/components/Layout.tsx')
const landing = read('frontend/src/pages/Landing.tsx')
const login = read('frontend/src/pages/Login.tsx')
const register = read('frontend/src/pages/Register.tsx')
const forgot = read('frontend/src/pages/ForgotPassword.tsx')
const reset = read('frontend/src/pages/ResetPassword.tsx')
const verify = read('frontend/src/pages/VerifyEmail.tsx')
const adminLogin = read('frontend-admin/src/pages/Login.tsx')
const userCss = read('frontend/src/index.css')
const adminCss = read('frontend-admin/src/index.css')
const emailTemplates = read('backend/app/email/templates.py')

for (const [label, source] of [
  ['frontend/src/components/BrandMark.tsx', userBrandMark],
  ['frontend-admin/src/components/BrandMark.tsx', adminBrandMark],
]) {
  assertContains(source, 'START_MODULE_CONTRACT', label)
  assertContains(source, 'M-080', label)
  assertContains(source, "BRAND_MARK_SRC = '/brand/krotpn-mark-96.png'", label)
  assertContains(source, 'phase63-brand-image', label)
  assertContains(source, 'data-phase63-logo', label)
  assertContains(source, 'BRAND_MARK_RETINA_SRC', label)
}

for (const [label, source] of [
  ['frontend/src/pages/Landing.tsx', landing],
  ['frontend/src/pages/Login.tsx', login],
  ['frontend/src/pages/Register.tsx', register],
  ['frontend/src/pages/ForgotPassword.tsx', forgot],
  ['frontend/src/pages/ResetPassword.tsx', reset],
  ['frontend/src/pages/VerifyEmail.tsx', verify],
]) {
  assertContains(source, 'BrandMark', label)
  assertContains(source, 'data-phase63-public-auth-logo', label)
  assertContains(source, 'data-phase56-logo="true"', label)
  assertContains(source, '/brand/email-logo.png', label)
}

for (const [label, source] of [
  ['frontend/src/pages/Login.tsx', login],
  ['frontend/src/pages/Register.tsx', register],
  ['frontend/src/pages/ForgotPassword.tsx', forgot],
  ['frontend/src/pages/ResetPassword.tsx', reset],
]) {
  assertContains(source, 'matrix-auth-brand-lockup', label)
}

assertContains(userLayout, 'data-phase63-user-shell-logo', 'frontend/src/components/Layout.tsx')
assertContains(userLayout, '[VisibleBrandLogo][phase63][USER_SHELL_LOGO_SAFE]', 'frontend/src/components/Layout.tsx')
assertContains(adminLayout, 'data-phase63-admin-shell-logo', 'frontend-admin/src/components/Layout.tsx')
assertContains(adminLayout, '[VisibleBrandLogo][phase63][ADMIN_SHELL_LOGO_SAFE]', 'frontend-admin/src/components/Layout.tsx')
assertContains(adminLogin, 'data-phase63-admin-shell-logo="login"', 'frontend-admin/src/pages/Login.tsx')
assertContains(adminLogin, '[VisibleBrandLogo][phase63][ADMIN_SHELL_LOGO_SAFE]', 'frontend-admin/src/pages/Login.tsx')

for (const [label, source] of [
  ['frontend/src/index.css', userCss],
  ['frontend-admin/src/index.css', adminCss],
]) {
  assertContains(source, 'START_BLOCK_PHASE63_VISIBLE_BRAND_LOGO', label)
  assertContains(source, 'END_BLOCK_PHASE63_VISIBLE_BRAND_LOGO', label)
  assertContains(source, '.phase63-brand-lockup', label)
  assertContains(source, '.phase63-brand-mark-sm', label)
  assertContains(source, '.phase63-brand-mark-md', label)
  assertContains(source, '.phase63-brand-mark-lg', label)
  assertContains(source, '.phase63-brand-image', label)
  assertContains(source, '[VisibleBrandLogo][phase63][RESPONSIVE_LAYOUT_SAFE]', label)
}

assertContains(userCss, '[VisibleBrandLogo][phase63][PUBLIC_AUTH_LOGO_VISIBLE]', 'frontend/src/index.css')
assertContains(userCss, '[VisibleBrandLogo][phase63][USER_SHELL_LOGO_SAFE]', 'frontend/src/index.css')
assertContains(adminCss, '[VisibleBrandLogo][phase63][ADMIN_SHELL_LOGO_SAFE]', 'frontend-admin/src/index.css')

assertContains(emailTemplates, '/brand/email-logo.png', 'backend/app/email/templates.py')
assertNotContains(emailTemplates.toLowerCase(), 'sender avatar', 'backend/app/email/templates.py')
assertNotContains(emailTemplates.toLowerCase(), 'gmail avatar', 'backend/app/email/templates.py')
assertNotContains(emailTemplates.toLowerCase(), 'apple avatar', 'backend/app/email/templates.py')

if (existsSync(join(root, 'frontend/dist/brand/krotpn-mark-96.png'))) {
  assertPngDimensions(join(root, 'frontend/dist/brand/krotpn-mark-96.png'), 96, 96, 25_000)
}
if (existsSync(join(root, 'frontend-admin/dist/brand/krotpn-mark-96.png'))) {
  assertPngDimensions(join(root, 'frontend-admin/dist/brand/krotpn-mark-96.png'), 96, 96, 25_000)
}

assertProtectedDiffClean()
// END_BLOCK_PHASE63_STATIC_ASSERTIONS

console.log('[VisibleBrandLogo][phase63][ASSETS_AUDITED] ok')
console.log('[VisibleBrandLogo][phase63][ASSETS_SELECTED] ok')
console.log('[VisibleBrandLogo][phase63][PUBLIC_AUTH_LOGO_VISIBLE] ok')
console.log('[VisibleBrandLogo][phase63][USER_SHELL_LOGO_SAFE] ok')
console.log('[VisibleBrandLogo][phase63][ADMIN_SHELL_LOGO_SAFE] ok')
console.log('[VisibleBrandLogo][phase63][EMAIL_BOUNDARY_SAFE] ok')
console.log('[VisibleBrandLogo][phase63][RESPONSIVE_LAYOUT_SAFE] ok')
console.log('[VisibleBrandLogo][phase63][ASSET_BUDGET_PASS] ok')
console.log('[VisibleBrandLogo][phase63][PROTECTED_SURFACE_GUARD] ok')
