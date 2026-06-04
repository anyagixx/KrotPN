#!/usr/bin/env node
// FILE: scripts/phase69-referral-bonus-smoke.mjs
// VERSION: 1.0.0
// ROLE: TEST
// MAP_MODE: LOCALS
// START_MODULE_CONTRACT
//   PURPOSE: Static Phase-69 smoke for referral-bonus activation contracts and masked invite identity UI
//   SCOPE: Source-level checks for referral bonus grant path, subscription access labels, user API typing, referral UI copy, and protected deploy surface
//   DEPENDS: M-005, M-004, M-063, M-009, M-036
//   LINKS: Phase-69, V-M-005, V-M-004, V-M-063, V-M-009, V-M-036
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   read - Read one UTF-8 project file
//   assertContains/assertNotContains - Minimal deterministic assertions
//   gitChangedProtectedFiles - Return protected diff paths for deploy/runtime guard
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.0.0 - Added Phase-69 referral bonus and masked identity static smoke.
// END_CHANGE_SUMMARY

import { execSync } from 'node:child_process'
import { readFileSync } from 'node:fs'

function read(path) {
  return readFileSync(path, 'utf8')
}

function assertContains(source, needle, label) {
  if (!source.includes(needle)) {
    throw new Error(`[Phase69][ASSERT_CONTAINS_FAILED] ${label}: missing ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`[Phase69][ASSERT_NOT_CONTAINS_FAILED] ${label}: forbidden ${needle}`)
  }
}

function gitChangedProtectedFiles() {
  const output = execSync(
    'git diff --name-only HEAD -- install.sh docker-compose.yml nginx deploy deploy/mtproto-de-compose.yml .env.example mtproto-runtime official-mtproxy telegram-bot frontend-admin',
    { encoding: 'utf8' },
  )
  return output.trim().split('\n').filter(Boolean)
}

// START_BLOCK_PHASE69_SOURCE_CONTRACTS
const billingService = read('backend/app/billing/service.py')
const billingRouter = read('backend/app/billing/router.py')
const billingSchemas = read('backend/app/billing/schemas.py')
const referralService = read('backend/app/referrals/service.py')
const referralRouter = read('backend/app/referrals/router.py')
const api = read('frontend/src/lib/api.ts')
const referralsPage = read('frontend/src/pages/Referrals.tsx')
const subscriptionPanel = read('frontend/src/components/SubscriptionPanel.tsx')

assertContains(billingService, 'REFERRAL_BONUS_ACCESS_LABEL = "referral-bonus"', 'billing service')
assertContains(billingService, 'async def grant_referral_bonus_days', 'billing service')
assertContains(billingService, 'mode=active_extension', 'billing service')
assertContains(billingService, 'mode=pending_create', 'billing service')
assertContains(billingService, 'consume_pending_referral_bonus_days', 'billing service')
assertContains(billingService, 'Subscription.pending_activation == True', 'billing activation')
assertContains(referralService, 'grant_referral_bonus_days', 'referral service')
assertContains(referralService, '[ReferralService][process_first_payment][REFERRAL_BONUS_APPLIED]', 'referral service log marker')
assertContains(billingRouter, 'access_label=subscription.access_label', 'billing router')
assertContains(billingSchemas, 'pending_duration_days: int | None = None', 'billing schemas')
assertContains(referralRouter, 'mask_referred_identity', 'referral router')
assertContains(referralRouter, 'referred_identity', 'referral router')
assertContains(referralRouter, 'referred_email_masked', 'referral router')
assertContains(api, 'referred_identity: string', 'frontend api type')
assertContains(api, 'access_label: string | null', 'frontend api type')
assertContains(api, 'pending_duration_days: number | null', 'frontend api type')
assertContains(referralsPage, 'data-phase69-masked-referral-identity="true"', 'referrals page')
assertContains(referralsPage, 'Реферал {item.referred_identity', 'referrals page')
assertNotContains(referralsPage, 'Реферал #{item.id}', 'referrals page')
assertContains(subscriptionPanel, "subscription.access_label === 'referral-bonus'", 'subscription panel')
assertContains(subscriptionPanel, "subscription.access_label === 'trial-referral-bonus'", 'subscription panel')
// END_BLOCK_PHASE69_SOURCE_CONTRACTS

// START_BLOCK_PHASE69_PROTECTED_GUARD
const protectedDiff = gitChangedProtectedFiles()
if (protectedDiff.length > 0) {
  throw new Error(`[Phase69][PROTECTED_SURFACE_DRIFT] ${protectedDiff.join(', ')}`)
}
// END_BLOCK_PHASE69_PROTECTED_GUARD

console.log('[Phase69][ReferralBonus][PENDING_AND_EXTENSION_CONTRACTS] ok')
console.log('[Phase69][ReferralBonus][MASKED_IDENTITY_UI] ok')
console.log('[Phase69][ProtectedSurfaceGuard][NO_DEPLOY_RUNTIME_DRIFT] ok')
