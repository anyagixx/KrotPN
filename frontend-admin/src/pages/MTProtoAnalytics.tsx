// FILE: frontend-admin/src/pages/MTProtoAnalytics.tsx
// VERSION: 2.8.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact Matrix admin MTProto analytics console with usage graphs, alert review, user investigation, runtime metrics, promotion tag controls, Phase-58 readonly cockpit markers, Phase-59 feedback, and Phase-62 deletion-audit compaction
//   SCOPE: Overview, Users, Abuse, Settings tabs, top users, user detail drawer with IP history, folded alert archive, auto-refresh, masked promotion tag update, Phase-54 visibility guards, Phase-58 analytics/read-only proof, and status/feedback transitions
//   DEPENDS: M-010 (frontend-admin), M-058 (mtproto-admin-analytics-ui), M-057 (admin analytics API), M-059 (promotion tag), M-060 (alerts), M-061 (IP observability), M-070 (matrix-visual-runtime), M-071 (matrix-style-system), M-074 (responsive-device-adaptation), M-076 (premium-admin-cockpit), M-077 (matrix-motion-interactions)
//   LINKS: M-058, M-057, M-059, M-060, M-061, M-070, M-071, M-074, M-076, M-077, V-M-058, Phase-54, Phase-58, Phase-59, Phase-62
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   MTProtoAnalyticsPanel - Compact analytics panel embedded in MTProto admin page with Phase-62 folded secondary surfaces
//   formatBytes - Helper: render byte counters
//   formatDuration - Helper: render millisecond durations
//   formatDate - Helper: render ISO timestamps
//   MetricAreaChart - Compact responsive area graph for Phase-43 metrics
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v2.8.0 - Added Phase-62 admin deletion audit markers and folded alert archive/storage details without hiding abuse actions.
//   LAST_CHANGE: v2.7.0 - Added Phase-59 analytics feedback, status transition, and chart motion markers.
//   LAST_CHANGE: v2.6.0 - Phase-58 added readonly analytics, chart, bounded user/IP, and alert review cockpit markers.
//   LAST_CHANGE: v2.5.0 - Phase-54 added compact Matrix chart frames, bounded analytics lists, and explicit redaction/Signals-hidden markers.
//   LAST_CHANGE: v2.4.0 - Made IP history compact, scrollable, and removed visible CIDR prefix rows.
//   LAST_CHANGE: v2.3.0 - Removed visible technical Signals panel/count and added Russian hover help for alert actions.
//   LAST_CHANGE: v2.2.0 - Split Abuse into open inbox and archive, and standardized icon input padding.
//   LAST_CHANGE: v2.1.0 - Added paginated user investigation, clearer IP-source states, harder-abuse UI copy, and richer compact area graphs.
//   LAST_CHANGE: v2.0.0 - Rebuilt for Phase-43 compact tabs, alert inbox, IP investigation, graphs, resource metrics, and auto-refresh
//   LAST_CHANGE: v1.0.0 - Added Phase-42 MTProto analytics and promotion tag panel
// END_CHANGE_SUMMARY

import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Cpu,
  Database,
  Eye,
  HardDrive,
  MemoryStick,
  RadioTower,
  Save,
  Search,
  ShieldAlert,
  Tag,
  Users,
  XCircle,
} from 'lucide-react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { adminApi } from '../lib/api'
import type {
  AdminMTProtoAlert,
  AdminMTProtoIPObservation,
  AdminMTProtoTimeseriesBucket,
  AdminMTProtoTopUser,
  AdminMTProtoUserSearchItem,
} from '../types'

type MetricKey = 'traffic' | 'duration' | 'connections' | 'errors'
type TabKey = 'overview' | 'users' | 'abuse' | 'settings'

