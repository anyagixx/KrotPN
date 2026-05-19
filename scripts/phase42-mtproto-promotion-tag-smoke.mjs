// FILE: scripts/phase42-mtproto-promotion-tag-smoke.mjs
// VERSION: 1.0.0
// ROLE: SCRIPT
// MAP_MODE: LOCALS
// START_MODULE_CONTRACT
//   PURPOSE: Static smoke for Phase-42 MTProxy promotion tag validation and runtime propagation
//   SCOPE: Backend validator, admin routes, runtime PROXY_AD_TAG fallback, compose env, and redaction markers
//   DEPENDS: M-059
//   LINKS: V-M-059
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   assertContains - Helper: fail on missing marker
//   main - Runs static promotion tag checks
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.0.0 - Added Phase-42 promotion tag static smoke
// END_CHANGE_SUMMARY

import { readFileSync } from 'node:fs'

// START_BLOCK_SMOKE_HELPERS
function read(path) {
  return readFileSync(path, 'utf8')
}

function assertContains(text, marker, path) {
  if (!text.includes(marker)) {
    throw new Error(`Missing ${marker} in ${path}`)
  }
}
// END_BLOCK_SMOKE_HELPERS

// START_BLOCK_MAIN
const backendPath = 'backend/app/mtproto/promotion_tag.py'
const adminRouterPath = 'backend/app/admin/router.py'
const runtimePath = 'mtproto-runtime/src/kpproton_app.erl'
const composePath = 'deploy/mtproto-de-compose.yml'
const envPath = '.env.example'

const backend = read(backendPath)
const adminRouter = read(adminRouterPath)
const runtime = read(runtimePath)
const compose = read(composePath)
const env = read(envPath)

for (const marker of [
  'validate_promotion_tag',
  '[M-059][validate_promotion_tag][VALIDATE_TAG]',
  '[M-059][update_promotion_tag][AUDIT_UPDATE]',
  '[M-059][promotion_tag_state][REDACTED_STATE]',
]) {
  assertContains(backend, marker, backendPath)
}
for (const marker of ['/mtproto/promotion-tag', 'MTProtoPromotionTagUpdateRequest', 'mtproto.promotion_tag.update']) {
  assertContains(adminRouter, marker, adminRouterPath)
}
for (const marker of ['proxy_ad_tag/0', 'PROXY_AD_TAG', '00000000000000000000000000000000']) {
  assertContains(runtime, marker, runtimePath)
}
assertContains(compose, 'PROXY_AD_TAG: ${MTPROTO_AD_TAG:-00000000000000000000000000000000}', composePath)
assertContains(env, 'MTPROTO_AD_TAG=00000000000000000000000000000000', envPath)
console.log('phase42 mtproto promotion tag smoke: ok')
// END_BLOCK_MAIN
