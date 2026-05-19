#!/usr/bin/env node
// FILE: scripts/phase41-kpproton-faketls-smoke.mjs
// VERSION: 1.0.0
// ROLE: SCRIPT
// MAP_MODE: LOCALS
// START_MODULE_CONTRACT
//   PURPOSE: Static Phase-41 smoke proving KPprotoN fake-TLS is the active MTProto production path.
//   SCOPE: Backend derived-per-SNI issuance, admin/scheduler runtime bridge use, DE KPprotoN compose, RU SNI router default, and official MTProxy rollback isolation.
//   DEPENDS: M-012, M-043, M-044, M-049, M-050, M-052, M-053, node:fs, node:path
//   LINKS: docs/plans/Phase-41.xml, docs/modules/M-043.xml, docs/modules/M-044.xml, docs/modules/M-049.xml, docs/modules/M-050.xml, docs/modules/M-052.xml, docs/modules/M-053.xml
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   read - Load a project file as UTF-8.
//   requireText/requireAbsent - Minimal static contract assertions.
//   BLOCK_PHASE41_KPPROTON_FAKETLS_SMOKE - Phase-41 static assertions.
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.0.0 - Added Phase-41 KPprotoN fake-TLS static smoke.
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

// START_BLOCK_PHASE41_KPPROTON_FAKETLS_SMOKE
requireText('docs/plans/Phase-41.xml', 'KPprotoN fake-TLS production data-plane rollback')
requireText('backend/app/mtproto/provisioning.py', 'MTProtoCredentialMode.DERIVED_PER_SNI')
requireText('backend/app/mtproto/provisioning.py', 'derive_fake_tls_secret(')
requireText('backend/app/mtproto/provisioning.py', 'server=assignment.sni')
requireText('backend/app/mtproto/provisioning.py', 'build_tg_link(assignment.sni')
requireText('backend/app/mtproto/provisioning.py', 'MTProtoRuntimeBridge(self.session)')
requireAbsent('backend/app/mtproto/provisioning.py', 'MTProxySecretSyncService')
requireAbsent('backend/app/mtproto/provisioning.py', 'derive_official_secret')
requireAbsent('backend/app/mtproto/provisioning.py', 'build_official_tg_link')

requireText('backend/app/admin/router.py', 'MTProtoRuntimeBridge')
requireAbsent('backend/app/admin/router.py', 'MTProxySecretSyncService')
requireText('backend/app/tasks/scheduler.py', 'MTProtoRuntimeBridge')
requireAbsent('backend/app/tasks/scheduler.py', 'official_secrets')

requireText('docker-compose.yml', '${SNI_ROUTER_CONF_PATH:-./deploy/haproxy-phase38.cfg}:/usr/local/etc/haproxy/haproxy.cfg:ro')
requireText('.env.example', 'SNI_ROUTER_CONF_PATH=./deploy/haproxy-phase38.cfg')
requireText('deploy/deploy-on-server.sh', 'haproxy-phase38.cfg')
requireText('deploy/deploy-on-server.sh', 'krotpn-mtproto-runtime.tgz')
requireText('deploy/deploy-on-server.sh', 'DE_MTPROTO_DOMAIN_FRONTING=${domain_fronting_target}')
requireText('deploy/deploy-on-server.sh', '/opt/KrotPN/ssl/server.crt')
requireText('deploy/deploy-on-server.sh', '/opt/KrotPN/ssl/server.key')
requireAbsent('deploy/deploy-on-server.sh', 'krotpn-official-mtproxy.tgz')
requireAbsent('deploy/deploy-on-server.sh', 'MTPROXY_NAT_INFO')

requireText('deploy/mtproto-de-compose.yml', 'context: ./mtproto-runtime')
requireText('deploy/mtproto-de-compose.yml', 'PROXY_SECRET_HEX: ${MTPROTO_BASE_SECRET_HEX:?MTPROTO_BASE_SECRET_HEX must be set}')
requireText('deploy/mtproto-de-compose.yml', 'PROXY_SECRET_SALT: ${MTPROTO_SECRET_SALT:?MTPROTO_SECRET_SALT must be set}')
requireText('deploy/mtproto-de-compose.yml', 'POLICY_LISTEN_IP: ${MTPROTO_POLICY_BIND_IP:-127.0.0.1}')
requireText('deploy/mtproto-de-compose.yml', 'PORTAL_DOMAIN_FRONTING: ${DE_MTPROTO_DOMAIN_FRONTING:-127.0.0.1:18443}')
requireText('deploy/mtproto-de-compose.yml', './ssl:/certs/krotpn:ro')
requireAbsent('deploy/mtproto-de-compose.yml', 'official-mtproxy')
requireAbsent('deploy/mtproto-de-compose.yml', 'MTPROXY_NAT_INFO')
// END_BLOCK_PHASE41_KPPROTON_FAKETLS_SMOKE

console.log('[M-049][mtproto_runtime][KPPROTON_FAKETLS] Phase-41 KPprotoN fake-TLS static smoke passed')
