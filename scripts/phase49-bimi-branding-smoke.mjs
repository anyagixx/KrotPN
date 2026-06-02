#!/usr/bin/env node
/*
 * FILE: scripts/phase49-bimi-branding-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke checks for Phase-49 BIMI sender-branding asset delivery
 *   SCOPE: BIMI SVG Tiny P/S constraints, frontend nginx well-known routing, README DNS runbook, optional dist copy, and protected deploy surfaces
 *   DEPENDS: M-067, M-009, M-012, M-040, M-046, M-062
 *   LINKS: V-M-067
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads a repository file for static assertions
 *   assertContains - Fails if a source file lacks a required marker
 *   assertNotContains - Fails if a source file contains a forbidden marker
 *   assertBimiSvg - Validates the public BIMI SVG asset
 *   assertNginxWellKnownRoute - Validates frontend nginx route ordering
 *   assertReadmeDnsRunbook - Validates operator DNS instructions
 *   assertProtectedDeployDiffClean - Fails if Phase-49 touched protected operational surfaces
 *   main - Runs Phase-49 BIMI sender-branding smoke assertions
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-49 BIMI sender-branding static smoke gate
 * END_CHANGE_SUMMARY
 */

import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

const root = process.cwd()
const expectDist = process.argv.includes('--expect-dist') || process.env.PHASE49_EXPECT_DIST === '1'

function read(relativePath) {
  return readFileSync(join(root, relativePath), 'utf8')
}

function assertContains(source, needle, label) {
  if (!source.includes(needle)) {
    throw new Error(`${label} is missing required Phase-49 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains forbidden Phase-49 marker: ${needle}`)
  }
}

function assertMatches(source, pattern, label, message) {
  if (!pattern.test(source)) {
    throw new Error(`${label} failed Phase-49 assertion: ${message}`)
  }
}

function assertBimiSvg(relativePath) {
  const absolutePath = join(root, relativePath)
  if (!existsSync(absolutePath)) {
    throw new Error(`BIMI SVG asset missing: ${relativePath}`)
  }

  const byteSize = statSync(absolutePath).size
  if (byteSize >= 32 * 1024) {
    throw new Error(`BIMI SVG is too large: ${byteSize} bytes`)
  }

  const svg = read(relativePath)
  const rootMatch = svg.match(/<svg\b([^>]*)>/i)
  if (!rootMatch) {
    throw new Error(`BIMI SVG root <svg> tag is missing in ${relativePath}`)
  }

  const rootAttrs = rootMatch[1]
  assertMatches(rootAttrs, /\sversion="1\.2"/i, relativePath, 'root version="1.2" is required')
  assertMatches(rootAttrs, /\sbaseProfile="tiny-ps"/i, relativePath, 'root baseProfile="tiny-ps" is required')
  assertMatches(rootAttrs, /\sviewBox="0 0 ([0-9.]+) ([0-9.]+)"/i, relativePath, 'square viewBox is required')

  const viewBox = rootAttrs.match(/\sviewBox="0 0 ([0-9.]+) ([0-9.]+)"/i)
  if (viewBox && viewBox[1] !== viewBox[2]) {
    throw new Error(`BIMI SVG viewBox must be square: ${viewBox[1]}x${viewBox[2]}`)
  }

  assertNotContains(rootAttrs, ' x=', `${relativePath} root`)
  assertNotContains(rootAttrs, ' y=', `${relativePath} root`)
  assertContains(svg, '<title>KrotPN</title>', relativePath)
  assertContains(svg, '<desc>', relativePath)

  const forbiddenPatterns = [
    ['<script', /<script\b/i],
    ['foreignObject', /<foreignObject\b/i],
    ['<image', /<image\b/i],
    ['animation', /<(animate|animateTransform|animateMotion|set)\b/i],
    ['inline style attributes', /\sstyle\s*=/i],
    ['style tags', /<style\b/i],
    ['href attributes', /\s(?:xlink:)?href\s*=/i],
    ['base64 payloads', /base64/i],
    ['javascript URLs', /javascript:/i],
  ]
  for (const [label, pattern] of forbiddenPatterns) {
    if (pattern.test(svg)) {
      throw new Error(`BIMI SVG contains forbidden ${label}`)
    }
  }

  const withoutSvgNamespace = svg.replace(/xmlns="http:\/\/www\.w3\.org\/2000\/svg"/gi, '')
  if (/https?:\/\//i.test(withoutSvgNamespace)) {
    throw new Error('BIMI SVG contains an external http/https URL')
  }

  return byteSize
}

function assertNginxWellKnownRoute() {
  const nginxPath = 'frontend/nginx.conf'
  const nginx = read(nginxPath)
  const bimiRoute = 'location ^~ /.well-known/bimi/'
  const hiddenDeny = 'location ~ /\\.'

  assertContains(nginx, bimiRoute, nginxPath)
  assertContains(nginx, 'try_files $uri =404;', nginxPath)
  assertContains(nginx, 'default_type image/svg+xml;', nginxPath)
  assertContains(nginx, hiddenDeny, nginxPath)

  const bimiIndex = nginx.indexOf(bimiRoute)
  const hiddenIndex = nginx.indexOf(hiddenDeny)
  if (bimiIndex < 0 || hiddenIndex < 0 || bimiIndex > hiddenIndex) {
    throw new Error('frontend nginx BIMI well-known route must appear before hidden-file deny rule')
  }
}

function assertReadmeDnsRunbook() {
  const readmePath = 'README.md'
  const readme = read(readmePath)
  assertContains(readme, '### Email Sender Avatar (BIMI)', readmePath)
  assertContains(readme, 'default._bimi', readmePath)
  assertContains(readme, 'v=BIMI1; l=https://krotpn.xyz/.well-known/bimi/krotpn.svg;', readmePath)
  assertContains(readme, 'Do not add `a=` until VMC/CMC PEM certificate material exists.', readmePath)
}

function assertDistCopy() {
  const distPath = 'frontend/dist/.well-known/bimi/krotpn.svg'
  if (!expectDist) {
    return
  }

  assertBimiSvg(distPath)
  if (read(distPath) !== read('frontend/public/.well-known/bimi/krotpn.svg')) {
    throw new Error('Frontend build changed the BIMI SVG asset content unexpectedly')
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
    throw new Error(`Phase-49 must not change protected deploy/install surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE49_STATIC_ASSERTIONS
const byteSize = assertBimiSvg('frontend/public/.well-known/bimi/krotpn.svg')
assertNginxWellKnownRoute()
assertReadmeDnsRunbook()
assertDistCopy()
assertProtectedDeployDiffClean()
// END_BLOCK_PHASE49_STATIC_ASSERTIONS

console.log(`[M-067][phase49_bimi_branding][SVG_TINY_PS] ok bytes=${byteSize}`)
console.log('[M-067][phase49_bimi_branding][WELL_KNOWN_ROUTE] ok')
console.log('[M-067][phase49_bimi_branding][PROTECTED_SURFACES] ok')
