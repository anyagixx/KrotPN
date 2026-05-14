#!/usr/bin/env node
// FILE: scripts/phase31-mtproto-cabinet-smoke.mjs
// VERSION: 1.0.0
// ROLE: SCRIPT
// MAP_MODE: LOCALS
// START_MODULE_CONTRACT
//   PURPOSE: Static smoke gate for Phase-31 MTProto user-cabinet UX
//   SCOPE: Assert frontend API binding, compact dashboard anchors, redacted trace markers,
//          copy/open actions, and protected deploy/install surfaces
//   DEPENDS: M-045, M-009, M-036, node:fs, node:path, node:child_process
//   LINKS: V-M-045
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   read - Load a project file as UTF-8
//   requireText/requireAbsent - Minimal static assertions
//   changedFiles - Read current git diff names
//   BLOCK_PHASE31_MTPROTO_CABINET_SMOKE - Phase-31 dashboard/API assertions
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.0.0 - Added Phase-31 MTProto cabinet static smoke gate
// END_CHANGE_SUMMARY

import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = process.cwd()

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8')
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
  return execFileSync('git', ['diff', '--name-only'], { cwd: root, encoding: 'utf8' })
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}

// START_BLOCK_PHASE31_MTPROTO_CABINET_SMOKE
requireText('frontend/src/lib/api.ts', 'MTProtoProxyResponse')
requireText('frontend/src/lib/api.ts', 'mtprotoApi')
requireText('frontend/src/lib/api.ts', "api.get<MTProtoProxyResponse>('/mtproto/proxy')")

requireText('frontend/src/pages/Dashboard.tsx', 'data-phase31-mtproto-card')
requireText('frontend/src/pages/Dashboard.tsx', '[M-045][dashboard_mtproto_card][CARD_RENDER]')
requireText('frontend/src/pages/Dashboard.tsx', '[M-045][dashboard_mtproto_card][COPY_ACTION]')
requireText('frontend/src/pages/Dashboard.tsx', 'mtprotoApi.getProxy')
requireText('frontend/src/pages/Dashboard.tsx', 'navigator.clipboard.writeText')
requireText('frontend/src/pages/Dashboard.tsx', 'href={mtproto.tg_link}')
requireText('frontend/src/pages/Dashboard.tsx', 'break-all')
requireText('frontend/src/pages/Dashboard.tsx', 'sm:grid-cols-5')

requireAbsent('frontend/src/pages/Dashboard.tsx', 'console.log(mtproto')
requireAbsent('frontend/src/pages/Dashboard.tsx', 'console.info(mtproto')

const protectedChanges = changedFiles().filter((file) => (
  file === 'install.sh'
  || file === 'docker-compose.yml'
  || file.startsWith('deploy/')
  || file.startsWith('nginx/')
))

if (protectedChanges.length > 0) {
  throw new Error(`Phase-31 must not change deploy/install surfaces: ${protectedChanges.join(', ')}`)
}
// END_BLOCK_PHASE31_MTPROTO_CABINET_SMOKE

console.log('[M-045][dashboard_mtproto_card][CARD_RENDER] static smoke passed')
