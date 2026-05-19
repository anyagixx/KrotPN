// FILE: frontend-admin/src/pages/MTProtoAnalytics.tsx
// VERSION: 1.0.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact admin MTProto analytics panel with metadata-only usage, abuse, runtime proof, and promotion tag controls
//   SCOPE: Summary cards, window filters, top users, abuse signals, recent events, and masked promotion tag update
//   DEPENDS: M-010 (frontend-admin), M-058 (mtproto-admin-analytics-ui), M-057 (admin analytics API), M-059 (promotion tag)
//   LINKS: M-058, M-057, M-059, V-M-058
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   MTProtoAnalyticsPanel - Compact analytics panel embedded in MTProto admin page
//   formatBytes - Helper: render byte counters
//   formatDuration - Helper: render millisecond durations
//   formatDate - Helper: render ISO timestamps
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.0.0 - Added Phase-42 MTProto analytics and promotion tag panel
// END_CHANGE_SUMMARY

import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import {
  Activity,
  BarChart3,
  Clock3,
  Eye,
  RadioTower,
  Save,
  ShieldAlert,
  Tag,
  Users,
} from 'lucide-react'
import { adminApi } from '../lib/api'
import type { AdminMTProtoAbuseSignal, AdminMTProtoTopUser, AdminMTProtoUsageEvent } from '../types'

type MetricKey = 'traffic' | 'duration' | 'connections' | 'errors'

