#!/usr/bin/env node
// FILE: scripts/phase36-resend-deploy-smoke.mjs
// VERSION: 1.0.0
// ROLE: SCRIPT
// MAP_MODE: LOCALS
// START_MODULE_CONTRACT
//   PURPOSE: Static Phase-36 smoke for Resend installer/deploy email-provider wiring.
//   SCOPE: Installer prompts, Resend input guards, deploy env generation, redaction assertions, backend provider request-shape hooks, and MyGRACE documentation sync.
//   DEPENDS: M-048, M-012, M-001, M-040, M-041, node:fs, node:path
//   LINKS: docs/modules/M-048.xml, docs/plans/Phase-36.xml, docs/verification/V-M-048.xml
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   read - Load a project file as UTF-8.
//   requireText/requireAbsent/requireMatch - Minimal static contract assertions.
//   runInstallerValidator - Source install.sh without running main and execute validator assertions.
//   BLOCK_PHASE36_RESEND_DEPLOY_SMOKE - Phase-36 source and documentation assertions.
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.0.0 - Added Phase-36 Resend deploy wiring smoke.
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

// START_BLOCK_PHASE36_RESEND_DEPLOY_SMOKE
requireText('install.sh', 'START_MODULE_CONTRACT')
requireText('install.sh', 'DEFAULT_EMAIL_FROM="noreply@krotpn.xyz"')
requireText('install.sh', 'DEFAULT_RESEND_API_URL="https://api.resend.com/emails"')
requireText('install.sh', 'validate_resend_api_key')
requireText('install.sh', 'validate_email_from')
requireText('install.sh', 'get_email_config')
requireText('install.sh', 'ask_password "Resend API key" RESEND_API_KEY')
requireText('install.sh', 'RESEND_API_KEY) RESEND_API_KEY="$password"')
requireText('install.sh', "EMAIL_PROVIDER='${EMAIL_PROVIDER}'")
requireText('install.sh', "RESEND_API_KEY='${RESEND_API_KEY}'")
requireText('install.sh', "RESEND_API_URL='${RESEND_API_URL}'")
requireText('install.sh', "EMAIL_FROM='${EMAIL_FROM}'")
requireText('install.sh', '[M-048][installer_resend][PROMPT_SECRET]')
requireText('install.sh', 'RESEND_API_KEY      - key entered during installation, not printed')
requireAbsent('install.sh', 'echo -e "  • RESEND_API_KEY      - ${GREEN}${RESEND_API_KEY}')

requireText('deploy/deploy-on-server.sh', 'START_MODULE_CONTRACT')
requireText('deploy/deploy-on-server.sh', 'validate_resend_email_config')
requireText('deploy/deploy-on-server.sh', 'EMAIL_PROVIDER="${EMAIL_PROVIDER:-resend}"')
requireText('deploy/deploy-on-server.sh', 'RESEND_API_URL="${RESEND_API_URL:-https://api.resend.com/emails}"')
requireText('deploy/deploy-on-server.sh', 'EMAIL_FROM="$(printf')
requireText('deploy/deploy-on-server.sh', '[M-012][deploy_resend][ENV_WIRING]')
requireText('deploy/deploy-on-server.sh', '[M-012][deploy_resend][REDACT_SECRET]')
requireText('deploy/deploy-on-server.sh', '[M-012][deploy_resend][ABORT_MISSING_KEY]')
requireText('deploy/deploy-on-server.sh', '[M-048][deploy_resend][ENV_WIRING]')
requireText('deploy/deploy-on-server.sh', 'EMAIL_PROVIDER=${EMAIL_PROVIDER}')
requireText('deploy/deploy-on-server.sh', 'RESEND_API_KEY=${RESEND_API_KEY}')
requireText('deploy/deploy-on-server.sh', 'RESEND_API_URL=${RESEND_API_URL}')
requireText('deploy/deploy-on-server.sh', 'EMAIL_FROM=${EMAIL_FROM}')
requireText('deploy/deploy-on-server.sh', 'EMAIL_VERIFICATION_URL_BASE=https://${PUBLIC_DOMAIN}/verify-email')
requireAbsent('deploy/deploy-on-server.sh', 'echo -e "${GREEN}${RESEND_API_KEY}')
requireAbsent('deploy/deploy-on-server.sh', 'echo "$RESEND_API_KEY"')
requireAbsent('deploy/deploy-on-server.sh', 'cat "$RESEND_API_KEY"')
requireAbsent('deploy/deploy-on-server.sh', 'provider_disabled because EMAIL_PROVIDER')

requireText('backend/app/core/config.py', 'validate_resend_api_key')
requireText('backend/app/core/config.py', 'RESEND_API_URL must be https://api.resend.com/emails')
requireText('backend/app/core/config.py', 'EMAIL_FROM must be a valid sender email address')
requireText('backend/app/email/provider.py', '"Authorization": f"Bearer {api_key}"')
requireText('backend/app/email/provider.py', '"from": email_from')
requireText('backend/tests/test_email_delivery.py', 'test_resend_provider_builds_production_request_shape')

requireText('.env.example', 'EMAIL_PROVIDER=disabled')
requireText('.env.example', 'RESEND_API_KEY=')
requireText('.env.example', 'RESEND_API_URL=https://api.resend.com/emails')
requireText('.env.example', 'EMAIL_FROM=noreply@krotpn.xyz')

requireText('docs/plans/Phase-36.xml', 'Resend Deploy Email Provider Wiring')
requireText('docs/verification/V-M-040.xml', 'Resend request shape uses https://api.resend.com/emails')
requireText('docs/verification/V-M-041.xml', 'provider_disabled')
requireText('docs/verification/V-M-048.xml', 'deploy_resend_config_result')

runInstallerValidator('validate_resend_api_key resend_test_secret_123')
runInstallerValidator('if validate_resend_api_key ""; then exit 1; fi')
runInstallerValidator('if validate_resend_api_key "bad key"; then exit 1; fi')
runInstallerValidator('if validate_resend_api_key "bad;key"; then exit 1; fi')
runInstallerValidator('validate_email_from noreply@krotpn.xyz')
runInstallerValidator('if validate_email_from "noreply"; then exit 1; fi')
runInstallerValidator('if validate_email_from "bad;id@krotpn.xyz"; then exit 1; fi')
// END_BLOCK_PHASE36_RESEND_DEPLOY_SMOKE

console.log('[M-048][installer_resend][PROMPT_SECRET] Phase-36 Resend deploy static smoke passed')
