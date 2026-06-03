// FILE: frontend-admin/src/components/StatCard.tsx
// VERSION: 1.2.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Reusable compact Matrix metric tile with icon, value, label, and optional trend indicator
//   SCOPE: Props interface, StatCard presentational component, Phase-54 KPI marker
//   DEPENDS: M-010 (frontend-admin), M-038 (compact-ui-system), M-071 (matrix-style-system), React
//   LINKS: M-010, M-038, M-071, Phase-54
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   Props - Interface: icon, label, value, suffix?, trend?
//   StatCard - Default export: compact metric tile with optional trend pill
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v3.0.0 - Phase-54 marked KPI tiles for compact admin Matrix smoke coverage.
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.9.0 - Phase-24 compact metric tile with reduced spacing and stable mobile sizing
// END_CHANGE_SUMMARY

import { ReactNode } from 'react'

// START_BLOCK: Props
// Props interface for StatCard component
// icon: Lucide or custom ReactNode rendered in compact badge
// label: Descriptive text shown above the value
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
// Presentational compact metric tile component for dashboard stat display
// DEPENDS: React, compact CSS classes (metric-tile, metric-pill, danger-pill, muted)
export default function StatCard({ icon, label, value, suffix, trend }: Props) {
  return (
    <div className="metric-tile" data-phase54-kpi="compact-admin">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-300/10 text-emerald-200">
          {icon}
        </div>
        {trend ? (
          <span className={trend.positive ? 'metric-pill' : 'danger-pill'}>
            {trend.positive ? '+' : ''}
            {trend.value}%
          </span>
        ) : null}
      </div>

      <div className="metric-label">{label}</div>
      <div className="metric-value">
        {value}
        {suffix ? <span className="ml-1 text-sm text-cyan-100">{suffix}</span> : null}
      </div>
    </div>
  )
}
// END_BLOCK: StatCard
