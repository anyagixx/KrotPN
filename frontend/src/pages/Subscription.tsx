// FILE: frontend/src/pages/Subscription.tsx
// VERSION: 1.5.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compatibility route for the Phase-68 dashboard-owned subscription, tariff, checkout, and calendar panel
//   SCOPE: Route wrapper for the shared SubscriptionPanel; preserves /dashboard/subscription deep links without duplicating UI ownership
//   DEPENDS: M-009 (frontend-user), M-004 (billing API), M-036 (mobile-user-cabinet), M-038 (compact-ui-system), M-063 (trial countdown), M-068 (paid tariff catalog), M-071 (matrix-style-system), M-074 (responsive-device-adaptation), M-075 (premium-user-cabinet)
//   LINKS: M-009 (frontend-user), M-036 (mobile-user-cabinet), M-038, M-063, M-068, M-071, M-074, M-075, Phase-62, Phase-68
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   SubscriptionPage - Route wrapper rendering the shared Phase-68 SubscriptionPanel
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v2.15.0 - Moved subscription UI ownership into shared Phase-68 SubscriptionPanel and kept this route as compatibility wrapper.
//   LAST_CHANGE: v2.14.0 - Added Phase-62 subscription deletion audit markers and folded secondary tariff/features copy.
//   LAST_CHANGE: v2.13.0 - Added Phase-57 compact subscription command surface, countdown/calendar markers, and renewal CTA guard.
//   LAST_CHANGE: v2.12.0 - Applied Phase-53 compact Matrix tariff/status/calendar surfaces without changing checkout shape.
//   LAST_CHANGE: v2.11.0 - Added Phase-50 three paid tariffs with device-limit usage and downgrade guard UX.
//   LAST_CHANGE: v2.10.0 - Added Phase-45 pending trial countdown and compact active-date calendar.
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.9.0 - Reworked billing surface into compact mobile-first plan rows for Phase-23
// END_CHANGE_SUMMARY
//
// START_BLOCK_SUBSCRIPTION_PAGE
import SubscriptionPanel from '../components/SubscriptionPanel'

export default function Subscription() {
  return (
    <div
      className="content-section matrix-page animate-in min-w-0"
      data-phase53-route="subscription"
      data-phase57-route="subscription"
      data-phase62-user-surface="subscription-compact"
      data-phase62-keep="[CompactDeletionAudit][phase62][PRIMARY_WORKFLOWS_PRESERVED]"
      data-phase68-subscription-route="compatibility-wrapper"
    >
      <SubscriptionPanel />
    </div>
  )
}
// END_BLOCK_SUBSCRIPTION_PAGE
