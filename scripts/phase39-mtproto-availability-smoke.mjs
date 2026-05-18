#!/usr/bin/env node
// FILE: scripts/phase39-mtproto-availability-smoke.mjs
// VERSION: 1.0.0
// ROLE: SCRIPT
// MAP_MODE: LOCALS
// START_MODULE_CONTRACT
//   PURPOSE: Static Phase-39 smoke for MTProto availability diagnostics, redaction, UI link flow, and DE fallback guard.
//   SCOPE: Source markers, fallback-port contracts, redaction guards, live-smoke safety, backend helper tests, and MyGRACE Phase-39 docs.
//   DEPENDS: M-012, M-043, M-044, M-045, M-050, M-051, node:fs, node:path
//   LINKS: docs/modules/M-051.xml, docs/plans/Phase-39.xml, docs/verification/V-M-051.xml
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   read - Load a project file as UTF-8.
//   requireText/requireAbsent/requireAbsentPattern - Minimal static contract assertions.
//   BLOCK_PHASE39_MTPROTO_AVAILABILITY_SMOKE - Phase-39 static assertions.
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.0.0 - Added Phase-39 static availability smoke.
// END_CHANGE_SUMMARY

import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')

function read(relativePath) {
  return readFileSync(resolve(root, relativePath), 'utf8')
}

function requireText(file, marker) {
  const content = read(file)
  if (!content.includes(marker)) {
    throw new Error(`${file} is missing ${JSON.stringify(marker)}`)
  }
}

function requireAbsent(file, marker) {
  const content = read(file)
  if (content.includes(marker)) {
    throw new Error(`${file} must not contain ${JSON.stringify(marker)}`)
  }
}

function requireAbsentPattern(file, pattern) {
  const content = read(file)
  if (pattern.test(content)) {
    throw new Error(`${file} must not match ${pattern}`)
  }
}

// START_BLOCK_PHASE39_MTPROTO_AVAILABILITY_SMOKE
requireText('docs/plans/Phase-39.xml', 'MTProto Telegram Availability Closure')
requireText('docs/plans/Phase-39.xml', 'M-051')
requireText('docs/verification/V-M-051.xml', '[M-051][availability_smoke][FAKE_TLS_ACCEPT]')
requireText('docs/verification/V-M-051.xml', 'Never print full tg://proxy links')
requireText('docs/modules/M-051.xml', 'redacted-operator-diagnostics')

requireText('backend/app/mtproto/availability.py', 'def mask_sni')
requireText('backend/app/mtproto/availability.py', 'def redact_proxy_text')
requireText('backend/app/mtproto/availability.py', 'def build_telegram_web_link')
requireText('backend/tests/test_mtproto_availability_diagnostics.py', 'test_redact_proxy_text_removes_full_links_and_fake_tls_secrets')
requireText('backend/tests/test_mtproto_availability_diagnostics.py', 'test_build_telegram_web_link_uses_owner_values')
requireAbsent('backend/app/mtproto/availability.py', 'logger.')
requireAbsentPattern('backend/app/mtproto/availability.py', /^\s*print\(/m)

requireText('frontend/src/pages/Dashboard.tsx', '[M-045][dashboard_mtproto_card][OPEN_TELEGRAM]')
requireText('frontend/src/pages/Dashboard.tsx', 'buildMtprotoTelegramWebLink')
requireText('frontend/src/pages/Dashboard.tsx', 'https://t.me/proxy?')
requireText('frontend/src/pages/Dashboard.tsx', 'Full link')
requireText('frontend/src/pages/Dashboard.tsx', "field: 'telegram_web_link'")
requireAbsentPattern('frontend/src/pages/Dashboard.tsx', /console\.info\([^)]*secret/i)

requireText('deploy/mtproto-de-compose.yml', 'PORTAL_DOMAIN_FRONTING: ${DE_MTPROTO_DOMAIN_FRONTING:-127.0.0.1:9443}')
requireAbsent('deploy/mtproto-de-compose.yml', 'PORTAL_DOMAIN_FRONTING: ${DE_MTPROTO_DOMAIN_FRONTING:-127.0.0.1:8443}')
requireText('deploy/deploy-on-server.sh', 'normalize_de_mtproto_domain_fronting')
requireText('deploy/deploy-on-server.sh', '[M-051][de_mtproto_runtime][NORMALIZE_DOMAIN_FRONTING]')
requireText('deploy/deploy-on-server.sh', '[M-050][de_mtproto_runtime][FALLBACK_PORT_GUARD]')
requireText('deploy/deploy-on-server.sh', 'DE_MTPROTO_DOMAIN_FRONTING=127.0.0.1:9443')
requireAbsentPattern('deploy/deploy-on-server.sh', /^DE_MTPROTO_DOMAIN_FRONTING=127\.0\.0\.1:8443$/m)

requireText('scripts/phase39-mtproto-live-smoke.sh', 'set -euo pipefail')
requireText('scripts/phase39-mtproto-live-smoke.sh', '[M-051][availability_smoke][LOAD_ACTIVE_ASSIGNMENT]')
requireText('scripts/phase39-mtproto-live-smoke.sh', '[M-051][availability_smoke][POLICY_HEALTH]')
requireText('scripts/phase39-mtproto-live-smoke.sh', '[M-051][availability_smoke][ROUTE_PUBLIC_443]')
requireText('scripts/phase39-mtproto-live-smoke.sh', '[M-051][availability_smoke][FAKE_TLS_ACCEPT]')
requireText('scripts/phase39-mtproto-live-smoke.sh', '[M-050][de_mtproto_runtime][FALLBACK_PORT_GUARD]')
requireText('scripts/phase39-mtproto-live-smoke.sh', '[M-051][availability_smoke][TELEGRAM_DOWNSTREAM]')
requireText('scripts/phase39-mtproto-live-smoke.sh', '[M-051][availability_smoke][TELEGRAM_DESKTOP_PROOF]')
requireText('scripts/phase39-mtproto-live-smoke.sh', 'mask_sni')
requireText('scripts/phase39-mtproto-live-smoke.sh', 'redacted')
requireText('scripts/phase39-mtproto-live-smoke.sh', '--apply-fallback-guard')
requireAbsent('scripts/phase39-mtproto-live-smoke.sh', 'set -x')
requireAbsent('scripts/phase39-mtproto-live-smoke.sh', 'cat .env')
requireAbsent('scripts/phase39-mtproto-live-smoke.sh', 'cat /opt/KrotPN/.env')
requireAbsent('scripts/phase39-mtproto-live-smoke.sh', 'RESEND_API_KEY')
// END_BLOCK_PHASE39_MTPROTO_AVAILABILITY_SMOKE

console.log('[M-051][availability_smoke][STATIC_GUARD] Phase-39 MTProto availability static smoke passed')
