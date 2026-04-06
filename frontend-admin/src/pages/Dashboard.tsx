// FILE: frontend-admin/src/pages/Dashboard.tsx
// VERSION: 1.0.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Admin dashboard page showing operational overview (users, subscriptions, revenue, system health)
//   SCOPE: Display aggregated stats, system health metrics, routing topology overview
//   DEPENDS: M-010 (frontend-admin), M-006 (admin API)
//   LINKS: M-010
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   DashboardPage - Main admin dashboard component
//   formatCurrency - Helper: format number with ru-RU locale
//   StatCard - reused component from ../components/StatCard
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY

import { useQuery } from 'react-query'
import {
  Activity,
  CreditCard,
  DollarSign,
  Server,
  ShieldCheck,
  TrendingUp,
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

// START_BLOCK: Dashboard
// Admin dashboard: aggregated stats, system health, routing topology overview
// DEPENDS: M-010 (frontend-admin), M-006 (admin API via adminApi)
//   - adminApi.getStats (aggregated operational stats)
//   - adminApi.getSystemHealth (CPU, RAM, disk metrics)
export default function Dashboard() {
  const { data: stats, isLoading } = useQuery('admin-stats', () => adminApi.getStats())
  const { data: health } = useQuery('system-health', () => adminApi.getSystemHealth())

  const s = stats?.data

  if (isLoading) {
    return (
      <div className="empty-state">
        <Activity className="h-10 w-10 text-cyan-200" />
        <div>
          <p className="text-lg font-semibold">Собираем оперативную сводку</p>
          <p className="mt-1 text-sm muted">Backend уже отвечает, подгружаем агрегированные метрики.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="page-shell">
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,0.9fr)]">
        <div className="glass p-6 md:p-7">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-cyan-200/70">Оперативный срез</p>
              <h1 className="mt-3 text-4xl font-extrabold tracking-tight">Сервис под контролем</h1>
              <p className="mt-3 max-w-2xl text-sm muted">
                Здесь собраны живые показатели по пользователям, подпискам и policy-driven VPN topology.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="panel-soft px-4 py-4">
                <p className="text-xs uppercase tracking-[0.18em] muted">Общая выручка</p>
                <p className="mt-2 text-2xl font-bold">{formatCurrency(s?.revenue?.total)} ₽</p>
              </div>
              <div className="panel-soft px-4 py-4">
                <p className="text-xs uppercase tracking-[0.18em] muted">Новых пользователей</p>
                <p className="mt-2 text-2xl font-bold">{s?.users?.new_this_month || 0}</p>
              </div>
            </div>
          </div>
        </div>

        <div className="panel p-6">
          <div className="mb-5 flex items-center gap-3">
            <div className="rounded-2xl bg-emerald-300/12 p-3 text-emerald-200">
              <ShieldCheck className="h-6 w-6" />
            </div>
            <div>
              <p className="font-semibold">Состояние системы</p>
              <p className="text-sm muted">CPU, память и диск в текущий момент</p>
            </div>
          </div>

          {health?.data ? (
            <div className="space-y-5">
              {[
                { label: 'CPU', value: health.data.cpu_percent },
                { label: 'RAM', value: health.data.memory.percent },
                { label: 'Disk', value: health.data.disk.percent },
              ].map((metric) => (
                <div key={metric.label}>
                  <div className="mb-2 flex items-center justify-between text-sm">
                    <span className="muted">{metric.label}</span>
                    <span className="font-semibold">{metric.value}%</span>
                  </div>
                  <div className="progress-track">
                    <div className="progress-fill" style={{ width: `${metric.value}%` }} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm muted">Метрики системы пока недоступны.</p>
          )}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard icon={<Users className="h-6 w-6" />} label="Всего пользователей" value={s?.users?.total || 0} />
        <StatCard
          icon={<CreditCard className="h-6 w-6" />}
          label="Активных подписок"
          value={s?.subscriptions?.active || 0}
        />
        <StatCard
          icon={<DollarSign className="h-6 w-6" />}
          label="Выручка за месяц"
          value={formatCurrency(s?.revenue?.this_month)}
          suffix="₽"
        />
        <StatCard
          icon={<Server className="h-6 w-6" />}
          label="Активных domain rules"
          value={s?.routing?.domain_rules_active || 0}
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-4">
        <div className="panel p-6">
          <div className="mb-5 flex items-center gap-3">
            <TrendingUp className="h-5 w-5 text-emerald-200" />
            <h3 className="text-lg font-semibold">Рост аудитории</h3>
          </div>
          <p className="text-4xl font-extrabold">{s?.users?.new_this_month || 0}</p>
          <p className="mt-2 text-sm muted">Новых регистраций в текущем месяце.</p>
        </div>

        <div className="panel p-6">
          <div className="mb-5 flex items-center gap-3">
            <CreditCard className="h-5 w-5 text-cyan-200" />
            <h3 className="text-lg font-semibold">Trial-пул</h3>
          </div>
          <p className="text-4xl font-extrabold">{s?.subscriptions?.trial || 0}</p>
          <p className="mt-2 text-sm muted">Активные пробные подписки, требующие конверсии в оплату.</p>
        </div>

        <div className="panel p-6">
          <div className="mb-5 flex items-center gap-3">
            <Activity className="h-5 w-5 text-cyan-200" />
            <h3 className="text-lg font-semibold">VPN клиенты</h3>
          </div>
          <p className="text-4xl font-extrabold">{s?.vpn?.active_clients || 0}</p>
          <p className="mt-2 text-sm muted">Количество активных клиентов с доступом к сети.</p>
        </div>

        <div className="panel p-6">
          <div className="mb-5 flex items-center gap-3">
            <Server className="h-5 w-5 text-amber-200" />
            <h3 className="text-lg font-semibold">Routing topology</h3>
          </div>
          <div className="space-y-4 text-sm">
            <div className="flex items-center justify-between">
              <span className="muted">Онлайн узлов</span>
              <span className="font-bold">{s?.routing?.online_nodes || 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="muted">Активных маршрутов</span>
              <span className="font-bold">{s?.routing?.active_routes || 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="muted">DNS bindings</span>
              <span className="font-bold">{s?.routing?.dns_bindings_active || 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="muted">Legacy VPNServer</span>
              <span className="font-bold">{s?.vpn?.online_servers || 0}</span>
            </div>
          </div>
          <p className="mt-4 text-xs muted">
            {s?.vpn?.topology_note || 'Legacy server metric kept only for migration visibility.'}
          </p>
        </div>
      </section>
    </div>
  )
}
// END_BLOCK: Dashboard
