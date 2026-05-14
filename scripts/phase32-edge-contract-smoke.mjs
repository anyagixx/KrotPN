// FILE: scripts/phase32-edge-contract-smoke.mjs
// VERSION: 1.0.0
// ROLE: SCRIPT
// MAP_MODE: LOCALS
// START_MODULE_CONTRACT
//   PURPOSE: Static Phase-32 edge contract smoke without live DNS or certificate access
//   SCOPE: Source markers, domain/TLS settings, protected deploy/install guard, redaction guard
//   DEPENDS: M-046, M-012
//   LINKS: docs/verification/V-M-046.xml, docs/plans/Phase-32.xml
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   requireText - Assert that a file contains a contract marker
//   requireAbsent - Assert that a file does not contain unsafe text
//   changedFiles - Return current git diff names for protected-surface guard
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.0.0 - Added Phase-32 edge contract static smoke
// END_CHANGE_SUMMARY

import { execFileSync } from 'node:child_process'
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
    throw new Error(`${file} must contain ${JSON.stringify(marker)}`)
  }
}

function requireAbsent(file, marker) {
  const content = read(file)
  if (content.includes(marker)) {
    throw new Error(`${file} must not contain ${JSON.stringify(marker)}`)
  }
}

function changedFiles() {
  return execFileSync('git', ['diff', '--name-only', 'HEAD'], { cwd: root, encoding: 'utf8' })
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}

// START_BLOCK_PHASE32_EDGE_CONTRACT_SMOKE
requireText('backend/app/core/config.py', 'edge_public_domain: str = "krotpn.xyz"')
requireText('backend/app/core/config.py', 'edge_tls_certificate_mode')
requireText('backend/app/core/config.py', 'edge_wildcard_domain')

requireText('nginx/nginx.conf', '[M-046][edge_contract][DOMAIN_SETTINGS]')
requireText('nginx/nginx.conf', '[M-046][nginx_contract][HTTP_TO_HTTPS_REDIRECT]')
requireText('nginx/nginx.conf', '[M-046][edge_router][SNI_CLASSIFY]')
requireText('nginx/nginx.conf', '[M-046][edge_router][HTTPS_FALLBACK]')
requireText('nginx/nginx.conf', '[M-046][edge_router][MTPROTO_ROUTE]')
requireText('nginx/nginx.conf', 'server_name krotpn.xyz www.krotpn.xyz;')
requireText('nginx/nginx.conf', 'return 301 https://krotpn.xyz$request_uri;')
requireText('nginx/nginx.conf', 'server_name krotpn.xyz *.krotpn.xyz;')

requireText('.env.example', 'FRONTEND_URL=https://krotpn.xyz')
requireText('docs/edge/PHASE-32-CUTOVER.xml', '[M-046][edge_contract][ROLLBACK_READY]')
requireText('docs/edge/PHASE-32-CUTOVER.xml', 'operator-live')

requireAbsent('nginx/nginx.conf', 'MTPROTO_BASE_SECRET_HEX')
requireAbsent('docs/edge/PHASE-32-CUTOVER.xml', 'MTPROTO_BASE_SECRET_HEX=')

const protectedChanges = changedFiles().filter((file) => (
  file === 'install.sh'
  || file.startsWith('deploy/')
))

if (protectedChanges.length > 0) {
  throw new Error(`Phase-32 must not change deploy/install scripts: ${protectedChanges.join(', ')}`)
}
// END_BLOCK_PHASE32_EDGE_CONTRACT_SMOKE

console.log('[M-046][edge_contract][DOMAIN_SETTINGS] static edge contract smoke passed')
