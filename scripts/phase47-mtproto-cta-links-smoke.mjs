#!/usr/bin/env node
/*
 * FILE: scripts/phase47-mtproto-cta-links-smoke.mjs
 * VERSION: 1.2.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke checks for Phase-47 MTProto CTA subdomain link generation
 *   SCOPE: CTA prefix allow-list, public short-id helpers, owner link consistency, redaction, SNI-router compatibility, and protected non-router deploy surfaces
 *   DEPENDS: M-065, M-043, M-045, M-050, M-064
 *   LINKS: V-M-065, V-M-050
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads a repository file for static assertions
 *   assertContains - Fails if a required marker is missing
 *   assertNotContains - Fails if a forbidden marker is present
 *   assertProtectedSurfaceGuard - Guards protected non-router deploy/runtime topology files from Phase-47 markers
 *   assertSniRouterSupportsCtaLabels - Guards RU SNI router compatibility with CTA-issued hostnames
 *   main - Runs Phase-47 CTA link smoke assertions
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.2.0 - Assert the router ACL regex accepts representative legacy and CTA issued hostnames
 *   LAST_CHANGE: v1.1.0 - Added SNI-router compatibility guard for CTA-prefixed issued hostnames
 *   LAST_CHANGE: v1.0.0 - Added Phase-47 MTProto CTA link static smoke gate
 * END_CHANGE_SUMMARY
 */

import { existsSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

const root = process.cwd()
const ctaPrefixes = ['kupi-vpn', 'vpn-tut', 'beri-vpn', 'bez-blokirovok', 'hochu-bystree', 'krot-vpn']

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
    'nginx/nginx.conf',
    'deploy/deploy-on-server.sh',
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

function assertSniRouterSupportsCtaLabels() {
  const routerPath = 'deploy/haproxy-phase38.cfg'
  const router = read(routerPath)
  const aclPattern = '^(u-[0-9a-f]{12}|(kupi-vpn|vpn-tut|beri-vpn|bez-blokirovok|hochu-bystree|krot-vpn)-[0-9a-f]{7})\\.krotpn\\.xyz$'
  const routeRegex = new RegExp(aclPattern)

  assertContains(router, 'use_backend mtproto_de_runtime if sni_mtproto', routerPath)
  assertContains(router, 'default_backend web_https_fallback', routerPath)
  assertContains(router, aclPattern, routerPath)
  assertContains(router, 'u-[0-9a-f]{12}', routerPath)
  assertContains(router, '-[0-9a-f]{7}', routerPath)
  for (const prefix of ctaPrefixes) {
    assertContains(router, prefix, routerPath)
  }
  for (const hostname of [
    'u-0195616cec89.krotpn.xyz',
    'hochu-bystree-b405086.krotpn.xyz',
    'kupi-vpn-4bb40fa.krotpn.xyz',
  ]) {
    if (!routeRegex.test(hostname)) {
      throw new Error(`${routerPath} MTProto ACL does not match issued hostname: ${hostname}`)
    }
  }
  for (const hostname of ['krotpn.xyz', 'www.krotpn.xyz', 'unknown-b405086.krotpn.xyz']) {
    if (routeRegex.test(hostname)) {
      throw new Error(`${routerPath} MTProto ACL unexpectedly matches non-issued hostname: ${hostname}`)
    }
  }
  assertNotContains(router, 'default_backend mtproto_de_runtime', routerPath)
}

// START_BLOCK_PHASE47_STATIC_ASSERTIONS
const provisioningPath = 'backend/app/mtproto/provisioning.py'
const dashboardPath = 'frontend/src/pages/Dashboard.tsx'
const provisioning = read(provisioningPath)
const dashboard = read(dashboardPath)

for (const prefix of ctaPrefixes) {
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
assertSniRouterSupportsCtaLabels()
// END_BLOCK_PHASE47_STATIC_ASSERTIONS

console.log('[M-065][phase47_mtproto_cta_links][CTA_PREFIX_ALLOWLIST] ok')
console.log('[M-065][phase47_mtproto_cta_links][OWNER_LINK_CONSISTENCY] ok')
console.log('[M-065][phase47_mtproto_cta_links][SNI_ROUTER_COMPATIBILITY] ok')
console.log('[M-065][phase47_mtproto_cta_links][PROTECTED_SURFACES] ok')
