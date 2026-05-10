// FILE: frontend-admin/src/pages/Analytics.tsx
// VERSION: 1.1.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact admin analytics page with payment, subscription, referral, conversion, and chart detail summaries
//   SCOPE: Period-selectable KPI summaries, billing stats, referral funnel, trial-to-paid conversion, secondary charts
//   DEPENDS: M-010 (frontend-admin), M-006 (admin API), M-037 (mobile-admin-console), M-038 (compact-ui-system)
//   LINKS: M-010, M-037, M-038
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   AnalyticsPage - Main compact admin analytics page component
//   chartTheme - Recharts theme configuration object
//   formatCurrency - Helper: format number with ru-RU locale
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.9.0 - Phase-24 compact payment/subscription KPI-first analytics layout
// END_CHANGE_SUMMARY

import { useState } from 'react'
import { useQuery } from 'react-query'
import { Bar, BarChart, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { CreditCard, DollarSign, Percent, Users } from 'lucide-react'
import { adminApi } from '../lib/api'
import StatCard from '../components/StatCard'
import type { AnalyticsData, BillingStats, ReferralStats } from '../types'

// START_BLOCK: chartTheme
// Recharts theme configuration for consistent compact chart styling
// DEPENDS: none (static config object)
const chartTheme = {
  tooltip: {
    background: '#111f27',
    border: '1px solid rgba(154, 188, 198, 0.16)',
    borderRadius: 8,
    color: '#f3f8fa',
  },
  axis: '#8fa3ac',
}
// END_BLOCK: chartTheme

// START_BLOCK: formatCurrency
// Formats number with ru-RU locale for currency display
// DEPENDS: none (pure function)
function formatCurrency(value?: number) {
  return Number(value || 0).toLocaleString('ru-RU')
}
// END_BLOCK: formatCurrency

// START_BLOCK: Analytics
// Compact admin analytics page: payment/subscription KPIs first, charts second
// DEPENDS: M-010 (frontend-admin), M-006 (admin API via adminApi)
//   - adminApi.getRevenueAnalytics, adminApi.getUsersAnalytics
//   - adminApi.getBillingStats, adminApi.getReferralStats
export default function Analytics() {
  const [period, setPeriod] = useState(30)

  const { data: revenueData } = useQuery<{ data: AnalyticsData }>(['revenue-analytics', period], () => adminApi.getRevenueAnalytics(period))
  const { data: usersData } = useQuery<{ data: AnalyticsData }>(['users-analytics', period], () => adminApi.getUsersAnalytics(period))
  const { data: billingStats } = useQuery<{ data: BillingStats }>('billing-stats', () => adminApi.getBillingStats())
  const { data: referralStats } = useQuery<{ data: ReferralStats }>('referral-stats', () => adminApi.getReferralStats())

  const revenue = revenueData?.data?.daily || []
  const users = usersData?.data?.daily || []

  const conversion =
    (billingStats?.data?.trial_subscriptions ?? 0) > 0
      ? Math.round(((billingStats?.data?.active_subscriptions ?? 0) / (billingStats?.data?.trial_subscriptions ?? 1)) * 100)
      : 0

  return (
    <div className="page-shell">
      <div className="page-header">
        <div>
          <h1 className="page-title">Аналитика</h1>
          <p className="page-subtitle">Сначала деньги и подписки, затем графики как вторичный detail.</p>
        </div>

        <select value={period} onChange={(e) => setPeriod(Number(e.target.value))} className="input w-full sm:w-44">
          <option value={7}>7 дней</option>
          <option value={30}>30 дней</option>
          <option value={90}>90 дней</option>
          <option value={365}>365 дней</option>
        </select>
      </div>

      <section className="metric-grid">
        <StatCard icon={<DollarSign className="h-5 w-5" />} label="Выручка" value={formatCurrency(billingStats?.data?.revenue_this_month)} suffix="₽" />
        <StatCard icon={<CreditCard className="h-5 w-5" />} label="Активные" value={billingStats?.data?.active_subscriptions || 0} />
        <StatCard icon={<Users className="h-5 w-5" />} label="Trial" value={billingStats?.data?.trial_subscriptions || 0} />
        <StatCard icon={<Percent className="h-5 w-5" />} label="Trial→Paid" value={conversion} suffix="%" />
      </section>

      <section className="grid gap-3 lg:grid-cols-2">
        <div className="panel p-4">
          <h2 className="text-sm font-semibold text-white">Подписки</h2>
          <div className="mt-3 grid gap-2">
            <div className="status-row">
              <span className="muted">Активные</span>
              <span className="font-bold">{billingStats?.data?.active_subscriptions || 0}</span>
            </div>
            <div className="status-row">
              <span className="muted">Trial</span>
              <span className="font-bold">{billingStats?.data?.trial_subscriptions || 0}</span>
            </div>
            <div className="status-row">
              <span className="muted">Истекли за месяц</span>
              <span className="font-bold">{billingStats?.data?.expired_this_month || 0}</span>
            </div>
            <div className="status-row">
              <span className="muted">Выручка за месяц</span>
              <span className="font-bold text-emerald-200">{formatCurrency(billingStats?.data?.revenue_this_month)} ₽</span>
            </div>
          </div>
        </div>

        <div className="panel p-4">
          <h2 className="text-sm font-semibold text-white">Реферальная воронка</h2>
          <div className="mt-3 grid gap-2">
            <div className="status-row">
              <span className="muted">Кодов</span>
              <span className="font-bold">{referralStats?.data?.total_codes || 0}</span>
            </div>
            <div className="status-row">
              <span className="muted">Рефералов</span>
              <span className="font-bold">{referralStats?.data?.total_referrals || 0}</span>
            </div>
            <div className="status-row">
              <span className="muted">Оплативших</span>
              <span className="font-bold">{referralStats?.data?.paid_referrals || 0}</span>
            </div>
            <div className="status-row">
              <span className="muted">Конверсия</span>
              <span className="font-bold">{referralStats?.data?.conversion_rate || 0}%</span>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-3 lg:grid-cols-2">
        <div className="panel p-4">
          <h2 className="text-sm font-semibold text-white">Выручка по дням</h2>
          <p className="mt-1 text-xs muted">Факт успешных платежей за выбранный период.</p>
          <div className="mt-3 h-[220px] min-w-0">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={revenue}>
                <XAxis dataKey="date" tick={{ fill: chartTheme.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: chartTheme.axis, fontSize: 11 }} axisLine={false} tickLine={false} width={36} />
                <Tooltip contentStyle={chartTheme.tooltip} />
                <Bar dataKey="revenue" fill="#5cd5b6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel p-4">
          <h2 className="text-sm font-semibold text-white">Регистрации</h2>
          <p className="mt-1 text-xs muted">Новые пользователи, зарегистрированные за период.</p>
          <div className="mt-3 h-[220px] min-w-0">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={users}>
                <XAxis dataKey="date" tick={{ fill: chartTheme.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: chartTheme.axis, fontSize: 11 }} axisLine={false} tickLine={false} width={36} />
                <Tooltip contentStyle={chartTheme.tooltip} />
                <Line type="monotone" dataKey="count" stroke="#75c7ff" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>
    </div>
  )
}
// END_BLOCK: Analytics
