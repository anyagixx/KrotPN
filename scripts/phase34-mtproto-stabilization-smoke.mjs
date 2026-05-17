#!/usr/bin/env node
// FILE: scripts/phase34-mtproto-stabilization-smoke.mjs
// VERSION: 1.1.0
// ROLE: SCRIPT
// MAP_MODE: LOCALS
// START_MODULE_CONTRACT
//   PURPOSE: Static Phase-34 stabilization smoke for verified onboarding, MTProto owner/admin surfaces, redaction, and release handoff.
//   SCOPE: Source markers, Phase-34 integration-test presence, frontend/admin anchors,
//          release checklist markers, secret-redaction guards, and Phase-35 scoped deploy/install/edge surface guard.
//   DEPENDS: M-040, M-041, M-042, M-043, M-045, M-046, M-047, M-048, node:fs, node:path, node:child_process
//   LINKS: V-M-041, V-M-045, V-M-046, V-M-047, V-M-048, docs/plans/Phase-34.xml, docs/plans/Phase-35.xml
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   read - Load a project file as UTF-8.
//   requireText/requireAbsent - Minimal static assertions.
//   changedFiles - Read current git diff names against HEAD.
//   BLOCK_PHASE34_MTPROTO_STABILIZATION_SMOKE - Phase-34 static release-readiness assertions.
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.1.0 - Allowed approved Phase-35 wildcard TLS installer edge/deploy changes.
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

function changedFiles() {
  return execFileSync('git', ['diff', '--name-only', 'HEAD'], { cwd: root, encoding: 'utf8' })
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}

// START_BLOCK_PHASE34_MTPROTO_STABILIZATION_SMOKE
requireText('docs/plans/Phase-34.xml', 'backend/tests/test_phase34_mtproto_integration.py')
requireText('docs/plans/Phase-34.xml', 'scripts/phase34-mtproto-stabilization-smoke.mjs')
requireText('docs/plans/Phase-34.xml', 'docs/handoff/PHASE-34-RELEASE-CHECKLIST.xml')
requireText('docs/plans/Phase-34.xml', 'operator-live')

requireText('backend/tests/test_phase34_mtproto_integration.py', 'START_MODULE_CONTRACT')
requireText('backend/tests/test_phase34_mtproto_integration.py', 'test_verified_registration_issues_single_owner_mtproto_proxy')
requireText('backend/tests/test_phase34_mtproto_integration.py', 'test_unverified_user_cannot_get_mtproto_assignment')
requireText('backend/tests/test_phase34_mtproto_integration.py', 'MTProtoAssignment')
requireText('backend/tests/test_phase34_mtproto_integration.py', 'token_replayed')
requireText('backend/tests/test_phase34_mtproto_integration.py', 'phase34.owner@example.com')

requireText('backend/app/users/router.py', '[M-041][verify_registration][ACTIVATE_SIDE_EFFECTS]')
requireText('backend/app/mtproto/router.py', '[M-045][get_my_mtproto_proxy][OWNER_LOOKUP]')
requireText('backend/app/mtproto/router.py', '[M-045][get_my_mtproto_proxy][RENDER_PAYLOAD]')
requireText('backend/app/admin/router.py', '@router.post("/mtproto/assignments/{assignment_id}/revoke")')
requireText('backend/app/admin/audit.py', 'log_admin_action')
requireText('backend/app/mtproto/runtime_bridge.py', '[M-044][revoke_domain_policy][POLICY_REVOKED]')

