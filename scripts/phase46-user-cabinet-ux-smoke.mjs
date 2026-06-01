#!/usr/bin/env node
/*
 * FILE: scripts/phase46-user-cabinet-ux-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke checks for Phase-46 password example and MTProto user-cabinet UX polish
 *   SCOPE: Registration password example, dual MTProto link schemes, Russian labels, bounded status refresh, redaction, and protected deploy surfaces
 *   DEPENDS: M-009, M-036, M-045, M-062, M-064
 *   LINKS: V-M-064
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   assertContains - Fails if a source file lacks a required marker
 *   assertNotContains - Fails if a source file contains a forbidden marker
 *   assertPasswordExampleSatisfiesStaticPolicy - Checks the exported example against the Phase-44 policy shape
 *   main - Runs Phase-46 UX smoke assertions
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-46 user cabinet UX static smoke gate
 * END_CHANGE_SUMMARY
 */

import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const root = process.cwd()

function read(relativePath) {
  return readFileSync(join(root, relativePath), 'utf8')
}

function assertContains(relativePath, needle) {
  const source = read(relativePath)
  if (!source.includes(needle)) {
    throw new Error(`${relativePath} is missing required Phase-46 marker: ${needle}`)
  }
}

function assertNotContains(relativePath, needle) {
  const source = read(relativePath)
  if (source.includes(needle)) {
    throw new Error(`${relativePath} contains forbidden Phase-46 marker: ${needle}`)
  }
}

function assertPasswordExampleSatisfiesStaticPolicy(source) {
  const match = source.match(/passwordPolicyExample\s*=\s*'([^']+)'/)
  if (!match) {
    throw new Error('passwordPolicy.ts must export passwordPolicyExample')
  }

  const example = match[1]
  const checks = [
    [example.length >= 10, 'minimum length'],
    [/[a-zа-я]/.test(example), 'lowercase letter'],
    [/[A-ZА-Я]/.test(example), 'uppercase letter'],
    [/\d/.test(example), 'digit'],
    [/[^A-Za-zА-Яа-я0-9]/.test(example), 'special character'],
    [!/\s/.test(example), 'no spaces'],
  ]

  for (const [ok, label] of checks) {
    if (!ok) {
      throw new Error(`passwordPolicyExample fails static policy check: ${label}`)
    }
  }
}

// START_BLOCK_PHASE46_STATIC_ASSERTIONS
const passwordPolicy = read('frontend/src/lib/passwordPolicy.ts')
assertPasswordExampleSatisfiesStaticPolicy(passwordPolicy)
assertContains('frontend/src/lib/passwordPolicy.ts', 'passwordPolicyExample')

assertContains('frontend/src/pages/Register.tsx', 'passwordPolicyExample')
assertContains('frontend/src/pages/Register.tsx', 'data-phase46-password-example="true"')
assertContains('frontend/src/pages/Register.tsx', 'Не используйте этот пример дословно')
assertContains('frontend/src/pages/Register.tsx', 'passwordStrengthIssues')

assertContains('frontend/src/pages/Dashboard.tsx', 'buildMtprotoTelegramAppLink')
assertContains('frontend/src/pages/Dashboard.tsx', 'buildMtprotoBrowserLink')
assertContains('frontend/src/pages/Dashboard.tsx', 'tg://proxy?')
assertContains('frontend/src/pages/Dashboard.tsx', 'https://t.me/proxy?')
assertContains('frontend/src/pages/Dashboard.tsx', 'telegram_app_link')
assertNotContains('frontend/src/pages/Dashboard.tsx', 'telegram_web_link')

assertContains('frontend/src/pages/Dashboard.tsx', "renderMtprotoCopyButton('link', 'Ссылка'")
assertContains('frontend/src/pages/Dashboard.tsx', '>Сервер<')
assertContains('frontend/src/pages/Dashboard.tsx', '>Порт<')
assertContains('frontend/src/pages/Dashboard.tsx', '>Секрет<')
assertNotContains('frontend/src/pages/Dashboard.tsx', '>Full link<')
assertNotContains('frontend/src/pages/Dashboard.tsx', '>Server<')
assertNotContains('frontend/src/pages/Dashboard.tsx', '>Port<')
assertNotContains('frontend/src/pages/Dashboard.tsx', '>Secret<')

assertContains('frontend/src/pages/Dashboard.tsx', 'MTPROTO_STATUS_REFRESH_MS = 30000')
assertContains('frontend/src/pages/Dashboard.tsx', 'refetchInterval: MTPROTO_STATUS_REFRESH_MS')
assertContains('frontend/src/pages/Dashboard.tsx', 'refetchIntervalInBackground: false')
assertContains('frontend/src/pages/Dashboard.tsx', 'data-phase46-mtproto-status-refresh-ms')

assertNotContains('frontend/src/pages/Dashboard.tsx', 'console.info(MTPROTO_COPY_ACTION_MARKER, { field, value')
assertNotContains('frontend/src/pages/Dashboard.tsx', 'console.info(MTPROTO_OPEN_TELEGRAM_MARKER, { link')

for (const protectedPath of ['install.sh', 'docker-compose.yml', 'nginx/nginx.conf']) {
  if (!existsSync(join(root, protectedPath))) {
    throw new Error(`Protected surface missing from repository: ${protectedPath}`)
  }
}
// END_BLOCK_PHASE46_STATIC_ASSERTIONS

console.log('[M-064][phase46_user_cabinet_ux][PASSWORD_EXAMPLE] ok')
console.log('[M-064][phase46_user_cabinet_ux][DUAL_MTPROTO_LINKS] ok')
console.log('[M-064][phase46_user_cabinet_ux][RUSSIAN_LABELS] ok')
console.log('[M-064][phase46_user_cabinet_ux][DYNAMIC_STATUS] ok')
