#!/usr/bin/env node
/*
 * FILE: scripts/phase51-brand-assets-smoke.mjs
 * VERSION: 1.0.1
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke checks for Phase-51 favicon and Resend email logo branding
 *   SCOPE: Frontend/admin favicon assets, PWA icon assets, email logo asset, email template binding, README notes, and protected deploy surfaces
 *   DEPENDS: M-069, M-009, M-010, M-040, M-062, M-067
 *   LINKS: V-M-069
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository text files for static assertions
 *   readBuffer - Loads binary assets for signature and dimension assertions
 *   assertContains - Fails if a file lacks a required marker
 *   assertPngDimensions - Fails if a PNG asset is missing or has unexpected dimensions
 *   assertIcoFile - Fails if favicon.ico is not an ICO container
 *   assertProtectedDeployDiffClean - Fails if Phase-51 touched deploy/install surfaces
 *   main - Runs Phase-51 brand asset smoke assertions with optional dist-copy checks
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.1 - Accepted Phase-66 larger 128px email logo rendering while preserving public asset boundary
 *   LAST_CHANGE: v1.0.0 - Added Phase-51 brand asset static smoke gate
 * END_CHANGE_SUMMARY
 */

import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const root = process.cwd()
const expectDist = process.argv.includes('--expect-dist')

function read(relativePath) {
  return readFileSync(join(root, relativePath), 'utf8')
}

function readBuffer(relativePath) {
  return readFileSync(join(root, relativePath))
}

function assertContains(source, needle, label) {
  if (!source.includes(needle)) {
    throw new Error(`${label} is missing required Phase-51 marker: ${needle}`)
  }
}

function assertPngDimensions(relativePath, expectedWidth, expectedHeight) {
  if (!existsSync(join(root, relativePath))) {
    throw new Error(`Missing PNG asset: ${relativePath}`)
  }
  const buffer = readBuffer(relativePath)
  const pngSignature = '89504e470d0a1a0a'
  if (buffer.subarray(0, 8).toString('hex') !== pngSignature) {
    throw new Error(`${relativePath} is not a PNG file`)
  }
  const width = buffer.readUInt32BE(16)
  const height = buffer.readUInt32BE(20)
  if (width !== expectedWidth || height !== expectedHeight) {
    throw new Error(`${relativePath} expected ${expectedWidth}x${expectedHeight}, got ${width}x${height}`)
  }
}

function assertIcoFile(relativePath) {
  if (!existsSync(join(root, relativePath))) {
    throw new Error(`Missing ICO asset: ${relativePath}`)
  }
  const buffer = readBuffer(relativePath)
  if (buffer.length < 6 || buffer.readUInt16LE(0) !== 0 || buffer.readUInt16LE(2) !== 1) {
    throw new Error(`${relativePath} is not an ICO file`)
  }
  if (buffer.readUInt16LE(4) < 1) {
    throw new Error(`${relativePath} must contain at least one favicon image`)
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
    throw new Error(`Phase-51 must not change deploy/install surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE51_STATIC_ASSERTIONS
assertIcoFile('frontend/public/favicon.ico')
assertIcoFile('frontend-admin/public/favicon.ico')
assertPngDimensions('frontend/public/favicon-16x16.png', 16, 16)
assertPngDimensions('frontend/public/favicon-32x32.png', 32, 32)
assertPngDimensions('frontend/public/apple-touch-icon.png', 180, 180)
assertPngDimensions('frontend/public/pwa-192x192.png', 192, 192)
assertPngDimensions('frontend/public/pwa-512x512.png', 512, 512)
assertPngDimensions('frontend/public/brand/email-logo.png', 256, 256)
assertPngDimensions('frontend-admin/public/favicon-16x16.png', 16, 16)
assertPngDimensions('frontend-admin/public/favicon-32x32.png', 32, 32)
assertPngDimensions('frontend-admin/public/apple-touch-icon.png', 180, 180)

const userIndex = read('frontend/index.html')
const adminIndex = read('frontend-admin/index.html')
const userVite = read('frontend/vite.config.ts')
const emailTemplates = read('backend/app/email/templates.py')
const emailService = read('backend/app/email/service.py')
const emailTests = read('backend/tests/test_email_delivery.py')
const readme = read('README.md')

for (const [label, source] of [
  ['frontend/index.html', userIndex],
  ['frontend-admin/index.html', adminIndex],
]) {
  assertContains(source, 'href="/favicon.ico"', label)
  assertContains(source, 'href="/favicon-32x32.png"', label)
  assertContains(source, 'href="/favicon-16x16.png"', label)
  assertContains(source, 'href="/apple-touch-icon.png"', label)
}

assertContains(userVite, "'favicon-16x16.png'", 'frontend/vite.config.ts')
assertContains(userVite, "'favicon-32x32.png'", 'frontend/vite.config.ts')
assertContains(userVite, "src: 'pwa-192x192.png'", 'frontend/vite.config.ts')
assertContains(userVite, "src: 'pwa-512x512.png'", 'frontend/vite.config.ts')

assertContains(emailTemplates, '/brand/email-logo.png', 'backend/app/email/templates.py')
assertContains(emailTemplates, 'alt="{safe_app_name}"', 'backend/app/email/templates.py')
assertContains(emailTemplates, 'width="128" height="128"', 'backend/app/email/templates.py')
assertContains(emailService, 'brand_base_url=app_settings.frontend_url', 'backend/app/email/service.py')
assertContains(emailTests, 'https://krotpn.xyz/brand/email-logo.png', 'backend/tests/test_email_delivery.py')
assertContains(emailTests, '"brand/email-logo.png" not in text', 'backend/tests/test_email_delivery.py')

assertContains(readme, '### Favicon and Email Logo', 'README.md')
assertContains(readme, 'https://krotpn.xyz/brand/email-logo.png', 'README.md')
assertContains(readme, 'BIMI', 'README.md')

assertProtectedDeployDiffClean()

if (expectDist) {
  assertIcoFile('frontend/dist/favicon.ico')
  assertIcoFile('frontend-admin/dist/favicon.ico')
  assertPngDimensions('frontend/dist/favicon-16x16.png', 16, 16)
  assertPngDimensions('frontend/dist/favicon-32x32.png', 32, 32)
  assertPngDimensions('frontend/dist/apple-touch-icon.png', 180, 180)
  assertPngDimensions('frontend/dist/pwa-192x192.png', 192, 192)
  assertPngDimensions('frontend/dist/pwa-512x512.png', 512, 512)
  assertPngDimensions('frontend/dist/brand/email-logo.png', 256, 256)
  assertPngDimensions('frontend-admin/dist/favicon-16x16.png', 16, 16)
  assertPngDimensions('frontend-admin/dist/favicon-32x32.png', 32, 32)
  assertPngDimensions('frontend-admin/dist/apple-touch-icon.png', 180, 180)
}
// END_BLOCK_PHASE51_STATIC_ASSERTIONS

console.log('[M-069][phase51_brand_assets][FAVICON_ASSETS] ok')
console.log('[M-069][phase51_brand_assets][EMAIL_LOGO_TEMPLATE] ok')
console.log('[M-069][phase51_brand_assets][DOCUMENTATION] ok')
console.log('[M-069][phase51_brand_assets][PROTECTED_SURFACES] ok')
