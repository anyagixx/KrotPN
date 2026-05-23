// FILE: scripts/phase43-mtproto-admin-analytics-smoke.mjs
// VERSION: 1.6.0
// ROLE: SCRIPT
// MAP_MODE: LOCALS
// START_MODULE_CONTRACT
//   PURPOSE: Static smoke for Phase-43 MTProto admin analytics UX/API wiring and redaction boundaries
//   SCOPE: Frontend tabs, removed visible events panel, auto-refresh markers, API bindings, backend routes,
//          router-observation ingestion, and forbidden literal checks
//   DEPENDS: M-058, M-057, M-060, M-061, M-054
//   LINKS: V-M-058, V-M-057, V-M-060, V-M-061, V-M-054
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   assertContains - Helper: fail on missing markers
//   assertForbiddenAbsent - Helper: fail on forbidden high-risk literals
//   main - Runs static Phase-43 UI/API checks
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.6.0 - Guard compact scrollable IP history without visible CIDR prefixes.
//   LAST_CHANGE: v1.5.0 - Guard hidden technical signal UI and Russian alert-action hover help.
//   LAST_CHANGE: v1.4.0 - Guard M-054 trusted router-hop skip before persistence.
//   LAST_CHANGE: v1.3.0 - Guard RU SNI-router real client IP ingestion and trusted router-hop filtering.
//   LAST_CHANGE: v1.2.0 - Guard Abuse open inbox/archive split and empty-state copy.
//   LAST_CHANGE: v1.1.0 - Added Phase-43 live-feedback checks for pagination, area chart, hardened abuse copy, and IP observation events.
//   LAST_CHANGE: v1.0.0 - Added Phase-43 MTProto admin analytics static smoke
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
const apiPath = 'frontend-admin/src/lib/api.ts'
const typesPath = 'frontend-admin/src/types/index.ts'
const adminRouterPath = 'backend/app/admin/router.py'
const mtprotoRouterPath = 'backend/app/mtproto/router.py'
const analyticsPath = 'backend/app/mtproto/analytics_service.py'
const alertsPath = 'backend/app/mtproto/admin_alerts.py'
const ipPath = 'backend/app/mtproto/ip_observability.py'
const usageRepoPath = 'backend/app/mtproto/usage_repository.py'
const usageModelsPath = 'backend/app/mtproto/usage_models.py'
const runtimeSamplerPath = 'mtproto-runtime/apps/kpproton_proxy/src/mtproto/kpproton_usage_sampler.erl'
const routerTelemetryPath = 'deploy/sni-router-telemetry.py'

const ui = read(uiPath)
const api = read(apiPath)
const types = read(typesPath)
const adminRouter = read(adminRouterPath)
const mtprotoRouter = read(mtprotoRouterPath)
const analytics = read(analyticsPath)
const alerts = read(alertsPath)
const ip = read(ipPath)
const usageRepo = read(usageRepoPath)
const usageModels = read(usageModelsPath)
const runtimeSampler = read(runtimeSamplerPath)
const routerTelemetry = read(routerTelemetryPath)

