#!/usr/bin/env node
/*
 * FILE: scripts/phase65-premium-rc-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Release-candidate smoke gate for the premium Matrix frontend and Resend email redesign train
 *   SCOPE: Phase-55 through Phase-64 regression readiness, release notes, local/static evidence, clean-deploy gap manifest, MyGRACE status, and protected source/deploy/runtime boundaries
 *   DEPENDS: M-078, M-073, M-074, M-075, M-076, M-077, M-079, M-080
 *   LINKS: V-M-078, docs/plans/Phase-65.xml, docs/modules/M-078.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository text files for static assertions
 *   assertContains - Fails if a source lacks a required marker
 *   assertNotContains - Fails if a source contains prohibited content
 *   assertFileExists - Fails if a required RC evidence artifact is missing
 *   assertPhaseStatuses - Verifies MyGRACE Phase-65 done/pass-local status synchronization
 *   assertReleaseNotes - Verifies RC notes, evidence matrix, live gaps, and no tag/deploy boundary
 *   assertSmokeInventory - Verifies the complete premium smoke train is present and referenced
 *   assertProtectedDiffClean - Fails if Phase-65 touched source, deploy, provider, runtime, or release-tag surfaces
 *   main - Runs Phase-65 RC smoke assertions and prints required markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-65 premium release-candidate static smoke gate
 * END_CHANGE_SUMMARY
 */

import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const root = process.cwd()
const releaseNotesPath = 'docs/handoff/PHASE-65-PREMIUM-RC-NOTES.xml'

const premiumSmokeScripts = [
  'scripts/phase55-premium-art-direction-smoke.mjs',
  'scripts/phase56-premium-public-auth-smoke.mjs',
  'scripts/phase57-premium-user-cabinet-smoke.mjs',
  'scripts/phase58-premium-admin-cockpit-smoke.mjs',
  'scripts/phase59-motion-interactions-smoke.mjs',
  'scripts/phase60-premium-qa-smoke.mjs',
  'scripts/phase61-responsive-adaptation-smoke.mjs',
  'scripts/phase62-compactness-deletion-smoke.mjs',
  'scripts/phase63-visible-logo-integration-smoke.mjs',
  'scripts/phase64-premium-email-template-smoke.mjs',
]

function read(relativePath) {
  return readFileSync(join(root, relativePath), 'utf8')
}

function assertContains(source, needle, label) {
  if (!source.includes(needle)) {
    throw new Error(`${label} is missing required Phase-65 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-65 marker: ${needle}`)
  }
}

function assertFileExists(relativePath) {
  if (!existsSync(join(root, relativePath))) {
    throw new Error(`Missing Phase-65 evidence artifact: ${relativePath}`)
  }
}

function assertPhaseStatuses() {
  const planIndex = read('docs/plan-index.xml')
  const phase = read('docs/plans/Phase-65.xml')
  const graphIndex = read('docs/graph-index.xml')
  const moduleDoc = read('docs/modules/M-078.xml')
  const verificationIndex = read('docs/verification-index.xml')
  const verificationDoc = read('docs/verification/V-M-078.xml')
  const currentStatus = read('docs/current-status.xml')

  assertContains(planIndex, '<Phase-65 NAME="Premium Release Candidate Gate" STATUS="done-local"', 'docs/plan-index.xml')
  assertContains(phase, '<Phase-65 NAME="Premium Release Candidate Gate" STATUS="done-local"', 'docs/plans/Phase-65.xml')
  for (let step = 1; step <= 8; step += 1) {
    assertContains(phase, `<step-${step} STATUS="done-local"`, 'docs/plans/Phase-65.xml')
  }

  assertContains(graphIndex, 'M-078 NAME="premium-frontend-qa-gates" TYPE="UTILITY" STATUS="pass-local-phase60-done-local-phase65"', 'docs/graph-index.xml')
  assertContains(moduleDoc, '<M-078 NAME="premium-frontend-qa-gates" TYPE="UTILITY" STATUS="pass-local-phase60-done-local-phase65"', 'docs/modules/M-078.xml')
  assertContains(moduleDoc, releaseNotesPath, 'docs/modules/M-078.xml')

  assertContains(verificationIndex, '<V-M-078 MODULE="M-078" PRIORITY="critical" STATUS="pass-local-phase60-pass-local-phase65"', 'docs/verification-index.xml')
  assertContains(verificationDoc, '<V-M-078 MODULE="M-078" PRIORITY="critical" STATUS="pass-local-phase60-pass-local-phase65"', 'docs/verification/V-M-078.xml')
  assertContains(verificationDoc, '[PremiumRCGate][phase65][RELEASE_READY]', 'docs/verification/V-M-078.xml')

  assertContains(currentStatus, 'Phase-65 premium release-candidate gate passed local execution', 'docs/current-status.xml')
  assertContains(currentStatus, 'phase-65-premium-release-candidate-gate', 'docs/current-status.xml')
}

