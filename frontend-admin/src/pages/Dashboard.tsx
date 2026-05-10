// FILE: frontend-admin/src/pages/Dashboard.tsx
// VERSION: 1.1.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact admin dashboard page showing operational overview, revenue, subscriptions, users, and system health
//   SCOPE: Display aggregated stats, system health, urgent admin paths, and compact mobile-first metric rows
//   DEPENDS: M-010 (frontend-admin), M-006 (admin API), M-037 (mobile-admin-console), M-038 (compact-ui-system)
//   LINKS: M-010, M-037, M-038
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   DashboardPage - Main compact admin dashboard component
//   formatCurrency - Helper: format number with ru-RU locale
//   normalizePercent - Helper: clamp numeric health percentages for compact meters
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.9.0 - Phase-24 compact mobile operator overview without hero/table-first layout
// END_CHANGE_SUMMARY

import { Link } from 'react-router-dom'
import { useQuery } from 'react-query'
import {
  Activity,
  AlertTriangle,
  CreditCard,
  DollarSign,
  Server,
  ShieldAlert,
  ShieldCheck,
  Users,
} from 'lucide-react'
import { adminApi } from '../lib/api'
import StatCard from '../components/StatCard'

// START_BLOCK: formatCurrency
// Formats number with ru-RU locale for currency display
// DEPENDS: none (pure function)
function formatCurrency(value?: number) {
  return Number(value || 0).toLocaleString('ru-RU')
}
// END_BLOCK: formatCurrency

// START_BLOCK: normalizePercent
// Normalizes optional numeric health metric values to a safe 0-100 range for compact progress bars
// DEPENDS: none (pure function)
function normalizePercent(value: unknown) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return null
  return Math.max(0, Math.min(100, numeric))
}
// END_BLOCK: normalizePercent

// START_BLOCK: Dashboard
// Compact admin dashboard: aggregated stats, system health, and urgent operator links
// DEPENDS: M-010 (frontend-admin), M-006 (admin API via adminApi)
//   - adminApi.getStats (aggregated operational stats)
//   - adminApi.getSystemHealth (CPU, RAM, disk and service health metrics when available)
export default function Dashboard() {
  const { data: stats, isLoading } = useQuery('admin-stats', () => adminApi.getStats())
  const { data: health } = useQuery('system-health', () => adminApi.getSystemHealth())

  const s = stats?.data
  const h = health?.data || {}
  const healthMetrics = [
    { label: 'CPU', value: normalizePercent(h.cpu_percent) },
    { label: 'RAM', value: normalizePercent(h.memory?.percent) },
    { label: 'Disk', value: normalizePercent(h.disk?.percent) },
  ].filter((metric) => metric.value !== null)
  const serviceHealth = [
    { label: 'Backend', value: h.backend || 'ok' },
    { label: 'DB', value: h.database || 'ok' },
    { label: 'Redis', value: h.redis || 'ok' },
    { label: 'VPN', value: h.vpn_tunnel || h.vpn || 'ok' },
  ]

  if (isLoading) {
    return (
      <div className="empty-state">
        <Activity className="h-9 w-9 text-cyan-200" />
        <div>
          <p className="text-base font-semibold">Собираем оперативную сводку</p>
          <p className="mt-1 text-sm muted">Подгружаем агрегированные метрики admin API.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="page-shell">
      <section className="metric-grid">
        <StatCard icon={<Users className="h-5 w-5" />} label="Пользователи" value={s?.users?.total || 0} />
        <StatCard icon={<CreditCard className="h-5 w-5" />} label="Подписки" value={s?.subscriptions?.active || 0} />
        <StatCard icon={<DollarSign className="h-5 w-5" />} label="Месяц" value={formatCurrency(s?.revenue?.this_month)} suffix="₽" />
        <StatCard icon={<ShieldCheck className="h-5 w-5" />} label="Новые" value={s?.users?.new_this_month || 0} />
      </section>

      <section className="grid gap-3 xl:grid-cols-[minmax(0,1.15fr)_minmax(280px,0.85fr)]">
        <div className="panel p-4">
          <div className="status-row">
            <div>
              <p className="text-sm font-semibold text-white">Состояние сервиса</p>
              <p className="text-xs muted">Короткий статус для телефона и аварийной проверки.</p>
            </div>
            <span className="metric-pill">
              <ShieldCheck className="h-3.5 w-3.5" />
              Console online
            </span>
          </div>

          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {serviceHealth.map((item) => (
              <div key={item.label} className="surface px-3 py-2">
                <span className="metric-label">{item.label}</span>
                <span className="mt-1 block truncate text-sm font-semibold text-white">{String(item.value)}</span>
              </div>
            ))}
          </div>

          {healthMetrics.length ? (
            <div className="mt-4 space-y-3">
              {healthMetrics.map((metric) => (
                <div key={metric.label}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="muted">{metric.label}</span>
                    <span className="font-semibold">{metric.value}%</span>
                  </div>
                  <div className="progress-track">
                    <div className="progress-fill" style={{ width: `${metric.value}%` }} />
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>

        <div className="panel p-4">
          <div className="flex items-start gap-3">
            <div className="brand-mark shrink-0">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-white">Быстрые действия</p>
              <p className="text-xs muted">Критические разделы доступны без desktop sidebar.</p>
            </div>
          </div>

          <div className="mt-4 grid gap-2">
            <Link to="/devices" className="btn-danger justify-start">
              <ShieldAlert className="h-4 w-4" />
              Устройства и санкции
            </Link>
            <Link to="/users" className="btn-secondary justify-start">
              <Users className="h-4 w-4" />
              Поиск пользователя
            </Link>
            <Link to="/analytics" className="btn-secondary justify-start">
              <DollarSign className="h-4 w-4" />
              Деньги и подписки
            </Link>
            <Link to="/servers" className="btn-secondary justify-start">
              <Server className="h-4 w-4" />
              Ноды и маршруты
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}
// END_BLOCK: Dashboard
