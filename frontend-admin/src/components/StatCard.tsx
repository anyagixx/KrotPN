// FILE: frontend-admin/src/components/StatCard.tsx
// VERSION: 1.0.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Reusable metric display card with icon, value, label, and optional trend indicator
//   SCOPE: Props interface, StatCard presentational component
//   DEPENDS: M-010 (frontend-admin), React
//   LINKS: M-010
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   Props - Interface: icon, label, value, suffix?, trend?
//   StatCard - Default export: metric card with trend pill (green/red)
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY

import { ReactNode } from 'react'

// START_BLOCK: Props
// Props interface for StatCard component
// icon: Lucide or custom ReactNode rendered in top-left badge
// label: Descriptive text shown below the value
// value: Primary metric number or string
// suffix: Optional unit/label appended to value (e.g. "%", "руб")
// trend: Optional { value, positive } for trend pill display
interface Props {
  icon: ReactNode
  label: string
  value: string | number
  suffix?: string
  trend?: { value: number; positive: boolean }
}
// END_BLOCK: Props

// START_BLOCK: StatCard
// Presentational metric card component for dashboard stat display
// Renders icon badge, primary value with optional suffix, label, and trend pill
// DEPENDS: React, Tailwind utility classes (panel, metric-pill, danger-pill, muted)
export default function StatCard({ icon, label, value, suffix, trend }: Props) {
  return (
    <div className="panel p-5">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div className="rounded-2xl bg-emerald-300/10 p-3 text-emerald-200 ring-1 ring-emerald-200/10">
          {icon}
        </div>
        {trend ? (
          <span className={trend.positive ? 'metric-pill' : 'danger-pill'}>
            {trend.positive ? '+' : ''}
            {trend.value}%
          </span>
        ) : null}
      </div>

      <div className="text-3xl font-extrabold tracking-tight text-white">
        {value}
        {suffix ? <span className="ml-1 text-lg text-cyan-100">{suffix}</span> : null}
      </div>
      <div className="mt-2 text-sm muted">{label}</div>
    </div>
  )
}
// END_BLOCK: StatCard
