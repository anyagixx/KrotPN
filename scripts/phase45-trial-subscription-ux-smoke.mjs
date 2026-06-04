#!/usr/bin/env node
/*
 * FILE: scripts/phase45-trial-subscription-ux-smoke.mjs
 * VERSION: 1.1.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke checks for Phase-45 subscription countdown and calendar UX wiring
 *   SCOPE: Frontend API type fields, dashboard-owned subscription panel, pending-trial copy, subscription calendar marker, and stale 3-day copy guard
 *   DEPENDS: M-009, M-063
 *   LINKS: V-M-063
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   assertContains - Fails if a source file lacks a required marker
 *   assertNotContains - Fails if a source file still contains stale copy
 *   main - Runs Phase-45 UX smoke assertions
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.1.0 - Updated assertions for Phase-68 dashboard-owned compact subscription panel.
 *   LAST_CHANGE: v1.0.0 - Added Phase-45 subscription UX static smoke
 * END_CHANGE_SUMMARY
 */

import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const root = process.cwd()

function read(path) {
  return readFileSync(join(root, path), 'utf8')
}

function assertContains(path, needle) {
  const source = read(path)
  if (!source.includes(needle)) {
    throw new Error(`${path} is missing required Phase-45 marker: ${needle}`)
  }
}

function assertNotContains(path, needle) {
  const source = read(path)
  if (source.includes(needle)) {
    throw new Error(`${path} still contains stale Phase-45 copy: ${needle}`)
  }
}

assertContains('frontend/src/lib/api.ts', 'pending_activation: boolean')
assertContains('frontend/src/lib/api.ts', 'remaining_minutes: number')
assertContains('frontend/src/pages/Dashboard.tsx', '<SubscriptionPanel compact />')
assertContains('frontend/src/components/SubscriptionPanel.tsx', 'id="dashboard-subscription"')
assertContains('frontend/src/components/SubscriptionPanel.tsx', 'data-phase45-subscription-calendar="true"')
assertContains('frontend/src/components/SubscriptionPanel.tsx', 'Конфиг уже доступен. Таймер на 4 дня стартует после первого подключения.')
assertContains('frontend/src/components/SubscriptionPanel.tsx', 'remaining_minutes')
assertContains('frontend/src/pages/Subscription.tsx', 'data-phase68-subscription-route="compatibility-wrapper"')
assertNotContains('frontend/src/pages/Subscription.tsx', "trialDays', { days: 3")
assertNotContains('frontend/src/components/SubscriptionPanel.tsx', 'Trial начнется после первого VPN подключения')

console.log('[M-063][phase45-ux-smoke][PASS] subscription countdown and calendar wiring present')
