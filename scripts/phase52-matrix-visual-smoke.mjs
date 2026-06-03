#!/usr/bin/env node
/*
 * FILE: scripts/phase52-matrix-visual-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke checks for Phase-52 Matrix visual runtime and style-system foundation
 *   SCOPE: User/admin VisualShell mounting, Matrix canvas runtime markers, shared CSS tokens/layers, reduced-motion/focus rules, and protected deploy surfaces
 *   DEPENDS: M-009, M-010, M-038, M-070, M-071
 *   LINKS: V-M-070, V-M-071
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository text files for static assertions
 *   assertContains - Fails if a file lacks a required marker
 *   assertNotContains - Fails if a file contains a prohibited reference artifact marker
 *   assertProtectedDeployDiffClean - Fails if Phase-52 touched deploy/install surfaces
 *   main - Runs Phase-52 Matrix visual smoke assertions
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-52 Matrix visual foundation static smoke gate
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
    throw new Error(`${label} is missing required Phase-52 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited reference artifact marker: ${needle}`)
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
    throw new Error(`Phase-52 must not change deploy/install surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE52_STATIC_ASSERTIONS
const userApp = read('frontend/src/App.tsx')
const adminMain = read('frontend-admin/src/main.tsx')
const userRuntime = read('frontend/src/components/MatrixBackground.tsx')
const adminRuntime = read('frontend-admin/src/components/MatrixBackground.tsx')
const userShell = read('frontend/src/components/VisualShell.tsx')
const adminShell = read('frontend-admin/src/components/VisualShell.tsx')
const userCss = read('frontend/src/index.css')
const adminCss = read('frontend-admin/src/index.css')

for (const [label, source] of [
  ['frontend/src/App.tsx', userApp],
  ['frontend-admin/src/main.tsx', adminMain],
]) {
  assertContains(source, 'VisualShell', label)
  assertContains(source, '<VisualShell>', label)
}

for (const [label, source] of [
  ['frontend/src/components/VisualShell.tsx', userShell],
  ['frontend-admin/src/components/VisualShell.tsx', adminShell],
]) {
  assertContains(source, 'START_MODULE_CONTRACT', label)
  assertContains(source, 'M-070', label)
  assertContains(source, 'M-071', label)
  assertContains(source, 'matrix-visual-shell', label)
  assertContains(source, 'matrix-scanline-overlay', label)
  assertContains(source, 'matrix-vignette', label)
  assertContains(source, 'matrix-visual-content', label)
}

for (const [label, source] of [
  ['frontend/src/components/MatrixBackground.tsx', userRuntime],
  ['frontend-admin/src/components/MatrixBackground.tsx', adminRuntime],
]) {
  assertContains(source, 'START_MODULE_CONTRACT', label)
  assertContains(source, 'requestAnimationFrame', label)
  assertContains(source, 'cancelAnimationFrame', label)
  assertContains(source, 'prefers-reduced-motion: reduce', label)
  assertContains(source, 'visibilitychange', label)
  assertContains(source, 'data-matrix-canvas', label)
  assertContains(source, '[MatrixVisualRuntime][init][CANVAS_READY]', label)
  assertContains(source, '[MatrixVisualRuntime][resize][CANVAS_RESIZE]', label)
  assertContains(source, '[MatrixVisualRuntime][motionPolicy][REDUCED_MOTION]', label)
  assertContains(source, '[MatrixVisualRuntime][fallback][CANVAS_CONTEXT_UNAVAILABLE]', label)
  assertContains(source, '[MatrixVisualRuntime][cleanup][ANIMATION_STOPPED]', label)
}

for (const [label, source] of [
  ['frontend/src/index.css', userCss],
  ['frontend-admin/src/index.css', adminCss],
]) {
  assertContains(source, 'START_MODULE_CONTRACT', label)
  assertContains(source, '--matrix-green', label)
  assertContains(source, '--matrix-cyan', label)
  assertContains(source, '--matrix-magenta', label)
  assertContains(source, '--matrix-amber', label)
  assertContains(source, '--matrix-red', label)
  assertContains(source, '.matrix-visual-shell', label)
  assertContains(source, '.matrix-canvas', label)
  assertContains(source, '.matrix-scanline-overlay', label)
  assertContains(source, '.matrix-vignette', label)
  assertContains(source, '.matrix-visual-content', label)
  assertContains(source, ':focus-visible', label)
  assertContains(source, '@media (prefers-reduced-motion: reduce)', label)
  assertContains(source, 'overflow-x: hidden', label)

  for (const prohibited of [
    'background-music',
    'fluid-cursor',
    'spider',
    'nft1',
    'nft2',
    'nft3',
    'nft4',
    'neural-glow',
  ]) {
    assertNotContains(source, prohibited, label)
  }
}

assertProtectedDeployDiffClean()
// END_BLOCK_PHASE52_STATIC_ASSERTIONS

console.log('[MatrixVisualRuntime][init][CANVAS_READY] static-contract-ok')
console.log('[MatrixVisualRuntime][resize][CANVAS_RESIZE] static-contract-ok')
console.log('[MatrixVisualRuntime][motionPolicy][REDUCED_MOTION] static-contract-ok')
console.log('[MatrixVisualRuntime][fallback][CANVAS_CONTEXT_UNAVAILABLE] static-contract-ok')
console.log('[MatrixVisualRuntime][cleanup][ANIMATION_STOPPED] static-contract-ok')
console.log('[MatrixStyleSystem][smoke][TOKENS_PRESENT] ok')
console.log('[MatrixStyleSystem][smoke][REDUCED_MOTION_POLICY] ok')
console.log('[MatrixStyleSystem][smoke][VIEWPORT_NO_OVERFLOW] ok')
console.log('[MatrixStyleSystem][smoke][FOCUS_VISIBLE] ok')
console.log('[MatrixStyleSystem][smoke][PROTECTED_SURFACE_GUARD] ok')