// START_BLOCK: formatters
function formatBytes(value?: number | null) {
  const bytes = Math.max(value || 0, 0)
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let size = bytes / 1024
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }
  return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[unitIndex]}`
}

function formatDuration(value?: number | null) {
  const seconds = Math.floor((value || 0) / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m`
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`
}

function formatDate(value?: string | null) {
  if (!value) return 'Нет данных'
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatPercent(value?: number | null) {
  if (value === null || value === undefined) return 'n/a'
  return `${Math.round(value)}%`
}

function metricValue(row: AdminMTProtoTimeseriesBucket, metric: MetricKey) {
  if (metric === 'duration') return Math.round(row.duration_ms / 1000)
  if (metric === 'connections') return row.connection_count
  if (metric === 'errors') return row.error_count
  return row.traffic_bytes
}
// END_BLOCK: formatters

// START_BLOCK: MetricAreaChart
function MetricAreaChart({ data, metric }: { data: AdminMTProtoTimeseriesBucket[]; metric: MetricKey }) {
  const chartData = data.map((row) => ({
    label: formatDate(row.bucket_start),
    value: metricValue(row, metric),
    traffic: row.traffic_bytes,
    connects: row.connection_count,
    active: row.active_connections,
    errors: row.error_count,
  }))
  const total = chartData.reduce((sum, row) => sum + row.value, 0)
  const peak = chartData.reduce((max, row) => Math.max(max, row.value), 0)
  const latest = chartData[chartData.length - 1]?.value || 0
  return (
    <div
      className="grid gap-2"
      data-log-marker="[M-058][admin_mtproto_analytics_ui][AUTO_REFRESH]"
      data-phase54-auto-refresh="[M-058][phase54_mtproto_analytics][AUTO_REFRESH_STABLE]"
    >
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="rounded-lg border border-white/10 bg-white/5 px-3 py-2">
          <span className="metric-label">Total</span>
          <strong className="block text-white">{metric === 'traffic' ? formatBytes(total) : total}</strong>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/5 px-3 py-2">
          <span className="metric-label">Peak</span>
          <strong className="block text-white">{metric === 'traffic' ? formatBytes(peak) : peak}</strong>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/5 px-3 py-2">
          <span className="metric-label">Last</span>
          <strong className="block text-white">{metric === 'traffic' ? formatBytes(latest) : latest}</strong>
        </div>
      </div>
      <div className="chart-frame h-64" data-log-marker="[M-058][phase54_mtproto_analytics][CHARTS_TABLES_READABLE]" data-phase58-chart="premium-operator-graph">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 12, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={`mtproto-${metric}-fill`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.42} />
              <stop offset="95%" stopColor="#22d3ee" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="rgba(148,163,184,.16)" vertical={false} />
          <XAxis dataKey="label" tick={{ fill: '#9ca3af', fontSize: 11 }} minTickGap={24} tickLine={false} axisLine={false} />
          <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} width={54} tickLine={false} axisLine={false} />
          <Tooltip
            formatter={(value: number) => [metric === 'traffic' ? formatBytes(value) : value, metric]}
            contentStyle={{ background: '#0f172a', border: '1px solid rgba(255,255,255,.14)', borderRadius: 8 }}
            labelStyle={{ color: '#e5e7eb' }}
          />
          <Area type="monotone" dataKey="value" stroke="#22d3ee" strokeWidth={2.5} fill={`url(#mtproto-${metric}-fill)`} dot={false} activeDot={{ r: 4 }} />
        </AreaChart>
      </ResponsiveContainer>
      </div>
    </div>
  )
}
// END_BLOCK: MetricAreaChart