// START_BLOCK: formatters
function formatBytes(value?: number) {
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

function formatDuration(value?: number) {
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
// END_BLOCK: formatters

// START_BLOCK: MTProtoAnalyticsPanel
export default function MTProtoAnalyticsPanel() {
  const [days, setDays] = useState(30)
  const [metric, setMetric] = useState<MetricKey>('traffic')
  const [tagValue, setTagValue] = useState('')
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
  const queryClient = useQueryClient()

  const summaryQuery = useQuery(['admin-mtproto-analytics-summary', days], () => adminApi.getMTProtoAnalyticsSummary(days))
  const topUsersQuery = useQuery(['admin-mtproto-top-users', metric, days], () => adminApi.getMTProtoTopUsers(metric, days, 5))
  const eventsQuery = useQuery(['admin-mtproto-events', days], () => adminApi.getMTProtoEvents({ days, limit: 8 }))
  const abuseQuery = useQuery(['admin-mtproto-abuse', days], () => adminApi.getMTProtoAbuseSignals(days))
  const promotionTagQuery = useQuery('admin-mtproto-promotion-tag', () => adminApi.getMTProtoPromotionTag())

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

  const summary = summaryQuery.data?.data
  const topUsers = topUsersQuery.data?.data?.items || []
  const events = eventsQuery.data?.data?.items || []
  const abuseSignals = abuseQuery.data?.data?.items || []
  const promotionTag = promotionTagQuery.data?.data
  const selectedWindow = summary?.traffic_windows?.selected

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

  return (
    <section
      className="grid gap-3"
      data-phase42-mtproto-analytics
      data-log-marker="[M-058][admin_mtproto_analytics_ui][REDACTED_RENDER]"
    >
      <div className="surface p-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <h2 className="text-base font-bold text-white">Usage analytics</h2>
            <p className="text-xs muted">Metadata-only counters, runtime proof and observe-only abuse signals.</p>
          </div>
          <div className="flex gap-2" data-log-marker="[M-058][admin_mtproto_analytics_ui][FILTER_USAGE]">
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

        <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <div className="metric-tile">
            <div className="mb-2 inline-flex h-8 w-8 items-center justify-center rounded-lg bg-white/10 text-cyan-100"><RadioTower className="h-4 w-4" /></div>
            <span className="metric-label">Issued</span>
            <strong className="mt-1 block text-xl text-white">{summary?.issued_total ?? 0}</strong>
            <span className="text-xs muted">active {summary?.status_counts?.active ?? 0}</span>
          </div>
          <div className="metric-tile">
            <div className="mb-2 inline-flex h-8 w-8 items-center justify-center rounded-lg bg-white/10 text-cyan-100"><Activity className="h-4 w-4" /></div>
            <span className="metric-label">Live</span>
            <strong className="mt-1 block text-xl text-white">{summary?.active_connections ?? 0}</strong>
            <span className="text-xs muted">{summary?.telemetry_status || 'missing'}</span>
          </div>
          <div className="metric-tile">
            <div className="mb-2 inline-flex h-8 w-8 items-center justify-center rounded-lg bg-white/10 text-cyan-100"><BarChart3 className="h-4 w-4" /></div>
            <span className="metric-label">Traffic</span>
            <strong className="mt-1 block text-xl text-white">{formatBytes(selectedWindow?.traffic_bytes)}</strong>
            <span className="text-xs muted">{selectedWindow?.connection_count ?? 0} connects</span>
          </div>
          <div className="metric-tile">
            <div className="mb-2 inline-flex h-8 w-8 items-center justify-center rounded-lg bg-white/10 text-cyan-100"><Clock3 className="h-4 w-4" /></div>
            <span className="metric-label">req_pq proof</span>
            <strong className="mt-1 block text-xl text-white">{summary?.availability_proof?.status || 'missing'}</strong>
            <span className="text-xs muted">{formatDate(summary?.availability_proof?.req_pq_last_at)}</span>
          </div>
        </div>
      </div>

      <div className="grid gap-3 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="surface p-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-cyan-200" />
              <h3 className="text-sm font-semibold text-white">Top users</h3>
            </div>
            <select className="input max-w-[190px]" value={metric} onChange={(event) => setMetric(event.target.value as MetricKey)}>
              <option value="traffic">Traffic</option>
              <option value="duration">Duration</option>
              <option value="connections">Connects</option>
              <option value="errors">Errors</option>
            </select>
          </div>
          <div className="mt-3 compact-list">
            {topUsers.length === 0 ? (
              <p className="py-4 text-sm muted">Нет данных за выбранный период.</p>
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

        <div className="surface p-3">
          <div className="flex items-center gap-2">
            <Tag className="h-4 w-4 text-cyan-200" />
            <h3 className="text-sm font-semibold text-white">Promotion tag</h3>
          </div>
          <div className="mt-3 grid gap-2">
            <div className="rounded-lg border border-white/10 bg-white/5 p-3">
              <span className="metric-label">Current</span>
              <strong className="mt-1 block text-lg text-white">{promotionTag?.masked_tag || '0000...0000'}</strong>
              <span className={promotionTag?.pending_restart ? 'warning-pill mt-2 inline-flex' : 'metric-pill mt-2 inline-flex'}>
                {promotionTag?.runtime_status || 'applied'}
              </span>
            </div>
            <input
              className="input"
              value={tagValue}
              onChange={(event) => setTagValue(event.target.value)}
              placeholder="32 hex tag"
              inputMode="text"
            />
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
            {feedback ? (
              <p className={feedback.tone === 'success' ? 'text-sm text-emerald-100' : 'text-sm text-amber-100'}>{feedback.text}</p>
            ) : null}
          </div>
        </div>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <div className="surface p-3">
          <div className="flex items-center gap-2">
            <Eye className="h-4 w-4 text-cyan-200" />
            <h3 className="text-sm font-semibold text-white">Recent events</h3>
          </div>
          <div className="mt-3 compact-list">
            {events.length === 0 ? (
              <p className="py-4 text-sm muted">Событий пока нет.</p>
            ) : events.map((event: AdminMTProtoUsageEvent) => (
              <div key={event.id} className="list-row py-3">
                <div className="row-main">
                  <div className="min-w-0">
                    <p className="row-title">{event.event_type}</p>
                    <p className="row-subtitle">{event.sni_masked || `Assignment #${event.assignment_id || 'unknown'}`}</p>
                  </div>
                  <span className={event.error_code ? 'warning-pill' : 'neutral-pill'}>{formatDate(event.observed_at)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="surface p-3">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-cyan-200" />
            <h3 className="text-sm font-semibold text-white">Abuse signals</h3>
          </div>
          <div className="mt-3 compact-list">
            {abuseSignals.length === 0 ? (
              <p className="py-4 text-sm muted">Observe-only сигналов нет.</p>
            ) : abuseSignals.map((signal: AdminMTProtoAbuseSignal) => (
              <div key={signal.id} className="list-row py-3">
                <div className="row-main">
                  <div className="min-w-0">
                    <p className="row-title">{signal.signal_type}</p>
                    <p className="row-subtitle">Assignment #{signal.assignment_id || 'unknown'} · {signal.metric_value}/{signal.threshold_value}</p>
                  </div>
                  <span className="warning-pill">observe-only</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
// END_BLOCK: MTProtoAnalyticsPanel