for (const marker of [
  'data-phase43-mtproto-analytics',
  '[M-058][admin_mtproto_analytics_ui][RECENT_EVENTS_REMOVED]',
  '[M-058][admin_mtproto_analytics_ui][USER_DETAIL_DRAWER]',
  '[M-058][admin_mtproto_analytics_ui][AUTO_REFRESH]',
  '[M-058][admin_mtproto_analytics_ui][ALERT_REVIEW]',
  '[M-058][admin_mtproto_analytics_ui][ALERT_ARCHIVE]',
  '[M-058][admin_mtproto_analytics_ui][ALERT_ACTION_TOOLTIP]',
  '[M-058][admin_mtproto_analytics_ui][COMPACT_IP_HISTORY]',
  'data-mtproto-ip-history-scroll',
  'max-h-[180px] overflow-y-auto overscroll-contain',
  'Overview',
  'Users',
  'Abuse',
  'Settings',
  'IP history',
  'MetricAreaChart',
  'SourceIPNotice',
  'Обычная смена сети не создает тревогу',
  "getMTProtoAlerts('open'",
  "getMTProtoAlerts('acknowledged'",
  "getMTProtoAlerts('resolved'",
  'Нет открытых alerts',
  'Открыть карточку пользователя, IP history и детали этого proxy',
  'Пометить alert как просмотренный без блокировки пользователя',
  'Закрыть alert без блокировки, инцидент уйдет в архив',
  'Отключить MTProto proxy этого пользователя и закрыть alert',
  'Заблокировать последний IP на 24 часа и закрыть alert',
]) {
  assertContains(ui, marker, uiPath)
}
assertForbiddenAbsent(ui, 'Recent events', uiPath)
assertForbiddenAbsent(ui, 'Нет открытых alerts.', uiPath)
assertForbiddenAbsent(ui, '<h3 className="text-sm font-semibold text-white">Signals</h3>', uiPath)
assertForbiddenAbsent(ui, 'Нет signals', uiPath)
assertForbiddenAbsent(ui, ' signals</span>', uiPath)
assertForbiddenAbsent(ui, 'getMTProtoAbuseSignals(days)', uiPath)
assertForbiddenAbsent(ui, 'ip.ip_prefix || ip.source_status', uiPath)
for (const marker of [
  'getMTProtoTimeseries',
  'searchMTProtoUsers',
  'offset',
  'getMTProtoUserUsage',
  'getMTProtoResourceMetrics',
  'getMTProtoStorageBudget',
  'getMTProtoAlerts',
  'acknowledgeMTProtoAlert',
  'resolveMTProtoAlert',
  'disableMTProtoAlertProxy',
  'blockMTProtoAlertIP',
]) {
  assertContains(api, marker, apiPath)
}
for (const marker of [
  'AdminMTProtoTimeseriesResponse',
  'AdminMTProtoUserInvestigation',
  'AdminMTProtoAlertListResponse',
  'AdminMTProtoRuntimeResourceSnapshot',
  'AdminMTProtoStorageBudget',
]) {
  assertContains(types, marker, typesPath)
}
for (const marker of [
  '/mtproto/analytics/timeseries',
  '/mtproto/analytics/users/search',
  '/mtproto/analytics/users/{assignment_id}/usage',
  '/mtproto/analytics/resource-metrics',
  '/mtproto/analytics/storage-budget',
  '/mtproto/analytics/alerts',
]) {
  assertContains(adminRouter, marker, adminRouterPath)
}
assertContains(analytics, '[M-057][admin_mtproto_user_usage][IP_INVESTIGATION_SCOPE]', analyticsPath)
assertContains(analytics, 'IP_OBSERVATION', analyticsPath)
for (const marker of [
  '[M-060][create_abuse_alert][ALERT_CREATED]',
  '[M-060][acknowledge_alert][ALERT_ACKNOWLEDGED]',
  '[M-060][resolve_alert][ALERT_RESOLVED]',
  '[M-060][block_ip][CONFIRM_TTL_BLOCK]',
]) {
  assertContains(alerts, marker, alertsPath)
}
for (const marker of [
  '[M-061][record_ip_observation][OBSERVATION_UPSERT]',
  '[M-061][record_ip_observation][TRUSTED_PROXY_HOP_SKIP]',
  '[M-061][list_user_ip_observations][ADMIN_SCOPE]',
  '[M-061][current_ip_summary][SOURCE_UNAVAILABLE]',
]) {
  assertContains(ip, marker, ipPath)
}
assertContains(usageRepo, '[M-054][ingest_telemetry_batch][TRUSTED_PROXY_HOP_SKIP]', usageRepoPath)
for (const marker of [
  '/router-observations',
  '[M-055][router_observation_ingest][INGEST_SUMMARY]',
  'x-krotpn-mtproto-token',
]) {
  assertContains(mtprotoRouter, marker, mtprotoRouterPath)
}
for (const marker of [
  '[M-055][ru_sni_router][CLIENT_IP_OBSERVATION]',
  '[M-055][sni_router_telemetry][FORWARD_SUMMARY]',
  'MTPROTO_ROUTER_TRUSTED_PROXY_IPS',
]) {
  assertContains(routerTelemetry, marker, routerTelemetryPath)
}
assertContains(usageModels, 'IP_OBSERVATION = "ip_observation"', usageModelsPath)
assertContains(runtimeSampler, 'policy_counter_client_sample', runtimeSamplerPath)
assertContains(runtimeSampler, 'client_ip', runtimeSamplerPath)
for (const [path, text] of [[uiPath, ui], [apiPath, api], [adminRouterPath, adminRouter], [mtprotoRouterPath, mtprotoRouter], [analyticsPath, analytics], [alertsPath, alerts], [ipPath, ip]]) {
  for (const forbidden of [
    'https://t.me/proxy?',
    'tg://proxy?server=',
    'MTPROTO_BASE_SECRET_HEX=',
    'MTPROTO_RUNTIME_TOKEN=',
    '203.0.113.',
    '198.51.100.',
  ]) {
    assertForbiddenAbsent(text, forbidden, path)
  }
}
console.log('phase43 mtproto admin analytics smoke: ok')
// END_BLOCK_MAIN
