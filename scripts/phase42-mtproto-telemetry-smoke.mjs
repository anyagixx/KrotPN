// FILE: scripts/phase42-mtproto-telemetry-smoke.mjs
// VERSION: 1.1.0
// ROLE: SCRIPT
// MAP_MODE: LOCALS
// START_MODULE_CONTRACT
//   PURPOSE: Static smoke for Phase-42 MTProto runtime telemetry bridge wiring
//   SCOPE: Runtime telemetry module, metric backend, sampler, private routes, backend adapter methods, scheduler job, and redaction markers
//   DEPENDS: M-055
//   LINKS: V-M-055
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   assertContains - Helper: fail if a required marker is missing
//   main - Runs static checks over runtime/backend files
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.1.0 - Guard live mtproto_proxy metric backend and sampler wiring.
//   LAST_CHANGE: v1.0.0 - Added Phase-42 runtime telemetry static smoke
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
const runtimeModulePath = 'mtproto-runtime/apps/kpproton_proxy/src/mtproto/kpproton_usage_telemetry.erl'
const metricBackendPath = 'mtproto-runtime/apps/kpproton_proxy/src/mtproto/kpproton_usage_metric_backend.erl'
const samplerPath = 'mtproto-runtime/apps/kpproton_proxy/src/mtproto/kpproton_usage_sampler.erl'
const appPath = 'mtproto-runtime/src/kpproton_app.erl'
const supPath = 'mtproto-runtime/src/kpproton_sup.erl'
const policyHandlerPath = 'mtproto-runtime/src/kpproton_policy_handler.erl'
const webPath = 'mtproto-runtime/src/kpproton_web.erl'
const bridgePath = 'backend/app/mtproto/runtime_bridge.py'
const ingestionPath = 'backend/app/mtproto/usage_ingestion.py'
const schedulerPath = 'backend/app/tasks/scheduler.py'

const runtimeModule = read(runtimeModulePath)
const metricBackend = read(metricBackendPath)
const sampler = read(samplerPath)
const app = read(appPath)
const sup = read(supPath)
const policyHandler = read(policyHandlerPath)
const web = read(webPath)
const bridge = read(bridgePath)
const ingestion = read(ingestionPath)
const scheduler = read(schedulerPath)

for (const marker of ['emit_event/1', 'add_metric/2', 'active_domain_counts/0', 'snapshot/0', 'drain/2', '[M-055][runtime_telemetry][EMIT_EVENT]']) {
  assertContains(runtimeModule, marker, runtimeModulePath)
}
for (const marker of ['notify/4', 'received, upstream, bytes', 'protocol_error']) {
  assertContains(metricBackend, marker, metricBackendPath)
}
for (const marker of ['active_domain_counts()', 'drain_metric_counters()', 'single_active_domain', 'global_runtime']) {
  assertContains(sampler, marker, samplerPath)
}
assertContains(app, 'metric_backend, kpproton_usage_metric_backend', appPath)
assertContains(sup, 'kpproton_usage_sampler', supPath)
for (const marker of ['telemetry_snapshot', 'telemetry_drain', 'x-krotpn-mtproto-token']) {
  assertContains(policyHandler, marker, policyHandlerPath)
}
for (const marker of ['/krotpn/mtproto/policy/telemetry/snapshot', '/krotpn/mtproto/policy/telemetry/drain']) {
  assertContains(web, marker, webPath)
}
for (const marker of ['telemetry_snapshot', 'telemetry_drain', 'MTProtoRuntimeTelemetryEvent']) {
  assertContains(bridge, marker, bridgePath)
}
assertContains(ingestion, '[M-055][telemetry_ingest][INGEST_SUMMARY]', ingestionPath)
assertContains(scheduler, 'ingest_mtproto_telemetry', schedulerPath)
console.log('phase42 mtproto telemetry smoke: ok')
// END_BLOCK_MAIN
