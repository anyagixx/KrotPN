// FILE: frontend-admin/src/pages/Analytics.tsx
// VERSION: 1.0.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Admin analytics page with charts for revenue, registrations, subscriptions, referrals
//   SCOPE: Display period-selectable charts, billing stats, referral funnel, trial-to-paid conversion KPI
//   DEPENDS: M-010 (frontend-admin), M-006 (admin API)
//   LINKS: M-010
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   AnalyticsPage - Main admin analytics page component
//   chartTheme - Recharts theme configuration object
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY

import { useState } from 'react'
import { useQuery } from 'react-query'
import { Bar, BarChart, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { adminApi } from '../lib/api'
import type { AnalyticsData, BillingStats, ReferralStats } from '../types'

// START_BLOCK: chartTheme
// Recharts theme configuration for consistent chart styling
// DEPENDS: none (static config object)
const chartTheme = {
  tooltip: {
    background: '#10242d',
    border: '1px solid rgba(154, 199, 214, 0.12)',
    borderRadius: 16,
    color: '#eff8fb',
  },
  axis: '#82a0aa',
}
// END_BLOCK: chartTheme

// START_BLOCK: Analytics
// Admin analytics page: revenue/registration charts, billing stats, referral funnel, conversion KPI
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
          <p className="page-subtitle">Срез по выручке, регистрациям, подпискам и реферальной воронке.</p>
        </div>

        <select value={period} onChange={(e) => setPeriod(Number(e.target.value))} className="input w-full sm:w-44">
          <option value={7}>7 дней</option>
          <option value={30}>30 дней</option>
          <option value={90}>90 дней</option>
          <option value={365}>365 дней</option>
        </select>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="panel p-6">
          <h3 className="text-lg font-semibold">Выручка по дням</h3>
          <p className="mt-1 text-sm muted">Факт успешных платежей за выбранный период.</p>
          <div className="mt-6 h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={revenue}>
                <XAxis dataKey="date" tick={{ fill: chartTheme.axis, fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: chartTheme.axis, fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={chartTheme.tooltip} />
                <Bar dataKey="revenue" fill="#53d2b2" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel p-6">
          <h3 className="text-lg font-semibold">Регистрации</h3>
          <p className="mt-1 text-sm muted">Новые пользователи, зарегистрированные за период.</p>
          <div className="mt-6 h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={users}>
                <XAxis dataKey="date" tick={{ fill: chartTheme.axis, fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: chartTheme.axis, fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={chartTheme.tooltip} />
                <Line type="monotone" dataKey="count" stroke="#6fc6ff" strokeWidth={3} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="panel p-6">
          <h3 className="text-lg font-semibold">Подписки</h3>
          <div className="mt-5 space-y-4">
            <div className="flex items-center justify-between">
              <span className="muted">Активные</span>
              <span className="font-bold">{billingStats?.data?.active_subscriptions || 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="muted">Trial</span>
              <span className="font-bold">{billingStats?.data?.trial_subscriptions || 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="muted">Истекли за месяц</span>
              <span className="font-bold">{billingStats?.data?.expired_this_month || 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="muted">Выручка за месяц</span>
              <span className="font-bold text-emerald-200">
                {Number(billingStats?.data?.revenue_this_month || 0).toLocaleString('ru-RU')} ₽
              </span>
            </div>
          </div>
        </div>

        <div className="panel p-6">
          <h3 className="text-lg font-semibold">Реферальная воронка</h3>
          <div className="mt-5 space-y-4">
            <div className="flex items-center justify-between">
              <span className="muted">Всего кодов</span>
              <span className="font-bold">{referralStats?.data?.total_codes || 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="muted">Рефералов</span>
              <span className="font-bold">{referralStats?.data?.total_referrals || 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="muted">Оплативших</span>
              <span className="font-bold">{referralStats?.data?.paid_referrals || 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="muted">Конверсия</span>
              <span className="font-bold">{referralStats?.data?.conversion_rate || 0}%</span>
            </div>
          </div>
        </div>

        <div className="glass p-6">
          <p className="text-xs uppercase tracking-[0.18em] text-cyan-200/75">Main KPI</p>
          <h3 className="mt-3 text-xl font-semibold">Trial → Paid</h3>
          <div className="mt-8 flex items-center justify-center">
            <div className="text-center">
              <p className="text-6xl font-extrabold text-emerald-200">{conversion}%</p>
              <p className="mt-3 text-sm muted">Конверсия из пробных подписок в платные.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
// END_BLOCK: Analytics
