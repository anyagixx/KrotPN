#!/usr/bin/env node
// FILE: scripts/phase35-installer-wildcard-tls-smoke.mjs
// VERSION: 1.4.0
// ROLE: SCRIPT
// MAP_MODE: LOCALS
// START_MODULE_CONTRACT
//   PURPOSE: Static Phase-35 smoke for operator-provided wildcard TLS installer and deploy wiring.
//   SCOPE: Installer prompts, TLS input guards, remote cert validation, production self-signed guard, env wiring, runtime nginx/SNI-router config, MTProto edge token wiring, and redaction assertions.
//   DEPENDS: M-048, M-012, M-044, M-046, M-050, node:fs, node:path
//   LINKS: docs/modules/M-048.xml, docs/plans/Phase-35.xml, docs/verification/V-M-048.xml
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   read - Load a project file as UTF-8.
//   requireText/requireAbsent/requireMatch - Minimal static contract assertions.
//   runInstallerValidator - Source install.sh without running main and execute validator assertions.
//   BLOCK_PHASE35_INSTALLER_WILDCARD_TLS_SMOKE - Phase-35 source and documentation assertions.
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.4.0 - Updated MTProto env assertions for Phase-38 DE-backed policy URL and secret preservation.
//   LAST_CHANGE: v1.3.0 - Added Phase-37 MTProto runtime token and shared-443 edge checks.
//   LAST_CHANGE: v1.2.0 - Added deploy-generated MTProto secret regression guard.
//   LAST_CHANGE: v1.1.0 - Added dynamic installer validator checks for unsafe domains and certificate paths.
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
    throw new Error(`${file} is missing ${JSON.stringify(marker)}`)
  }
}

function requireAbsent(file, marker) {
  const content = read(file)
  if (content.includes(marker)) {
    throw new Error(`${file} must not contain ${JSON.stringify(marker)}`)
  }
}

function requireMatch(file, pattern, description) {
  const content = read(file)
  if (!pattern.test(content)) {
    throw new Error(`${file} is missing ${description}`)
  }
}

function runInstallerValidator(command) {
  return execFileSync(
    'bash',
    ['-lc', `set -e; KROTPN_INSTALLER_SOURCE_ONLY=1 source ./install.sh >/dev/null; ${command}`],
    { cwd: root, encoding: 'utf8', stdio: 'pipe' },
  )
}

// START_BLOCK_PHASE35_INSTALLER_WILDCARD_TLS_SMOKE
requireText('install.sh', 'START_MODULE_CONTRACT')
requireText('install.sh', 'DEFAULT_PUBLIC_DOMAIN="krotpn.xyz"')
requireText('install.sh', 'DEFAULT_TLS_FULLCHAIN_PATH="/root/krotpn-ssl/fullchain1.pem"')
requireText('install.sh', 'DEFAULT_TLS_PRIVKEY_PATH="/root/krotpn-ssl/privkey1.pem"')
requireText('install.sh', 'PUBLIC_DOMAIN) PUBLIC_DOMAIN="$value"')
requireText('install.sh', 'TLS_FULLCHAIN_PATH) TLS_FULLCHAIN_PATH="$value"')
requireText('install.sh', 'TLS_PRIVKEY_PATH) TLS_PRIVKEY_PATH="$value"')
requireText('install.sh', 'validate_public_domain')
requireText('install.sh', 'validate_tls_path')
requireText('install.sh', 'validate_remote_tls_files')
requireText('install.sh', 'ensure_remote_openssl')
requireText('install.sh', 'KROTPN_INSTALLER_SOURCE_ONLY')
requireText('install.sh', '[M-048][installer_tls][VALIDATE_INPUTS]')
requireText('install.sh', '[M-048][installer_tls][VALIDATE_CERT_PATHS]')
requireText('install.sh', '[M-048][installer_tls][VALIDATE_CERT_KEY_MATCH]')
requireText('install.sh', '[M-048][installer_tls][VALIDATE_SAN]')
requireText('install.sh', 'TLS_CERTIFICATE_MODE=\'operator-wildcard\'')
requireText('install.sh', 'get_tls_config')
requireText('install.sh', 'get_tls_config')
requireAbsent('install.sh', 'Note: Browser will warn about self-signed certificate.')