requireText('frontend/src/lib/api.ts', 'verifyEmail: (token: string)')
requireText('frontend/src/lib/api.ts', 'MTProtoProxyResponse')
requireText('frontend/src/lib/api.ts', "api.get<MTProtoProxyResponse>('/mtproto/proxy')")
requireText('frontend/src/pages/Register.tsx', 'REGISTER_PENDING_STATE')
requireText('frontend/src/pages/Register.tsx', 'REGISTER_RESEND_AVAILABLE')
requireText('frontend/src/pages/VerifyEmail.tsx', 'REGISTER_VERIFIED_SUCCESS')
requireText('frontend/src/pages/VerifyEmail.tsx', 'token_replayed')
requireText('frontend/src/pages/Dashboard.tsx', 'data-phase31-mtproto-card="true"')
requireText('frontend/src/pages/Dashboard.tsx', '[M-045][dashboard_mtproto_card][CARD_RENDER]')
requireText('frontend/src/pages/Dashboard.tsx', '[M-045][dashboard_mtproto_card][COPY_ACTION]')
requireAbsent('frontend/src/pages/Register.tsx', "localStorage.setItem('access_token'")
requireAbsent('frontend/src/pages/Register.tsx', "localStorage.setItem('refresh_token'")

requireText('frontend-admin/src/pages/MTProto.tsx', 'data-phase33-mtproto-admin')
requireText('frontend-admin/src/pages/MTProto.tsx', '[M-047][admin_mtproto_ui][REDACTED_RENDER]')
requireText('frontend-admin/src/pages/MTProto.tsx', '[M-047][admin_mtproto_ui][CONFIRM_ACTION]')
requireText('frontend-admin/src/lib/api.ts', 'getMTProtoAssignments')
requireText('frontend-admin/src/lib/api.ts', 'revokeMTProtoAssignment')
requireAbsent('frontend-admin/src/pages/MTProto.tsx', 'tg://proxy')
requireAbsent('frontend-admin/src/pages/MTProto.tsx', 'console.log')
requireAbsent('frontend-admin/src/pages/MTProto.tsx', 'console.info')

requireText('docs/handoff/PHASE-34-RELEASE-CHECKLIST.xml', 'PHASE-34-RELEASE-CHECKLIST')
requireText('docs/handoff/PHASE-34-RELEASE-CHECKLIST.xml', 'local-gates')
requireText('docs/handoff/PHASE-34-RELEASE-CHECKLIST.xml', 'operator-live')
requireText('docs/handoff/PHASE-34-RELEASE-CHECKLIST.xml', 'rollback')
requireText('docs/handoff/PHASE-34-RELEASE-CHECKLIST.xml', 'MTPROTO_ASSIGNMENT')
requireText('docs/handoff/PHASE-34-RELEASE-CHECKLIST.xml', 'V-M-041')
requireText('docs/handoff/PHASE-34-RELEASE-CHECKLIST.xml', 'V-M-046')
requireAbsent('docs/handoff/PHASE-34-RELEASE-CHECKLIST.xml', '0123456789abcdef')
requireAbsent('docs/handoff/PHASE-34-RELEASE-CHECKLIST.xml', 'abcdef0123456789')
requireAbsent('docs/handoff/PHASE-34-RELEASE-CHECKLIST.xml', 'MTPROTO_BASE_SECRET_HEX=')

const approvedPhase35Surface = new Set([
  '.env.example',
  'docker-compose.yml',
  'install.sh',
  'deploy/deploy-on-server.sh',
  'backend/tests/test_domain_tls_edge_static.py',
  'scripts/phase32-edge-contract-smoke.mjs',
  'scripts/phase34-mtproto-stabilization-smoke.mjs',
  'scripts/phase35-installer-wildcard-tls-smoke.mjs',
])

const protectedChanges = changedFiles().filter((file) => (
  file === 'install.sh'
  || file === 'docker-compose.yml'
  || file === '.env.example'
  || file.startsWith('deploy/')
  || file.startsWith('nginx/')
  || file.startsWith('scripts/phase')
))
const unexpectedChanges = protectedChanges.filter((file) => !approvedPhase35Surface.has(file))

if (unexpectedChanges.length > 0) {
  throw new Error(`Phase-34/35 protected surface drift: ${unexpectedChanges.join(', ')}`)
}

if (protectedChanges.length > 0) {
  requireText('docs/graph-index.xml', 'M-048')
  requireText('docs/plan-index.xml', 'Phase-35')
}
// END_BLOCK_PHASE34_MTPROTO_STABILIZATION_SMOKE

console.log('[M-041][phase34_mtproto_integration][REGISTRATION_TO_MTPROTO] static smoke passed')
