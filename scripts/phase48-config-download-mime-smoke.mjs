#!/usr/bin/env node
/*
 * FILE: scripts/phase48-config-download-mime-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke checks for Phase-48 VPN .conf download MIME and filename hardening
 *   SCOPE: Backend attachment headers, frontend Blob MIME, safe filename markers, redaction, and protected deploy surfaces
 *   DEPENDS: M-066, M-003, M-009, M-022, M-036
 *   LINKS: V-M-066
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads a repository file for static assertions
 *   assertContains - Fails if a source file lacks a required marker
 *   assertNotContains - Fails if a source file contains a forbidden marker
 *   assertProtectedDeployDiffClean - Fails if Phase-48 touched deploy/install/nginx/docker-compose surfaces
 *   main - Runs Phase-48 config download MIME smoke assertions
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-48 config download MIME static smoke gate
 * END_CHANGE_SUMMARY
 */

import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const root = process.cwd()

function read(relativePath) {
  return readFileSync(join(root, relativePath), 'utf8')
}

function assertContains(source, needle, label) {
  if (!source.includes(needle)) {
    throw new Error(`${label} is missing required Phase-48 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains forbidden Phase-48 marker: ${needle}`)
  }
}

function assertProtectedDeployDiffClean() {
  const protectedPaths = [
    'install.sh',
    'docker-compose.yml',
    'nginx',
    'deploy',
    'deploy/mtproto-de-compose.yml',
    '.env.example',
  ]
  for (const protectedPath of protectedPaths) {
    if (!existsSync(join(root, protectedPath))) {
      throw new Error(`Protected deploy surface missing from repository: ${protectedPath}`)
    }
  }

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (diff) {
    throw new Error(`Phase-48 must not change deploy/install surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE48_STATIC_ASSERTIONS
const routerPath = 'backend/app/vpn/router.py'
const apiPath = 'frontend/src/lib/api.ts'
const configPath = 'frontend/src/pages/Config.tsx'

const router = read(routerPath)
const api = read(apiPath)
const configPage = read(configPath)

assertContains(router, 'CONFIG_DOWNLOAD_MIME_TYPE = "application/octet-stream"', routerPath)
assertContains(router, 'def sanitize_config_download_filename(', routerPath)
assertContains(router, 'def build_config_download_response(', routerPath)
assertContains(router, '"Content-Disposition"', routerPath)
assertContains(router, 'filename*=UTF-8', routerPath)
assertContains(router, '"X-Content-Type-Options": "nosniff"', routerPath)
assertContains(router, '"Cache-Control": CONFIG_DOWNLOAD_CACHE_CONTROL', routerPath)
assertContains(router, '[M-066][sanitize_config_download_filename][FILENAME_SAFE]', routerPath)
assertContains(router, '[M-066][build_config_download_response][DOWNLOAD_HEADERS]', routerPath)
assertContains(router, '[M-066][download_vpn_config][ATTACHMENT_RESPONSE]', routerPath)
assertNotContains(router, 'media_type="text/plain"', routerPath)
assertNotContains(router, 'StreamingResponse(', routerPath)
assertNotContains(router, '.conf.txt', routerPath)

assertContains(api, "CONFIG_DOWNLOAD_MIME_TYPE = 'application/octet-stream'", apiPath)
assertContains(api, "Accept: CONFIG_DOWNLOAD_MIME_TYPE", apiPath)
assertContains(api, "responseType: 'blob'", apiPath)
assertNotContains(api, '.conf.txt', apiPath)

assertContains(configPage, 'buildConfigDownloadBlob', configPath)
assertContains(configPage, 'buildConfigDownloadFilename', configPath)
assertContains(configPage, 'new Blob([source], { type: CONFIG_DOWNLOAD_MIME_TYPE })', configPath)
assertContains(configPage, "return `${safeBase || 'krotpn'}.conf`", configPath)
assertNotContains(configPage, 'new Blob([blobSource])', configPath)
assertNotContains(configPage, '.conf.txt', configPath)

assertProtectedDeployDiffClean()
// END_BLOCK_PHASE48_STATIC_ASSERTIONS

console.log('[M-066][phase48_config_download_mime][STATIC_GUARD] ok')
console.log('[M-066][phase48_config_download_mime][ATTACHMENT_HEADERS] ok')
console.log('[M-066][phase48_config_download_mime][FRONTEND_BLOB] ok')