requireText('deploy/deploy-on-server.sh', 'START_MODULE_CONTRACT')
requireText('deploy/deploy-on-server.sh', 'TLS_CERTIFICATE_MODE="${TLS_CERTIFICATE_MODE:-operator-wildcard}"')
requireText('deploy/deploy-on-server.sh', 'validate_operator_tls_certificate')
requireText('deploy/deploy-on-server.sh', 'install_operator_tls_certificate')
requireText('deploy/deploy-on-server.sh', 'generate_self_signed_dev_certificate')
requireText('deploy/deploy-on-server.sh', 'render_nginx_domain_config')
requireText('deploy/deploy-on-server.sh', 'path must not be under /opt/KrotPN')
requireText('deploy/deploy-on-server.sh', 'openssl x509 -in "$TLS_FULLCHAIN_PATH" -checkend 86400')
requireText('deploy/deploy-on-server.sh', 'openssl pkey -in "$TLS_PRIVKEY_PATH" -pubout -outform der')
requireText('deploy/deploy-on-server.sh', 'subjectAltName')
requireText('deploy/deploy-on-server.sh', '[M-048][deploy_tls][ABORT_BEFORE_DEPLOY]')
requireText('deploy/deploy-on-server.sh', '[M-048][deploy_tls][INSTALL_CERT]')
requireText('deploy/deploy-on-server.sh', '[M-048][deploy_tls][ENV_WIRING]')
requireText('deploy/deploy-on-server.sh', '/opt/KrotPN/ssl/server.crt')
requireText('deploy/deploy-on-server.sh', '/opt/KrotPN/ssl/server.key')
requireText('deploy/deploy-on-server.sh', 'NGINX_CONF_PATH=./nginx/nginx.runtime.conf')
requireText('deploy/deploy-on-server.sh', 'SNI_ROUTER_CONF_PATH=./deploy/haproxy.runtime.cfg')
requireText('deploy/deploy-on-server.sh', 'FRONTEND_URL=https://${PUBLIC_DOMAIN}')
requireText('deploy/deploy-on-server.sh', 'MTPROTO_BASE_DOMAIN=${PUBLIC_DOMAIN}')
requireText('deploy/deploy-on-server.sh', 'MTPROTO_BASE_SECRET_HEX=${MTPROTO_BASE_SECRET_HEX}')
requireText('deploy/deploy-on-server.sh', 'MTPROTO_SECRET_SALT=${MTPROTO_SECRET_SALT}')
requireText('deploy/deploy-on-server.sh', 'generate_or_preserve_secret MTPROTO_RUNTIME_TOKEN')
requireText('deploy/deploy-on-server.sh', 'MTPROTO_RUNTIME_POLICY_URL=http://${MTPROTO_POLICY_BIND_IP}:${MTPROTO_POLICY_PORT}/krotpn/mtproto/policy')
requireText('deploy/deploy-on-server.sh', 'generate_or_preserve_secret MTPROTO_BASE_SECRET_HEX')
requireText('deploy/deploy-on-server.sh', 'generate_or_preserve_secret MTPROTO_SECRET_SALT')
requireMatch('deploy/deploy-on-server.sh', /secrets\.token_hex\(16\)/, 'deploy-time MTProto secret generation')
requireText('deploy/deploy-on-server.sh', 'EDGE_TLS_CERTIFICATE_MODE=${TLS_CERTIFICATE_MODE}')
requireText('deploy/deploy-on-server.sh', 'EDGE_SHARED_443_ENABLED=true')
requireText('deploy/deploy-on-server.sh', 'EDGE_MTPROTO_MODE=${EDGE_MTPROTO_MODE}')
requireText('deploy/deploy-on-server.sh', 'self-signed-dev')
requireAbsent('deploy/deploy-on-server.sh', 'MTPROTO_BASE_SECRET_HEX=\n')
requireAbsent('deploy/deploy-on-server.sh', 'MTPROTO_SECRET_SALT=\n')
requireAbsent('deploy/deploy-on-server.sh', 'cat "$TLS_PRIVKEY_PATH"')
requireAbsent('deploy/deploy-on-server.sh', 'cat ${TLS_PRIVKEY_PATH}')

requireText('docker-compose.yml', 'START_MODULE_CONTRACT')
requireText('docker-compose.yml', 'NGINX_CONF_PATH')
requireText('docker-compose.yml', '${NGINX_CONF_PATH:-./nginx/nginx.conf}:/etc/nginx/nginx.conf:ro')
requireText('docker-compose.yml', 'container_name: krotpn-sni-router')
requireText('docker-compose.yml', 'SNI_ROUTER_CONF_PATH')
requireText('docker-compose.yml', 'container_name: krotpn-mtproto-edge')
requireText('docker-compose.yml', 'KROTPN_MTPROTO_POLICY_TOKEN')
requireText('.env.example', 'START_MODULE_CONTRACT')
requireText('.env.example', 'NGINX_CONF_PATH=./nginx/nginx.runtime.conf')
requireText('.env.example', 'SNI_ROUTER_CONF_PATH=./deploy/haproxy-phase38.cfg')
requireText('.env.example', 'EDGE_SHARED_443_ENABLED=true')

requireText('docs/plans/Phase-35.xml', 'Operator Wildcard TLS Installer')
requireText('docs/modules/M-048.xml', 'installer-wildcard-tls')
requireText('docs/verification/V-M-048.xml', 'installer_tls_validation_result')
requireText('docs/verification/V-M-048.xml', 'private-key material')

runInstallerValidator('validate_public_domain krotpn.xyz')
runInstallerValidator('if validate_public_domain "https://krotpn.xyz"; then exit 1; fi')
runInstallerValidator('if validate_public_domain "krotpn.xyz;id"; then exit 1; fi')
runInstallerValidator('validate_tls_path /root/krotpn-ssl/fullchain1.pem Fullchain')
runInstallerValidator('if validate_tls_path relative.pem Fullchain; then exit 1; fi')
runInstallerValidator('if validate_tls_path "/root/krotpn-ssl/fullchain1.pem;id" Fullchain; then exit 1; fi')
runInstallerValidator('if validate_tls_path /opt/KrotPN/ssl/server.crt Fullchain; then exit 1; fi')
// END_BLOCK_PHASE35_INSTALLER_WILDCARD_TLS_SMOKE

console.log('[M-048][installer_tls][VALIDATE_INPUTS] Phase-35 installer wildcard TLS static smoke passed')