// START_BLOCK: MTProtoAnalyticsPanel
export default function MTProtoAnalyticsPanel() {
  const [days, setDays] = useState(30)
  const [metric, setMetric] = useState<MetricKey>('traffic')
  const [topLimit, setTopLimit] = useState(25)
  const [activeTab, setActiveTab] = useState<TabKey>('overview')
  const [search, setSearch] = useState('')
  const [userPageSize, setUserPageSize] = useState(50)
  const [userPage, setUserPage] = useState(0)
  const [selectedAssignmentId, setSelectedAssignmentId] = useState<number | null>(null)
  const [selectedAlertId, setSelectedAlertId] = useState<number | null>(null)
  const [tagValue, setTagValue] = useState('')
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
  const queryClient = useQueryClient()
  const userOffset = userPage * userPageSize

  const summaryQuery = useQuery(['admin-mtproto-analytics-summary', days], () => adminApi.getMTProtoAnalyticsSummary(days), { refetchInterval: 15000 })
  const topUsersQuery = useQuery(['admin-mtproto-top-users', metric, days, topLimit], () => adminApi.getMTProtoTopUsers(metric, days, topLimit), { refetchInterval: 30000 })
  const timeseriesQuery = useQuery(['admin-mtproto-timeseries', metric, days], () => adminApi.getMTProtoTimeseries({ bucket: days <= 1 ? 'hour' : 'day', days }), { refetchInterval: 30000 })
  const alertsQuery = useQuery(['admin-mtproto-alerts', 'open'], () => adminApi.getMTProtoAlerts('open', 50), { refetchInterval: 10000 })
  const acknowledgedAlertsQuery = useQuery(['admin-mtproto-alerts', 'acknowledged'], () => adminApi.getMTProtoAlerts('acknowledged', 50), { refetchInterval: 30000 })
  const resolvedAlertsQuery = useQuery(['admin-mtproto-alerts', 'resolved'], () => adminApi.getMTProtoAlerts('resolved', 50), { refetchInterval: 30000 })
  const usersQuery = useQuery(
    ['admin-mtproto-user-search', search, userOffset, userPageSize],
    () => adminApi.searchMTProtoUsers(search, userPageSize, userOffset),
    { refetchInterval: 20000, keepPreviousData: true }
  )
  const selectedUsageQuery = useQuery(
    ['admin-mtproto-user-usage', selectedAssignmentId],
    () => adminApi.getMTProtoUserUsage(selectedAssignmentId || 0, 90),
    { enabled: Boolean(selectedAssignmentId), refetchInterval: 15000 }
  )
  const resourcesQuery = useQuery('admin-mtproto-resources', () => adminApi.getMTProtoResourceMetrics(), { refetchInterval: 10000 })
  const storageQuery = useQuery('admin-mtproto-storage-budget', () => adminApi.getMTProtoStorageBudget(), { refetchInterval: 60000 })
  const promotionTagQuery = useQuery('admin-mtproto-promotion-tag', () => adminApi.getMTProtoPromotionTag(), { refetchInterval: 60000 })

  useEffect(() => {
    setUserPage(0)
  }, [search, userPageSize])

  const updateTagMutation = useMutation((tag: string) => adminApi.updateMTProtoPromotionTag(tag), {
    onSuccess: () => {
      void queryClient.invalidateQueries('admin-mtproto-promotion-tag')
      setTagValue('')
      setFeedback({ tone: 'success', text: 'Promotion tag обновлен' })
    },
    onError: (error: unknown) => {
      setFeedback({
        tone: 'error',
        text: (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Promotion tag не обновлен',
      })
    },
  })

  const alertMutation = useMutation((params: { id: number; action: 'ack' | 'resolve' | 'disable' }) => {
    if (params.action === 'ack') return adminApi.acknowledgeMTProtoAlert(params.id)
    if (params.action === 'disable') return adminApi.disableMTProtoAlertProxy(params.id)
    return adminApi.resolveMTProtoAlert(params.id)
  }, {
    onSuccess: () => {
      void queryClient.invalidateQueries('admin-mtproto-alerts')
      void queryClient.invalidateQueries('admin-mtproto-analytics-summary')
      setFeedback({ tone: 'success', text: 'Действие выполнено' })
    },
    onError: () => setFeedback({ tone: 'error', text: 'Действие не выполнено' }),
  })

  const blockIpMutation = useMutation((params: { alertId: number; observationId: number }) => adminApi.blockMTProtoAlertIP(params.alertId, params.observationId, 24), {
    onSuccess: () => {
      void queryClient.invalidateQueries('admin-mtproto-alerts')
      setFeedback({ tone: 'success', text: 'IP block записан' })
    },
    onError: () => setFeedback({ tone: 'error', text: 'IP block не записан' }),
  })

  const summary = summaryQuery.data?.data
  const topUsers = topUsersQuery.data?.data?.items || []
  const timeseries = timeseriesQuery.data?.data?.items || []
  const alerts = alertsQuery.data?.data?.items || []
  const archivedAlerts = [
    ...(acknowledgedAlertsQuery.data?.data?.items || []),
    ...(resolvedAlertsQuery.data?.data?.items || []),
  ].sort((a, b) => {
    const left = a.resolved_at || a.acknowledged_at || a.last_seen_at || a.first_seen_at || ''
    const right = b.resolved_at || b.acknowledged_at || b.last_seen_at || b.first_seen_at || ''
    return right.localeCompare(left)
  })
  const users = usersQuery.data?.data?.items || []
  const userTotal = usersQuery.data?.data?.total || 0
  const userTotalPages = Math.max(Math.ceil(userTotal / userPageSize), 1)
  const userCurrentPage = Math.min(userPage + 1, userTotalPages)
  const selectedUsage = selectedUsageQuery.data?.data
  const resources = resourcesQuery.data?.data
  const storage = storageQuery.data?.data
  const promotionTag = promotionTagQuery.data?.data
  const selectedWindow = summary?.traffic_windows?.selected
  const resourceMetrics = resources?.resource_metrics

  const metricLabel = useMemo(() => {
    if (metric === 'duration') return 'Duration'
    if (metric === 'connections') return 'Connects'
    if (metric === 'errors') return 'Errors'
    return 'Traffic'
  }, [metric])

  const submitPromotionTag = () => {
    setFeedback(null)
    updateTagMutation.mutate(tagValue)
  }

  const reviewUser = (assignmentId?: number | null, alertId?: number | null) => {
    if (!assignmentId) return
    setSelectedAssignmentId(assignmentId)
    setSelectedAlertId(alertId || null)
    setActiveTab('users')
  }

  return (
    <section
      className="grid gap-3 phase58-route-frame"
      data-phase42-mtproto-analytics
      data-phase43-mtproto-analytics
      data-phase54-mtproto-analytics="compact"
      data-phase58-runtime-readonly="[PremiumAdminCockpit][phase58][ANALYTICS_RUNTIME_READONLY]"
      data-phase62-admin-surface="[CompactDeletionAudit][phase62][ADMIN_SURFACES_INVENTORIED]"
      data-phase59-status-transitions="[MatrixMotion][phase59][STATUS_TRANSITIONS_READY]"
      data-phase59-microinteractions="[MatrixMotion][phase59][MICROINTERACTIONS_READY]"
      data-observe-mode="observe-only"
      data-log-marker="[M-058][admin_mtproto_analytics_ui][REDACTED_RENDER]"
      data-phase43-recent-events="[M-058][admin_mtproto_analytics_ui][RECENT_EVENTS_REMOVED]"
      data-phase54-signals-hidden="[M-058][phase54_mtproto_analytics][SIGNALS_STILL_HIDDEN]"
      data-phase54-redaction="[M-058][phase54_mtproto_analytics][PROMOTION_TAG_REDACTED]"
    >
      <div className="surface p-3">
        <div className="compact-toolbar">
          <div className="min-w-0">
            <h2 className="text-base font-bold text-white">MTProto analytics</h2>
            <div className="mt-2 flex flex-wrap gap-2">
              {(['overview', 'users', 'abuse', 'settings'] as TabKey[]).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  className={activeTab === tab ? 'btn-primary px-3 py-2' : 'btn-secondary px-3 py-2'}
                  onClick={() => setActiveTab(tab)}
                >
                  {tab === 'overview' ? 'Overview' : tab === 'users' ? 'Users' : tab === 'abuse' ? 'Abuse' : 'Settings'}
                </button>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap gap-2" data-log-marker="[M-058][admin_mtproto_analytics_ui][FILTER_USAGE]">
            {[1, 7, 30].map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setDays(value)}
                className={days === value ? 'btn-primary px-3 py-2' : 'btn-secondary px-3 py-2'}
              >
                {value === 1 ? 'Day' : value === 7 ? 'Week' : 'Month'}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-3 mini-kpi-grid">
          <div className="metric-tile">
            <RadioTower className="mb-2 h-4 w-4 text-cyan-100" />
            <span className="metric-label">Issued</span>
            <strong className="mt-1 block text-xl text-white">{summary?.issued_total ?? 0}</strong>
            <span className="text-xs muted">active {summary?.status_counts?.active ?? 0}</span>
          </div>
          <div className="metric-tile">
            <Activity className="mb-2 h-4 w-4 text-cyan-100" />
            <span className="metric-label">Live</span>
            <strong className="mt-1 block text-xl text-white">{summary?.active_connections ?? 0}</strong>
            <span className="text-xs muted">{summary?.telemetry_status || 'missing'}</span>
          </div>
          <div className="metric-tile">
            <BarChart3 className="mb-2 h-4 w-4 text-cyan-100" />
            <span className="metric-label">Traffic</span>
            <strong className="mt-1 block text-xl text-white">{formatBytes(selectedWindow?.traffic_bytes)}</strong>
            <span className="text-xs muted">{selectedWindow?.connection_count ?? 0} connects</span>
          </div>
          <div className="metric-tile">
            <ShieldAlert className="mb-2 h-4 w-4 text-cyan-100" />
            <span className="metric-label">Alerts</span>
            <strong className="mt-1 block text-xl text-white">{alertsQuery.data?.data?.open_count ?? summary?.open_alert_count ?? 0}</strong>
            <span className="text-xs muted">open inbox</span>
          </div>
        </div>
      </div>

      {activeTab === 'overview' ? (
        <div className="grid gap-3 xl:grid-cols-[1.35fr_0.65fr]">
          <div className="surface p-3 phase58-chart-card">
            <div className="compact-toolbar">
              <div className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-cyan-200" />
                <h3 className="text-sm font-semibold text-white">{metricLabel}</h3>
              </div>
              <select className="input max-w-[180px]" value={metric} onChange={(event) => setMetric(event.target.value as MetricKey)}>
                <option value="traffic">Traffic</option>
                <option value="duration">Duration</option>
                <option value="connections">Connects</option>
                <option value="errors">Errors</option>
              </select>
            </div>
            <MetricAreaChart data={timeseries} metric={metric} />
          </div>

          <div className="surface p-3 phase58-readonly-frame">
            <div className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-cyan-200" />
              <h3 className="text-sm font-semibold text-white">Runtime</h3>
            </div>
            <div className="mt-3 grid gap-2">
              <div className="list-row py-3">
                <span className="row-title">CPU</span>
                <span className="metric-pill">{formatPercent(resourceMetrics?.cpu_percent)}</span>
              </div>
              <div className="list-row py-3">
                <span className="row-title">RAM</span>
                <span className="metric-pill">{formatBytes(resourceMetrics?.memory_rss_bytes || resourceMetrics?.memory_total_bytes)}</span>
              </div>
              <div className="list-row py-3">
                <span className="row-title">Buffered</span>
                <span className="metric-pill">{resources?.buffered_events ?? 0}</span>
              </div>
              <div className="list-row py-3">
                <span className="row-title">Dropped</span>
                <span className={resources?.dropped_events ? 'warning-pill' : 'metric-pill'}>{resources?.dropped_events ?? 0}</span>
              </div>
              <div className="list-row py-3">
                <span className="row-title">req_pq</span>
                <span className="metric-pill">{summary?.availability_proof?.status || 'missing'}</span>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {activeTab === 'users' ? (
        <div className="grid gap-3 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="surface p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4 text-cyan-200" />
                <h3 className="text-sm font-semibold text-white">Users</h3>
              </div>
              <div className="flex min-w-[240px] flex-1 flex-wrap gap-2 sm:flex-none">
                <div className="relative min-w-[220px] flex-1">
                  <Search className="input-icon-left" />
                  <input className="input input-with-icon-left w-full" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="email, SNI, id" />
                </div>
                <select className="input max-w-[110px]" value={userPageSize} onChange={(event) => setUserPageSize(Number(event.target.value))}>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </div>
            </div>
            <div className="compact-toolbar mt-3 text-xs muted">
              <span>Найдено {userTotal} · страница {userCurrentPage}/{userTotalPages}</span>
              <div className="flex gap-2">
                <button type="button" className="btn-secondary px-3 py-2" onClick={() => setUserPage((value) => Math.max(value - 1, 0))} disabled={userPage === 0}>
                  Назад
                </button>
                <button type="button" className="btn-secondary px-3 py-2" onClick={() => setUserPage((value) => Math.min(value + 1, userTotalPages - 1))} disabled={userPage >= userTotalPages - 1}>
                  Далее
                </button>
              </div>
            </div>
            <div
              className="mt-3 compact-list bounded-scroll phase58-inventory-list phase58-scroll-rail"
              data-phase58-inventory="[PremiumAdminCockpit][phase58][INVENTORIES_BOUNDED]"
            >
              {users.length === 0 ? (
                <p className="py-4 text-sm muted">Нет данных.</p>
              ) : users.map((item: AdminMTProtoUserSearchItem) => (
                <button
                  key={item.assignment_id}
                  type="button"
                  onClick={() => reviewUser(item.assignment_id)}
                  className={selectedAssignmentId === item.assignment_id ? 'list-row w-full py-3 text-left ring-1 ring-cyan-300/40' : 'list-row w-full py-3 text-left'}
                  data-log-marker="[M-058][admin_mtproto_analytics_ui][USER_DETAIL_DRAWER]"
                >
                  <div className="row-main">
                    <div className="min-w-0">
                      <p className="row-title">{item.user_display_name || item.user_email || `User #${item.user_id}`}</p>
                      <p className="row-subtitle">{item.sni_masked || `Assignment #${item.assignment_id}`}</p>
                    </div>
                    <span className={item.status === 'active' ? 'metric-pill motion-status' : 'warning-pill motion-status'}>{item.status}</span>
                  </div>
                  <div className="row-meta">
                    <span className="meta-cell"><span className="meta-label">Issued</span><span className="meta-value">{formatDate(item.issued_at)}</span></span>
                    <span className="meta-cell"><span className="meta-label">Last</span><span className="meta-value">{formatDate(item.last_seen_at)}</span></span>
                    <span className="meta-cell"><span className="meta-label">Now</span><span className="meta-value">{item.active_connections}</span></span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="surface p-3 xl:sticky xl:top-3 xl:self-start">
            {!selectedUsage ? (
              <div className="flex min-h-[300px] items-center justify-center text-sm muted">
                <Eye className="mr-2 h-4 w-4" />
                Выберите пользователя
              </div>
            ) : (
              <div className="grid gap-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="truncate text-sm font-semibold text-white">{selectedUsage.assignment.user_email || `User #${selectedUsage.assignment.user_id}`}</h3>
                    <p className="row-subtitle">{selectedUsage.assignment.sni_masked}</p>
                  </div>
                  <span className={selectedUsage.assignment.status === 'active' ? 'metric-pill motion-status' : 'warning-pill motion-status'}>{selectedUsage.assignment.status}</span>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="metric-tile"><span className="metric-label">Issued</span><strong className="mt-1 block text-sm text-white">{formatDate(selectedUsage.assignment.issued_at)}</strong></div>
                  <div className="metric-tile"><span className="metric-label">Last seen</span><strong className="mt-1 block text-sm text-white">{formatDate(selectedUsage.last_seen_at)}</strong></div>
                  <div className="metric-tile"><span className="metric-label">Traffic</span><strong className="mt-1 block text-sm text-white">{formatBytes(selectedUsage.bytes_in + selectedUsage.bytes_out)}</strong></div>
                  <div className="metric-tile"><span className="metric-label">Sessions</span><strong className="mt-1 block text-sm text-white">{selectedUsage.session_count}</strong></div>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <IPPanel title="Current IP" items={selectedUsage.current_ips} />
                  <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                    <span className="metric-label">Last IP</span>
                    <strong className="mt-1 block text-sm text-white">{selectedUsage.last_ip?.ip_address || selectedUsage.ip_source_status}</strong>
                    <span className="text-xs muted">{formatDate(selectedUsage.last_ip?.last_seen_at)}</span>
                  </div>
                </div>
                {selectedUsage.ip_source_status === 'source_ip_unavailable' ? (
                  <SourceIPNotice />
                ) : null}
                <div className="grid gap-2">
                  <div className="flex items-center justify-between gap-2">
                    <h4 className="text-sm font-semibold text-white">IP history</h4>
                    {selectedAlertId && selectedUsage.last_ip?.id ? (
                      <button
                        type="button"
                        className="btn-secondary px-3 py-2"
                        onClick={() => blockIpMutation.mutate({ alertId: selectedAlertId, observationId: selectedUsage.last_ip!.id })}
                        disabled={blockIpMutation.isLoading}
                        title="Заблокировать последний IP на 24 часа и закрыть alert"
                        aria-label="Заблокировать последний IP на 24 часа и закрыть alert"
                      >
                        <XCircle className="h-4 w-4" />
                        Block
                      </button>
                    ) : null}
                  </div>
                  <div
                    className="compact-list bounded-scroll max-h-[180px] overflow-y-auto overscroll-contain pr-1 phase58-scroll-rail"
                    data-log-marker="[M-058][admin_mtproto_analytics_ui][COMPACT_IP_HISTORY]"
                    data-phase58-inventory="[PremiumAdminCockpit][phase58][INVENTORIES_BOUNDED]"
                    data-mtproto-ip-history-scroll
                  >
                    {selectedUsage.ip_observations.length === 0 ? (
                      <p className="py-2 text-sm muted">Нет IP history</p>
                    ) : selectedUsage.ip_observations.map((ip: AdminMTProtoIPObservation) => (
                      <div key={ip.id} className="list-row py-2">
                        <div className="row-main">
                          <div className="min-w-0">
                            <p className="row-title truncate font-mono text-xs">{ip.ip_address || ip.ip_hash_prefix}</p>
                          </div>
                          <span className={ip.current_active ? 'metric-pill motion-status' : 'neutral-pill motion-status'}>{ip.current_active ? 'active' : 'seen'}</span>
                        </div>
                        <div className="row-meta">
                          <span className="meta-cell"><span className="meta-label">Last</span><span className="meta-value">{formatDate(ip.last_seen_at)}</span></span>
                          <span className="meta-cell"><span className="meta-label">Connects</span><span className="meta-value">{ip.connection_count}</span></span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {activeTab === 'abuse' ? (
        <div className="grid gap-3">
          <div
            className="surface p-3 phase58-readonly-frame"
            data-log-marker="[M-058][admin_mtproto_analytics_ui][ALERT_REVIEW]"
            data-phase62-keep="[CompactDeletionAudit][phase62][EMERGENCY_CONTROLS_PRESERVED]"
          >
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-cyan-200" />
              <h3 className="text-sm font-semibold text-white">Alerts</h3>
            </div>
            <p className="mt-2 text-xs muted">В inbox попадает только жесткий abuse: высокая одновременная активность, много разных IP и сильные всплески. Обычная смена сети не создает тревогу.</p>
            <div className="mt-3 flex items-center justify-between gap-2">
              <h4 className="text-xs font-semibold uppercase text-slate-400">Open</h4>
              <span className="neutral-pill">{alerts.length}</span>
            </div>
            <div className="mt-2 compact-list bounded-scroll max-h-[320px] phase58-scroll-rail">
              {alerts.length === 0 ? (
                <p className="py-4 pl-4 text-sm muted">Нет открытых alerts</p>
              ) : alerts.map((alert: AdminMTProtoAlert) => (
                <div key={alert.id} className="list-row py-3">
                  <div className="row-main">
                    <div className="min-w-0">
                      <p className="row-title">{alert.signal_type}</p>
                      <p className="row-subtitle">{alert.user_email || `Assignment #${alert.assignment_id || 'unknown'}`} · {alert.metric_value}/{alert.threshold_value}</p>
                    </div>
                    <span className={alert.severity === 'critical' ? 'warning-pill motion-status' : 'metric-pill motion-status'}>{alert.severity}</span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2" data-log-marker="[M-058][admin_mtproto_analytics_ui][ALERT_ACTION_TOOLTIP]">
                    <button
                      type="button"
                      className="btn-secondary px-3 py-2"
                      onClick={() => reviewUser(alert.assignment_id, alert.id)}
                      title="Открыть карточку пользователя, IP history и детали этого proxy"
                      aria-label="Открыть карточку пользователя, IP history и детали этого proxy"
                    >
                      Review
                    </button>
                    <button
                      type="button"
                      className="btn-secondary px-3 py-2"
                      onClick={() => alertMutation.mutate({ id: alert.id, action: 'ack' })}
                      disabled={alertMutation.isLoading}
                      title="Пометить alert как просмотренный без блокировки пользователя"
                      aria-label="Пометить alert как просмотренный без блокировки пользователя"
                    >
                      <CheckCircle2 className="h-4 w-4" />
                      Ack
                    </button>
                    <button
                      type="button"
                      className="btn-secondary px-3 py-2"
                      onClick={() => alertMutation.mutate({ id: alert.id, action: 'resolve' })}
                      disabled={alertMutation.isLoading}
                      title="Закрыть alert без блокировки, инцидент уйдет в архив"
                      aria-label="Закрыть alert без блокировки, инцидент уйдет в архив"
                    >
                      Resolve
                    </button>
                    <button
                      type="button"
                      className="btn-secondary px-3 py-2"
                      onClick={() => alertMutation.mutate({ id: alert.id, action: 'disable' })}
                      disabled={alertMutation.isLoading}
                      title="Отключить MTProto proxy этого пользователя и закрыть alert"
                      aria-label="Отключить MTProto proxy этого пользователя и закрыть alert"
                    >
                      <XCircle className="h-4 w-4" />
                      Disable
                    </button>
                  </div>
                </div>
              ))}
            </div>
            <details
              className="phase62-admin-fold mt-4"
              data-phase62-collapse="[CompactDeletionAudit][phase62][ADMIN_SURFACES_PRUNED]"
              data-log-marker="[M-058][admin_mtproto_analytics_ui][ALERT_ARCHIVE]"
            >
              <summary className="phase62-fold-summary">
                <span className="text-xs font-semibold uppercase text-slate-400">Archive</span>
                <span className="neutral-pill">{archivedAlerts.length}</span>
              </summary>
              <div className="mt-2 compact-list bounded-scroll max-h-[260px] phase58-scroll-rail">
                {archivedAlerts.length === 0 ? (
                  <p className="py-4 pl-4 text-sm muted">Архив пуст</p>
                ) : archivedAlerts.map((alert: AdminMTProtoAlert) => (
                  <div key={`archive-${alert.id}-${alert.status}`} className="list-row py-3">
                    <div className="row-main">
                      <div className="min-w-0">
                        <p className="row-title">{alert.signal_type}</p>
                        <p className="row-subtitle">{alert.user_email || `Assignment #${alert.assignment_id || 'unknown'}`} · {formatDate(alert.resolved_at || alert.acknowledged_at || alert.last_seen_at)}</p>
                      </div>
                      <span className="neutral-pill motion-status">{alert.status}</span>
                    </div>
                    <div className="row-meta">
                      <span className="meta-cell"><span className="meta-label">Action</span><span className="meta-value">{alert.action_taken || 'review'}</span></span>
                      <span className="meta-cell"><span className="meta-label">Result</span><span className="meta-value">{alert.action_result || alert.status}</span></span>
                    </div>
                  </div>
                ))}
              </div>
            </details>
          </div>
        </div>
      ) : null}

      {activeTab === 'settings' ? (
        <div className="grid gap-3 xl:grid-cols-2">
          <div className="surface p-3">
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-cyan-200" />
              <h3 className="text-sm font-semibold text-white">Top users</h3>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <select className="input max-w-[170px]" value={metric} onChange={(event) => setMetric(event.target.value as MetricKey)}>
                <option value="traffic">Traffic</option>
                <option value="duration">Duration</option>
                <option value="connections">Connects</option>
                <option value="errors">Errors</option>
              </select>
              <select className="input max-w-[140px]" value={topLimit} onChange={(event) => setTopLimit(Number(event.target.value))}>
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>
            <div
              className="mt-3 compact-list bounded-scroll phase58-inventory-list phase58-scroll-rail"
              data-phase58-inventory="[PremiumAdminCockpit][phase58][INVENTORIES_BOUNDED]"
            >
              {topUsers.length === 0 ? (
                <p className="py-4 text-sm muted">Нет данных.</p>
              ) : topUsers.map((user: AdminMTProtoTopUser) => (
                <div key={user.user_id} className="list-row py-3">
                  <div className="row-main">
                    <div className="min-w-0">
                      <p className="row-title">{user.user_display_name || user.user_email || `User #${user.user_id}`}</p>
                      <p className="row-subtitle">#{user.user_id}</p>
                    </div>
                    <span className="metric-pill">{metricLabel}</span>
                  </div>
                  <div className="row-meta">
                    <span className="meta-cell"><span className="meta-label">Traffic</span><span className="meta-value">{formatBytes(user.traffic_bytes)}</span></span>
                    <span className="meta-cell"><span className="meta-label">Duration</span><span className="meta-value">{formatDuration(user.duration_ms)}</span></span>
                    <span className="meta-cell"><span className="meta-label">Connects</span><span className="meta-value">{user.connection_count}</span></span>
                    <span className="meta-cell"><span className="meta-label">Errors</span><span className="meta-value">{user.error_count}</span></span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="grid gap-3">
            <div className="surface p-3">
              <div className="flex items-center gap-2">
                <Tag className="h-4 w-4 text-cyan-200" />
                <h3 className="text-sm font-semibold text-white">Promotion tag</h3>
              </div>
              <div className="mt-3 grid gap-2">
                <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                  <span className="metric-label">Current</span>
                  <strong className="mt-1 block text-lg text-white">{promotionTag?.masked_tag || '0000...0000'}</strong>
                  <span className={promotionTag?.pending_restart ? 'warning-pill motion-status mt-2 inline-flex' : 'metric-pill motion-status mt-2 inline-flex'}>
                    {promotionTag?.runtime_status || 'applied'}
                  </span>
                </div>
                <input className="input" value={tagValue} onChange={(event) => setTagValue(event.target.value)} placeholder="32 hex tag" inputMode="text" />
                <button
                  type="button"
                  className="btn-primary"
                  onClick={submitPromotionTag}
                  disabled={updateTagMutation.isLoading || tagValue.length === 0}
                  data-log-marker="[M-058][admin_mtproto_analytics_ui][PROMOTION_TAG_CONFIRM]"
                >
                  <Save className="h-4 w-4" />
                  {updateTagMutation.isLoading ? 'Saving...' : 'Save tag'}
                </button>
              </div>
            </div>

            <details className="surface p-3 phase62-admin-fold" data-phase62-collapse="mtproto-storage-secondary">
              <summary className="phase62-fold-summary">
                <span className="flex min-w-0 items-center gap-2">
                  <Database className="h-4 w-4 shrink-0 text-cyan-200" />
                  <span className="truncate font-semibold">Storage</span>
                </span>
                <span className="text-xs muted">retention</span>
              </summary>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <div className="metric-tile"><HardDrive className="mb-2 h-4 w-4 text-cyan-100" /><span className="metric-label">Estimated</span><strong className="mt-1 block text-sm text-white">{formatBytes(storage?.estimated_bytes)}</strong></div>
                <div className="metric-tile"><MemoryStick className="mb-2 h-4 w-4 text-cyan-100" /><span className="metric-label">IP rows</span><strong className="mt-1 block text-sm text-white">{storage?.counts?.ip_observations ?? 0}</strong></div>
              </div>
            </details>
          </div>
        </div>
      ) : null}

      {feedback ? (
        <p className={feedback.tone === 'success' ? 'motion-feedback-success text-sm text-emerald-100' : 'motion-feedback-error text-sm text-amber-100'}>{feedback.text}</p>
      ) : null}
    </section>
  )
}
// END_BLOCK: MTProtoAnalyticsPanel

function IPPanel({ title, items }: { title: string; items: AdminMTProtoIPObservation[] }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/5 p-3">
      <span className="metric-label">{title}</span>
      {items.length === 0 ? (
        <strong className="mt-1 block text-sm text-white">Нет данных</strong>
      ) : (
        <div className="mt-2 grid gap-1">
          {items.slice(0, 3).map((ip) => (
            <div key={ip.id} className="flex items-center justify-between gap-2 text-sm">
              <span className="truncate text-white">{ip.ip_address || ip.ip_hash_prefix}</span>
              <span className="metric-pill motion-status">{ip.active_connections}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function SourceIPNotice() {
  return (
    <div className="rounded-lg border border-amber-300/20 bg-amber-400/10 p-3 text-xs text-amber-100">
      Runtime еще не прислал доверенный client IP для этого proxy. После обновленного runtime-хука IP появится при следующем подключении пользователя.
    </div>
  )
}
