#!/usr/bin/env node
// FILE: scripts/phase37-mtproto-runtime-smoke.mjs
// VERSION: 1.0.0
// ROLE: SCRIPT
// MAP_MODE: LOCALS
// START_MODULE_CONTRACT
//   PURPOSE: Static Phase-37 smoke for the live MTProto shared-443 runtime bridge fix.
//   SCOPE: Runtime sidecar files, backend HTTP adapter, nginx fallback port, deploy env wiring, and redaction guards.
//   DEPENDS: M-044, M-046, M-049, node:fs, node:path
//   LINKS: docs/modules/M-044.xml, docs/modules/M-046.xml, docs/modules/M-049.xml, docs/plans/Phase-37.xml
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   read - Load a project file as UTF-8.
//   requireText/requireAbsent - Minimal static contract assertions.
//   BLOCK_PHASE37_MTPROTO_RUNTIME_SMOKE - Phase-37 static runtime assertions.
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.0.0 - Added Phase-37 MTProto runtime bridge static smoke.
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

// START_BLOCK_PHASE37_MTPROTO_RUNTIME_SMOKE
requireText('mtproto-runtime/rebar.config', 'mtproto_proxy')
requireText('mtproto-runtime/src/kpproton_app.erl', 'per_sni_secrets, on')
requireText('mtproto-runtime/src/kpproton_web.erl', '/krotpn/mtproto/policy/apply')
requireText('mtproto-runtime/src/kpproton_core_api.erl', 'STATIC_SECRET_FALLBACK')
requireText('mtproto-runtime/src/kpproton_core_api.erl', 'BOOTSTRAP_CORE_FETCH_TIMEOUT_SECONDS')
requireText('mtproto-runtime/src/kpproton_policy_handler.erl', 'KROTPN_MTPROTO_POLICY_TOKEN')
requireText('mtproto-runtime/apps/kpproton_proxy/src/mtproto/kpproton_proxy_bridge.erl', 'mtp_policy_table:add(personal_domains, tls_domain, SniDomain)')
requireText('mtproto-runtime/apps/kpproton_proxy/src/mtproto/kpproton_proxy_bridge.erl', 'mtp_policy_table:del(personal_domains, tls_domain, SniDomain)')

requireText('backend/app/mtproto/runtime_bridge.py', 'class HTTPMTProtoPolicyAdapter')
requireText('backend/app/mtproto/runtime_bridge.py', 'x-krotpn-mtproto-token')
requireText('backend/app/mtproto/provisioning.py', 'START_BLOCK_APPLY_RUNTIME_POLICY')
requireText('backend/tests/test_kpproton_runtime_bridge.py', 'test_http_policy_adapter_posts_apply_and_health_with_token')

requireText('docker-compose.yml', 'container_name: krotpn-mtproto-edge')
requireText('docker-compose.yml', 'PROXY_PORT: ${MTPROTO_PROXY_PORT:-443}')
requireText('docker-compose.yml', 'PORTAL_DOMAIN_FRONTING: 127.0.0.1:${EDGE_HTTPS_FALLBACK_PORT:-8443}')
requireText('nginx/nginx.conf', 'listen 8443 ssl;')
requireAbsent('nginx/nginx.conf', 'listen 443 ssl;')

requireText('deploy/deploy-on-server.sh', 'MTPROTO_RUNTIME_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")')
requireText('deploy/deploy-on-server.sh', 'MTPROTO_RUNTIME_POLICY_URL=http://127.0.0.1:18080/krotpn/mtproto/policy')
requireText('deploy/deploy-on-server.sh', 'START_BLOCK_MTPROTO_TELEGRAM_ROUTES')
requireText('deploy/deploy-on-server.sh', '149.154.160.0/20')
requireText('.env.example', 'EDGE_SHARED_443_ENABLED=true')
requireText('.env.example', 'MTPROTO_RUNTIME_TOKEN=')

requireAbsent('mtproto-runtime/src/kpproton_policy_handler.erl', 'PROXY_SECRET_HEX')
requireAbsent('mtproto-runtime/src/kpproton_policy_handler.erl', 'PROXY_SECRET_SALT')
// END_BLOCK_PHASE37_MTPROTO_RUNTIME_SMOKE

console.log('[M-049][mtproto_runtime][POLICY_BRIDGE] Phase-37 runtime static smoke passed')
