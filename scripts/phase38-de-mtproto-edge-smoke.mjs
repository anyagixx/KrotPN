#!/usr/bin/env node
// FILE: scripts/phase38-de-mtproto-edge-smoke.mjs
// VERSION: 1.1.0
// ROLE: SCRIPT
// MAP_MODE: LOCALS
// START_MODULE_CONTRACT
//   PURPOSE: Static Phase-38 smoke for the DE-backed MTProto edge and RU SNI router.
//   SCOPE: HAProxy SNI router, DE runtime compose, backend private policy URL validation, deploy env wiring, local compose ownership, and redaction guards.
//   DEPENDS: M-012, M-044, M-046, M-048, M-049, M-050, node:fs, node:path
//   LINKS: docs/modules/M-012.xml, docs/modules/M-044.xml, docs/modules/M-046.xml, docs/modules/M-048.xml, docs/modules/M-049.xml, docs/modules/M-050.xml, docs/plans/Phase-38.xml
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   read - Load a project file as UTF-8.
//   requireText/requireAbsent - Minimal static contract assertions.
//   BLOCK_PHASE38_DE_MTPROTO_EDGE_SMOKE - Phase-38 static assertions.
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.1.0 - Guard HAProxy low-port bind permissions and private fallback port 9443.
//   LAST_CHANGE: v1.0.0 - Added Phase-38 DE-backed MTProto edge static smoke.
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

// START_BLOCK_PHASE38_DE_MTPROTO_EDGE_SMOKE
requireText('deploy/haproxy-phase38.cfg', 'bind *:443')
requireText('deploy/haproxy-phase38.cfg', '[M-050][ru_sni_router][ROUTE_WEB]')
requireText('deploy/haproxy-phase38.cfg', '[M-050][ru_sni_router][ROUTE_MTPROTO]')
requireText('deploy/haproxy-phase38.cfg', '[M-050][ru_sni_router][ROUTE_UNKNOWN_SNI]')
requireText('deploy/haproxy-phase38.cfg', 'acl sni_web req.ssl_sni -i krotpn.xyz www.krotpn.xyz')
requireText('deploy/haproxy-phase38.cfg', '^u-[0-9a-f]{12}\\.krotpn\\.xyz$')
requireText('deploy/haproxy-phase38.cfg', 'server ru_nginx_9443 127.0.0.1:9443 check')
requireText('deploy/haproxy-phase38.cfg', 'server de_mtproto_443 127.0.0.1:19443 check')

requireText('docker-compose.yml', 'container_name: krotpn-sni-router')
requireText('docker-compose.yml', 'haproxy:2.9-alpine')
requireText('docker-compose.yml', 'user: "0:0"')
requireText('docker-compose.yml', 'NET_BIND_SERVICE')
requireText('docker-compose.yml', 'SNI_ROUTER_CONF_PATH')
requireText('docker-compose.yml', 'profiles:')
requireText('docker-compose.yml', 'local-mtproto-edge')
requireText('docker-compose.yml', '${SNI_ROUTER_CONF_PATH:-./deploy/haproxy-phase38.cfg}:/usr/local/etc/haproxy/haproxy.cfg:ro')

requireText('deploy/mtproto-de-compose.yml', 'container_name: krotpn-mtproto-de-runtime')
requireText('deploy/mtproto-de-compose.yml', 'POLICY_LISTEN_IP: ${MTPROTO_POLICY_BIND_IP:-127.0.0.1}')
requireText('deploy/mtproto-de-compose.yml', 'PROXY_LISTEN_IP: 0.0.0.0')
requireText('deploy/mtproto-de-compose.yml', '/krotpn/mtproto/policy/health')

requireText('mtproto-runtime/src/kpproton_runtime.erl', 'policy_listen_ip/0')
requireText('mtproto-runtime/src/kpproton_runtime.erl', 'POLICY_LISTEN_IP')
requireText('mtproto-runtime/src/kpproton_web.erl', '{ip, PolicyListenIp}')

requireText('backend/app/core/config.py', 'mtproto_policy_bind_ip: str = "127.0.0.1"')
requireText('backend/app/core/config.py', '_is_private_policy_host')
requireText('backend/app/core/config.py', 'edge_mtproto_mode')
requireText('backend/tests/test_mtproto_de_edge_contract.py', 'test_private_de_policy_url_is_allowed')
requireText('backend/tests/test_deploy_phase38_static.py', 'test_haproxy_routes_web_and_mtproto_sni')

requireText('deploy/deploy-on-server.sh', 'render_nginx_domain_config')
requireText('deploy/deploy-on-server.sh', 'deploy_de_mtproto_runtime')
requireText('deploy/deploy-on-server.sh', 'MTPROTO_POLICY_BIND_IP="${MTPROTO_POLICY_BIND_IP:-$VPN_RELAY_DE_ADDRESS}"')
requireText('deploy/deploy-on-server.sh', 'MTPROTO_RUNTIME_POLICY_URL=http://${MTPROTO_POLICY_BIND_IP}:${MTPROTO_POLICY_PORT}/krotpn/mtproto/policy')
requireText('deploy/deploy-on-server.sh', 'EDGE_HTTPS_FALLBACK_PORT=9443')
requireText('deploy/deploy-on-server.sh', '127\\\\.0\\\\.0\\\\.1:19443')
requireText('deploy/deploy-on-server.sh', 'SNI_ROUTER_CONF_PATH=./deploy/haproxy.runtime.cfg')
requireText('deploy/deploy-on-server.sh', '[M-050][de_policy_api][DENY_PUBLIC]')
requireText('deploy/deploy-on-server.sh', '[M-050][de_policy_api][HEALTH]')
requireText('deploy/deploy-on-server.sh', 'generate_or_preserve_secret MTPROTO_BASE_SECRET_HEX')
requireText('deploy/deploy-on-server.sh', 'generate_or_preserve_secret MTPROTO_SECRET_SALT')

requireText('.env.example', 'MTPROTO_RUNTIME_POLICY_URL=http://172.29.255.1:18080/krotpn/mtproto/policy')
requireText('.env.example', 'MTPROTO_POLICY_BIND_IP=172.29.255.1')
requireText('.env.example', 'EDGE_HTTPS_FALLBACK_PORT=9443')
requireText('.env.example', 'EDGE_MTPROTO_MODE=de-backed')
requireText('.env.example', 'EDGE_MTPROTO_DE_TARGET_HOST=203.0.113.10')
requireText('.env.example', 'SNI_ROUTER_CONF_PATH=./deploy/haproxy-phase38.cfg')

requireText('docs/plans/Phase-38.xml', 'DE-backed MTProto Edge')
requireText('docs/modules/M-050.xml', 'mtproto-de-backed-edge')
requireText('docs/verification/V-M-050.xml', 'RU SNI router owns public TCP 443')

requireAbsent('deploy/deploy-on-server.sh', 'cat "$TLS_PRIVKEY_PATH"')
requireAbsent('deploy/deploy-on-server.sh', 'cat ${TLS_PRIVKEY_PATH}')
requireAbsent('deploy/haproxy-phase38.cfg', 'MTPROTO_BASE_SECRET_HEX')
requireAbsent('deploy/haproxy-phase38.cfg', 'MTPROTO_SECRET_SALT')
// END_BLOCK_PHASE38_DE_MTPROTO_EDGE_SMOKE

console.log('[M-050][ru_sni_router][ROUTE_MTPROTO] Phase-38 DE-backed MTProto edge static smoke passed')
