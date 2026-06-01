#!/usr/bin/env node
/*
 * FILE: scripts/phase47-mtproto-cta-links-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke checks for Phase-47 MTProto CTA subdomain link generation
 *   SCOPE: CTA prefix allow-list, public short-id helpers, owner link consistency, redaction, and protected deploy surfaces
 *   DEPENDS: M-065, M-043, M-045, M-064
 *   LINKS: V-M-065
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads a repository file for static assertions
 *   assertContains - Fails if a required marker is missing
 *   assertNotContains - Fails if a forbidden marker is present
 *   assertProtectedSurfaceGuard - Guards protected deploy/runtime topology files from Phase-47 markers
 *   main - Runs Phase-47 CTA link smoke assertions
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-47 MTProto CTA link static smoke gate
 * END_CHANGE_SUMMARY
 */

import { existsSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

const root = process.cwd()

function read(relativePath) {
  return readFileSync(join(root, relativePath), 'utf8')
}

function assertContains(source, needle, label) {
  if (!source.includes(needle)) {
    throw new Error(`${label} is missing required Phase-47 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains forbidden Phase-47 marker: ${needle}`)
  }
}

function assertProtectedSurfaceGuard() {
  const protectedPaths = [
    'install.sh',
    'docker-compose.yml',
    'nginx',
    'deploy',
    'deploy/mtproto-de-compose.yml',
    '.env.example',
  ]
  for (const protectedPath of protectedPaths) {
    const fullPath = join(root, protectedPath)
    if (!existsSync(fullPath)) {
      throw new Error(`Protected deploy surface missing from repository: ${protectedPath}`)
    }
    if (statSync(fullPath).isFile()) {
      const source = read(protectedPath)
      assertNotContains(source, 'M-065', protectedPath)
      assertNotContains(source, 'generate_cta_sni', protectedPath)
    }
  }
}

// START_BLOCK_PHASE47_STATIC_ASSERTIONS
const provisioningPath = 'backend/app/mtproto/provisioning.py'
const dashboardPath = 'frontend/src/pages/Dashboard.tsx'
const provisioning = read(provisioningPath)
const dashboard = read(dashboardPath)

for (const prefix of ['kupi-vpn', 'vpn-tut', 'beri-vpn', 'bez-blokirovok', 'hochu-bystree', 'krot-vpn']) {
  assertContains(provisioning, `"${prefix}"`, provisioningPath)
}

assertContains(provisioning, 'MTPROTO_CTA_PREFIXES', provisioningPath)
assertContains(provisioning, 'PUBLIC_SHORT_ID_LEN = 7', provisioningPath)
assertContains(provisioning, 'def shorten_public_user_id(', provisioningPath)
assertContains(provisioning, 'def select_cta_prefix(', provisioningPath)
assertContains(provisioning, 'def generate_cta_sni(', provisioningPath)
assertContains(provisioning, 'collision_nonce', provisioningPath)
assertContains(provisioning, '[M-065][generate_cta_sni][CTA_PREFIX]', provisioningPath)
assertContains(provisioning, '[M-065][generate_cta_sni][PUBLIC_SHORT_ID]', provisioningPath)
assertContains(provisioning, '[M-065][issue_user_proxy][CTA_ASSIGNMENT]', provisioningPath)
assertContains(provisioning, '[M-065][phase47_mtproto_cta_links][LEGACY_PRESERVE]', provisioningPath)
assertContains(provisioning, 'derive_fake_tls_secret(', provisioningPath)
assertContains(provisioning, 'assignment.sni', provisioningPath)

assertContains(dashboard, 'buildMtprotoTelegramAppLink', dashboardPath)
assertContains(dashboard, 'buildMtprotoBrowserLink', dashboardPath)
assertContains(dashboard, 'server: payload.server', dashboardPath)
assertContains(dashboard, 'secret: payload.secret', dashboardPath)
assertContains(dashboard, 'tg://proxy?', dashboardPath)
assertContains(dashboard, 'https://t.me/proxy?', dashboardPath)
assertNotContains(dashboard, 'server: payload.sni', dashboardPath)

assertNotContains(provisioning, 'MTPROTO_BASE_SECRET_HEX=', provisioningPath)
assertNotContains(provisioning, 'MTPROTO_SECRET_SALT=', provisioningPath)
assertProtectedSurfaceGuard()
// END_BLOCK_PHASE47_STATIC_ASSERTIONS

console.log('[M-065][phase47_mtproto_cta_links][CTA_PREFIX_ALLOWLIST] ok')
console.log('[M-065][phase47_mtproto_cta_links][OWNER_LINK_CONSISTENCY] ok')
console.log('[M-065][phase47_mtproto_cta_links][PROTECTED_SURFACES] ok')
