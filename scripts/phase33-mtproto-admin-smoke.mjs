#!/usr/bin/env node
// FILE: scripts/phase33-mtproto-admin-smoke.mjs
// VERSION: 1.0.0
// ROLE: SCRIPT
// MAP_MODE: LOCALS
// START_MODULE_CONTRACT
//   PURPOSE: Static smoke gate for Phase-33 MTProto admin operations and compact UI
//   SCOPE: Backend route markers, frontend-admin API bindings, page/navigation anchors,
//          secret-redaction checks, and protected deploy/install surface guard
//   DEPENDS: M-047, M-006, M-010, node:fs, node:path, node:child_process
//   LINKS: V-M-047
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   read - Load a project file as UTF-8
//   requireText/requireAbsent - Minimal static assertions
//   changedFiles - Read current git diff names against HEAD
//   BLOCK_PHASE33_MTPROTO_ADMIN_SMOKE - Phase-33 backend/frontend assertions
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.0.0 - Added Phase-33 MTProto admin static smoke gate
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

// START_BLOCK_PHASE33_MTPROTO_ADMIN_SMOKE
requireText('backend/app/admin/router.py', '@router.get("/mtproto/assignments")')
requireText('backend/app/admin/router.py', '@router.get("/mtproto/assignments/{assignment_id}")')
requireText('backend/app/admin/router.py', '@router.get("/mtproto/health")')
requireText('backend/app/admin/router.py', '@router.post("/mtproto/assignments/{assignment_id}/reissue")')
requireText('backend/app/admin/router.py', '@router.post("/mtproto/assignments/{assignment_id}/revoke")')
requireText('backend/app/admin/router.py', '[M-047][admin_list_mtproto][FILTER_ASSIGNMENTS]')
requireText('backend/app/admin/router.py', '[M-047][admin_list_mtproto][REDACT_PAYLOAD]')
requireText('backend/app/admin/router.py', '[M-047][admin_reissue_mtproto][AUDIT_REISSUE]')
requireText('backend/app/admin/router.py', '[M-047][admin_revoke_mtproto][AUDIT_REVOKE]')

requireText('frontend-admin/src/lib/api.ts', 'getMTProtoAssignments')
requireText('frontend-admin/src/lib/api.ts', 'reissueMTProtoAssignment')
requireText('frontend-admin/src/lib/api.ts', 'revokeMTProtoAssignment')
requireText('frontend-admin/src/lib/api.ts', '/admin/mtproto/assignments')
requireText('frontend-admin/src/types/index.ts', 'AdminMTProtoAssignment')
requireText('frontend-admin/src/main.tsx', 'path="mtproto"')
requireText('frontend-admin/src/components/Layout.tsx', "to: '/mtproto'")

requireText('frontend-admin/src/pages/MTProto.tsx', 'data-phase33-mtproto-admin')
requireText('frontend-admin/src/pages/MTProto.tsx', '[M-047][admin_mtproto_ui][REDACTED_RENDER]')
requireText('frontend-admin/src/pages/MTProto.tsx', '[M-047][admin_mtproto_ui][CONFIRM_ACTION]')
requireText('frontend-admin/src/pages/MTProto.tsx', 'adminApi.getMTProtoAssignments')
requireText('frontend-admin/src/pages/MTProto.tsx', 'adminApi.reissueMTProtoAssignment')
requireText('frontend-admin/src/pages/MTProto.tsx', 'adminApi.revokeMTProtoAssignment')
requireAbsent('frontend-admin/src/pages/MTProto.tsx', 'tg://proxy')
requireAbsent('frontend-admin/src/pages/MTProto.tsx', 'console.log')
requireAbsent('frontend-admin/src/pages/MTProto.tsx', 'console.info')

const protectedChanges = changedFiles().filter((file) => (
  file === 'install.sh'
  || file === 'docker-compose.yml'
  || file.startsWith('deploy/')
  || file.startsWith('nginx/')
))

if (protectedChanges.length > 0) {
  throw new Error(`Phase-33 must not change deploy/install/edge surfaces: ${protectedChanges.join(', ')}`)
}
// END_BLOCK_PHASE33_MTPROTO_ADMIN_SMOKE

console.log('[M-047][admin_mtproto_ui][REDACTED_RENDER] static smoke passed')
