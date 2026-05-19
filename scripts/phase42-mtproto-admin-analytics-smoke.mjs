// FILE: scripts/phase42-mtproto-admin-analytics-smoke.mjs
// VERSION: 1.0.0
// ROLE: SCRIPT
// MAP_MODE: LOCALS
// START_MODULE_CONTRACT
//   PURPOSE: Static smoke for compact MTProto admin analytics UI and API wiring
//   SCOPE: Frontend component, API bindings, backend routes, redaction markers, and forbidden literal checks
//   DEPENDS: M-058, M-057
//   LINKS: V-M-058, V-M-057
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   assertContains - Helper: fail on missing markers
//   assertForbiddenAbsent - Helper: fail on forbidden high-risk literals
//   main - Runs static UI/API checks
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.0.0 - Added Phase-42 admin analytics UI static smoke
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

function assertForbiddenAbsent(text, marker, path) {
  if (text.includes(marker)) {
    throw new Error(`Forbidden marker ${marker} present in ${path}`)
  }
}
// END_BLOCK_SMOKE_HELPERS

// START_BLOCK_MAIN
const uiPath = 'frontend-admin/src/pages/MTProtoAnalytics.tsx'
const mtprotoPagePath = 'frontend-admin/src/pages/MTProto.tsx'
const apiPath = 'frontend-admin/src/lib/api.ts'
const typesPath = 'frontend-admin/src/types/index.ts'
const adminRouterPath = 'backend/app/admin/router.py'

const ui = read(uiPath)
const mtprotoPage = read(mtprotoPagePath)
const api = read(apiPath)
const types = read(typesPath)
const adminRouter = read(adminRouterPath)

for (const marker of [
  'data-phase42-mtproto-analytics',
  '[M-058][admin_mtproto_analytics_ui][REDACTED_RENDER]',
  'Promotion tag',
  'observe-only',
]) {
  assertContains(ui, marker, uiPath)
}
assertContains(mtprotoPage, 'MTProtoAnalyticsPanel', mtprotoPagePath)
for (const marker of [
  'getMTProtoAnalyticsSummary',
  'getMTProtoAssignmentUsage',
  'getMTProtoEvents',
  'getMTProtoTopUsers',
  'getMTProtoPromotionTag',
]) {
  assertContains(api, marker, apiPath)
}
for (const marker of ['AdminMTProtoAnalyticsSummary', 'AdminMTProtoAssignmentUsage', 'AdminMTProtoPromotionTagState']) {
  assertContains(types, marker, typesPath)
}
for (const marker of [
  '/mtproto/analytics/summary',
  '/mtproto/analytics/events',
  '/mtproto/analytics/top-users',
  '/mtproto/promotion-tag',
  '[M-057][admin_mtproto_analytics][SUMMARY]',
]) {
  assertContains(adminRouter, marker, adminRouterPath)
}
for (const [path, text] of [[uiPath, ui], [apiPath, api], [adminRouterPath, adminRouter]]) {
  for (const forbidden of ['https://t.me/proxy?', 'tg://proxy?server=', 'MTPROTO_BASE_SECRET_HEX=', 'MTPROTO_RUNTIME_TOKEN=']) {
    assertForbiddenAbsent(text, forbidden, path)
  }
}
console.log('phase42 mtproto admin analytics smoke: ok')
// END_BLOCK_MAIN