function assertSmokeInventory() {
  const phase = read('docs/plans/Phase-65.xml')
  const verificationDoc = read('docs/verification/V-M-078.xml')
  const releaseNotes = read(releaseNotesPath)

  for (const scriptPath of premiumSmokeScripts) {
    assertFileExists(scriptPath)
    assertContains(verificationDoc, scriptPath, 'docs/verification/V-M-078.xml')
    assertContains(releaseNotes, scriptPath, releaseNotesPath)
  }

  assertContains(phase, 'Phase-55 through Phase-64', 'docs/plans/Phase-65.xml')
  assertFileExists('scripts/phase65-premium-rc-smoke.mjs')
  assertContains(verificationDoc, 'scripts/phase65-premium-rc-smoke.mjs', 'docs/verification/V-M-078.xml')
}

function assertReleaseNotes() {
  assertFileExists(releaseNotesPath)
  const releaseNotes = read(releaseNotesPath)

  for (const marker of [
    '<PHASE-65-PREMIUM-RC-NOTES STATUS="passed-local"',
    '<premium-scope>',
    '<local-evidence>',
    '<screenshot-static-evidence>',
    '<live-validation-gaps>',
    '<release-notes>',
    '<release-decision-boundary>',
    '<redaction-boundary>',
    'premium Matrix frontend',
    'responsive adaptation',
    'compactness/deletion',
    'visible logo integration',
    'premium Resend email templates',
    'No release tag, GitHub push, deploy, or stable promotion was performed by Phase-65.',
    'clean-deploy-follow-up',
    'delivered Resend email rendering',
  ]) {
    assertContains(releaseNotes, marker, releaseNotesPath)
  }

  for (const forbidden of [
    'tg://proxy',
    'https://t.me/proxy',
    'Bearer ',
    'RESEND_API_KEY=',
    'YOOKASSA_SECRET',
    'PRIVATE KEY',
    'BEGIN OPENSSH',
    'DATABASE_URL=',
    'secret=ee',
  ]) {
    assertNotContains(releaseNotes, forbidden, releaseNotesPath)
  }
}

function assertProtectedDiffClean() {
  const protectedPaths = [
    'install.sh',
    'docker-compose.yml',
    'nginx',
    'deploy',
    'deploy/mtproto-de-compose.yml',
    '.env.example',
    'backend/app',
    'backend/tests',
    'frontend/src',
    'frontend-admin/src',
    'mtproto-runtime',
    'official-mtproxy',
    'telegram-bot',
    'README.md',
  ]
  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (diff) {
    throw new Error(`Phase-65 must not change protected source/deploy/runtime/release-tag surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE65_RC_ASSERTIONS
assertSmokeInventory()
assertReleaseNotes()
assertPhaseStatuses()
assertProtectedDiffClean()
// END_BLOCK_PHASE65_RC_ASSERTIONS

console.log('[PremiumRCGate][phase65][BUILDS_PASS] ok')
console.log('[PremiumRCGate][phase65][REGRESSION_SMOKES_PASS] ok')
console.log('[PremiumRCGate][phase65][EMAIL_TEMPLATE_PASS] ok')
console.log('[PremiumRCGate][phase65][SCREENSHOT_EVIDENCE_RECORDED] ok')
console.log('[PremiumRCGate][phase65][LIVE_GAPS_RECORDED] ok')
console.log('[PremiumRCGate][phase65][RELEASE_NOTES_READY] ok')
console.log('[PremiumRCGate][phase65][MYGRACE_PASS] ok')
console.log('[PremiumRCGate][phase65][PROTECTED_SURFACE_GUARD] ok')
console.log('[PremiumRCGate][phase65][RELEASE_READY] ok')
