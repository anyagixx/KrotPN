#!/usr/bin/env node
/*
 * FILE: scripts/phase50-tariff-catalog-smoke.mjs
 * VERSION: 1.2.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke checks for Phase-50 paid tariff catalog and compact billing UI
 *   SCOPE: Canonical tariff constants, backend checkout markers, user/admin UI contract, i18n tariff copy, README documentation, and protected deploy surfaces
 *   DEPENDS: M-068, M-004, M-009, M-010, M-021, M-038
 *   LINKS: V-M-068
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository files for static assertions
 *   assertContains - Fails if a file lacks a required marker
 *   assertNotContains - Fails if a file contains forbidden stale UI or unsafe markers
 *   assertProtectedDeployDiffClean - Fails if Phase-50 touched deploy/install surfaces
 *   main - Runs Phase-50 paid tariff catalog smoke assertions
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.2.0 - Aligned device-limit warning assertion with i18n-backed Phase-68/72 tariff copy.
 *   LAST_CHANGE: v1.1.0 - Updated user tariff assertions for Phase-68 shared SubscriptionPanel display aliases.
 *   LAST_CHANGE: v1.0.0 - Added Phase-50 paid tariff catalog static smoke gate
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
    throw new Error(`${label} is missing required Phase-50 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains forbidden Phase-50 marker: ${needle}`)
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
    throw new Error(`Phase-50 must not change deploy/install surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE50_STATIC_ASSERTIONS
const catalogPath = 'backend/app/billing/catalog.py'
const servicePath = 'backend/app/billing/service.py'
const routerPath = 'backend/app/billing/router.py'
const subscriptionPath = 'frontend/src/pages/Subscription.tsx'
const subscriptionPanelPath = 'frontend/src/components/SubscriptionPanel.tsx'
const frontendI18nPath = 'frontend/src/i18n/index.ts'
const adminPlansPath = 'frontend-admin/src/pages/Plans.tsx'
const adminTypesPath = 'frontend-admin/src/types/index.ts'
const readmePath = 'README.md'

const catalog = read(catalogPath)
const service = read(servicePath)
const router = read(routerPath)
const subscription = read(subscriptionPath)
const subscriptionPanel = read(subscriptionPanelPath)
const frontendI18n = read(frontendI18nPath)
const userSubscriptionSurface = `${subscription}\n${subscriptionPanel}\n${frontendI18n}`
const adminPlans = read(adminPlansPath)
const adminTypes = read(adminTypesPath)
const readme = read(readmePath)

for (const slug of ['krotpn-1', 'krotpn-6', 'krotpn-9']) {
  assertContains(catalog, `slug="${slug}"`, catalogPath)
  assertContains(readme, slug, readmePath)
}
for (const price of ['price=369.0', 'price=693.0', 'price=936.0']) {
  assertContains(catalog, price, catalogPath)
}
for (const limit of ['device_limit=1', 'device_limit=6', 'device_limit=9']) {
  assertContains(catalog, limit, catalogPath)
}

assertContains(service, 'ensure_canonical_tariffs', servicePath)
assertContains(service, 'validate_checkout_plan', servicePath)
assertContains(service, '[M-068][tariff_catalog][TARIFF_CATALOG_UPSERT]', servicePath)
assertContains(service, '[M-068][checkout][TARIFF_CHECKOUT_VALIDATED]', servicePath)
assertContains(service, '[M-068][checkout][TARIFF_DOWNGRADE_BLOCKED]', servicePath)
assertContains(service, '[BillingService][create_payment][BILLING_PAYMENT_CREATED]', servicePath)
assertContains(service, '[BillingService][process_payment_webhook][BILLING_SUBSCRIPTION_UPDATED]', servicePath)
assertContains(service, '"plan_slug": plan.slug', servicePath)
assertContains(service, '"device_limit": plan.device_limit', servicePath)
assertContains(service, '"duration_days": plan.duration_days', servicePath)

assertContains(router, 'canonical_only=True', routerPath)
assertContains(router, 'CheckoutPlanRejected', routerPath)
assertContains(router, 'status.HTTP_409_CONFLICT', routerPath)
assertContains(router, 'is_canonical', routerPath)
assertContains(router, 'sort_order', routerPath)

assertContains(userSubscriptionSurface, 'deviceApi.list()', 'frontend subscription surface')
assertContains(userSubscriptionSurface, 'plan.device_limit', 'frontend subscription surface')
assertContains(userSubscriptionSurface, 'plan.is_popular', 'frontend subscription surface')
assertContains(userSubscriptionSurface, 'Сначала отзовите лишние', 'frontend subscription surface')
assertContains(userSubscriptionSurface, 'billingApi.createPayment(planId)', 'frontend subscription surface')
assertContains(userSubscriptionSurface, 'KrotPN Self', 'frontend subscription surface')
assertContains(userSubscriptionSurface, 'KrotPN Family', 'frontend subscription surface')
assertContains(userSubscriptionSurface, 'KrotPN Team', 'frontend subscription surface')
assertContains(userSubscriptionSurface, 'Персональный тариф', 'frontend subscription surface')
assertContains(userSubscriptionSurface, 'Тариф для семьи', 'frontend subscription surface')
assertContains(userSubscriptionSurface, 'Тариф для команды', 'frontend subscription surface')
assertNotContains(userSubscriptionSurface, 'Оплата создается backend по выбранному plan_id', 'frontend subscription surface')

assertContains(adminTypes, 'slug?: string | null', adminTypesPath)
assertContains(adminTypes, 'is_canonical?: boolean', adminTypesPath)
assertContains(adminTypes, 'sort_order?: number', adminTypesPath)

assertContains(adminPlans, 'Защищенная матрица Phase-50', adminPlansPath)
assertContains(adminPlans, 'canonical', adminPlansPath)
assertContains(adminPlans, 'sort {plan.sort_order}', adminPlansPath)
assertNotContains(adminPlans, 'deletePlan', adminPlansPath)
assertNotContains(adminPlans, 'Создать план', adminPlansPath)
assertNotContains(adminPlans, 'CRUD-форма', adminPlansPath)
assertNotContains(adminPlans, 'Trash2', adminPlansPath)
assertNotContains(adminPlans, 'Edit', adminPlansPath)

assertContains(readme, '### Тарифы KrotPN', readmePath)
assertContains(readme, '369 ₽', readmePath)
assertContains(readme, '693 ₽', readmePath)
assertContains(readme, '936 ₽', readmePath)

assertProtectedDeployDiffClean()
// END_BLOCK_PHASE50_STATIC_ASSERTIONS

console.log('[M-068][phase50_tariff_catalog][CANONICAL_MATRIX] ok')
console.log('[M-068][phase50_tariff_catalog][CHECKOUT_GUARD] ok')
console.log('[M-068][phase50_tariff_catalog][USER_ADMIN_UI] ok')
console.log('[M-068][phase50_tariff_catalog][PROTECTED_SURFACES] ok')
