// FILE: frontend-admin/src/pages/MTProto.tsx
// VERSION: 1.3.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact Matrix admin page for redacted MTProto assignment observability and confirmation-safe lifecycle actions
//   SCOPE: Runtime health, paginated assignment search/status filters, redacted rows, reissue/revoke confirmation, embedded analytics panel, bounded inventory, and feedback
//   DEPENDS: M-010 (frontend-admin), M-047 (mtproto-admin-ops), M-058 (mtproto-admin-analytics-ui), M-037 (mobile-admin-console), M-038 (compact-ui-system), M-070 (matrix-visual-runtime), M-071 (matrix-style-system)
//   LINKS: M-010, M-047, M-058, M-037, M-038, M-070, M-071, V-M-047, V-M-058, Phase-54
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   MTProtoPage - Main compact admin MTProto operations page
//   formatDate - Helper: format ISO date to ru-RU locale string
//   statusClass - Helper: map assignment status to compact badge class
//   actionCopy - Labels and confirmation copy for MTProto assignment actions
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.3.0 - Phase-54 added Matrix route markers, bounded MTProto inventory, and confirmation/redaction smoke hooks.
//   LAST_CHANGE: v1.2.0 - Added paginated compact assignment inventory for large MTProto user sets.
//   LAST_CHANGE: v1.1.0 - Embedded Phase-42 compact MTProto analytics panel
//   LAST_CHANGE: v1.0.0 - Added Phase-33 redacted MTProto admin operations UI
// END_CHANGE_SUMMARY

import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import {
  AlertTriangle,
  KeyRound,
  Power,
  RefreshCw,
  Search,
  ServerCog,
  ShieldCheck,
  X,
} from 'lucide-react'
import { adminApi } from '../lib/api'
import type { AdminMTProtoAssignment } from '../types'
import MTProtoAnalyticsPanel from './MTProtoAnalytics'

type MTProtoAction = 'reissue' | 'revoke'

interface PendingAction {
  type: MTProtoAction
  assignment: AdminMTProtoAssignment
}

// START_BLOCK: actionCopy
const actionCopy: Record<MTProtoAction, { label: string; title: string; description: string; tone: 'danger' | 'normal' }> = {
  reissue: {
    label: 'Reissue',
    title: 'Перевыпустить MTProto',
    description: 'Будет обновлено только состояние выбранной MTProto выдачи. Секрет и ссылка не раскрываются в админке.',
    tone: 'normal',
  },
  revoke: {
    label: 'Revoke',
    title: 'Отключить MTProto',
    description: 'Будет отключена только эта MTProto выдача. KrotPN подписка, аккаунт и VPN устройства не меняются.',
    tone: 'danger',
  },
}
// END_BLOCK: actionCopy

// START_BLOCK: formatDate
function formatDate(value?: string | null) {
  if (!value) return 'Нет данных'
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
// END_BLOCK: formatDate

// START_BLOCK: statusClass
function statusClass(status: string) {
  if (status === 'active') return 'metric-pill shrink-0'
  if (status === 'reissue_required') return 'warning-pill shrink-0'
  if (status === 'disabled') return 'danger-pill shrink-0'
  return 'neutral-pill shrink-0'
}
// END_BLOCK: statusClass

// START_BLOCK: MTProtoPage
export default function MTProtoPage() {
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [pageSize, setPageSize] = useState(50)
  const [page, setPage] = useState(0)
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null)
  const queryClient = useQueryClient()
  const assignmentOffset = page * pageSize

  const assignmentsQuery = useQuery(
    ['admin-mtproto-assignments', search, statusFilter, assignmentOffset, pageSize],
    () => adminApi.getMTProtoAssignments(search, statusFilter, assignmentOffset, pageSize),
    { keepPreviousData: true }
  )
  const healthQuery = useQuery('admin-mtproto-health', () => adminApi.getMTProtoHealth())

  useEffect(() => {
    setPage(0)
  }, [search, statusFilter, pageSize])

  const mutateAndRefresh = (message: string) => ({
    onSuccess: () => {
      void queryClient.invalidateQueries('admin-mtproto-assignments')
      void queryClient.invalidateQueries('admin-mtproto-health')
      setFeedback({ tone: 'success', text: message })
      setPendingAction(null)
    },
    onError: (error: unknown) => {
      setFeedback({
        tone: 'error',
        text: (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Операция не выполнена',
      })
    },
  })

  const reissueMutation = useMutation((id: number) => adminApi.reissueMTProtoAssignment(id), mutateAndRefresh('MTProto выдача перевыпущена'))
  const revokeMutation = useMutation((id: number) => adminApi.revokeMTProtoAssignment(id), mutateAndRefresh('MTProto выдача отключена'))
  const isMutating = reissueMutation.isLoading || revokeMutation.isLoading
  const items = assignmentsQuery.data?.data?.items || []
  const total = assignmentsQuery.data?.data?.total || 0
  const totalPages = Math.max(Math.ceil(total / pageSize), 1)
  const currentPage = Math.min(page + 1, totalPages)
  const health = healthQuery.data?.data

  const counters = useMemo(() => {
    return items.reduce(
      (acc: { active: number; reissue: number; disabled: number }, item: AdminMTProtoAssignment) => {
        if (item.status === 'active') acc.active += 1
        if (item.status === 'reissue_required') acc.reissue += 1
        if (item.status === 'disabled') acc.disabled += 1
        return acc
      },
      { active: 0, reissue: 0, disabled: 0 }
    )
  }, [items])

  const openAction = (type: MTProtoAction, assignment: AdminMTProtoAssignment) => {
    setFeedback(null)
    setPendingAction({ type, assignment })
  }

  const runConfirmedAction = () => {
    if (!pendingAction) return
    if (pendingAction.type === 'reissue') reissueMutation.mutate(pendingAction.assignment.id)
    if (pendingAction.type === 'revoke') revokeMutation.mutate(pendingAction.assignment.id)
  }

  return (
    <div
      className="page-shell"
      data-phase33-mtproto-admin
      data-phase54-mtproto-admin="compact"
      data-log-marker="[M-047][admin_mtproto_ui][REDACTED_RENDER]"
      data-phase54-redaction-marker="[M-047][phase54_mtproto_admin][REDACTION_PRESERVED]"
    >
      <div className="page-header">
        <div>
          <h1 className="page-title">MTProto</h1>
          <p className="page-subtitle">Assignment inventory, runtime health и точечные действия без доступа к owner-only credentials.</p>
        </div>

        <div className="grid gap-2 sm:min-w-[460px]" data-log-marker="[M-047][phase54_mtproto_admin][OPS_CONTROLS_READABLE]">
          <div className="metric-strip">
            <div className="metric-strip-item">
              <span className="metric-label">Page active</span>
              <span className="block text-base font-bold">{counters.active}</span>
            </div>
            <div className="metric-strip-item">
              <span className="metric-label">Page reissue</span>
              <span className="block text-base font-bold">{counters.reissue}</span>
            </div>
            <div className="metric-strip-item">
              <span className="metric-label">Found</span>
              <span className="block text-base font-bold">{total}</span>
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-[1fr_150px_110px]">
            <div className="relative">
              <Search className="input-icon-left" />
              <input
                type="text"
                className="input input-with-icon-left"
                placeholder="Email, user id, assignment id, SNI"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>
            <select className="input" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">Все статусы</option>
              <option value="active">Active</option>
              <option value="reissue_required">Reissue</option>
              <option value="disabled">Disabled</option>
              <option value="superseded">Superseded</option>
            </select>
            <select className="input" value={pageSize} onChange={(event) => setPageSize(Number(event.target.value))}>
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </div>
        </div>
      </div>

      <section className="status-row surface p-3" data-log-marker="[MatrixVisualRuntime][phase54][ADMIN_ROUTE_CANVAS_READY]">
        <div className="flex min-w-0 items-center gap-2">
          <ServerCog className="h-5 w-5 shrink-0 text-cyan-200" />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-white">Runtime bridge</p>
            <p className="text-xs muted">{health?.adapter_name || 'adapter pending'} · {formatDate(health?.last_checked_at)}</p>
          </div>
        </div>
        <span className={health?.status === 'healthy' ? 'metric-pill' : health?.status === 'degraded' ? 'warning-pill' : 'neutral-pill'}>
          {health?.status === 'healthy' ? <ShieldCheck className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}
          {healthQuery.isLoading ? 'loading' : health?.status || 'unknown'}
        </span>
      </section>

      <MTProtoAnalyticsPanel />

      {feedback ? (
        <div className={feedback.tone === 'success' ? 'surface px-3 py-2 text-sm text-emerald-100' : 'surface px-3 py-2 text-sm text-amber-100'}>
          {feedback.text}
        </div>
      ) : null}

      {assignmentsQuery.isLoading ? (
        <div className="empty-state">
          <KeyRound className="h-9 w-9 text-cyan-200" />
          <div>
            <p className="text-base font-semibold">Загружаем MTProto выдачи</p>
            <p className="mt-1 text-sm muted">Проверяем registry и безопасный runtime summary.</p>
          </div>
        </div>
      ) : items.length === 0 ? (
        <div className="empty-state">
          <Search className="h-9 w-9 text-cyan-200" />
          <div>
            <p className="text-base font-semibold">Выдачи не найдены</p>
            <p className="mt-1 text-sm muted">Измени фильтр или дождись первого verified пользователя.</p>
          </div>
        </div>
      ) : (
        <section className="surface p-3">
          <div className="compact-toolbar mb-3 text-xs muted">
            <span>Показаны {items.length} из {total} · страница {currentPage}/{totalPages}</span>
            <div className="flex gap-2">
              <button type="button" className="btn-secondary px-3 py-2" onClick={() => setPage((value) => Math.max(value - 1, 0))} disabled={page === 0}>
                Назад
              </button>
              <button type="button" className="btn-secondary px-3 py-2" onClick={() => setPage((value) => Math.min(value + 1, totalPages - 1))} disabled={page >= totalPages - 1}>
                Далее
              </button>
            </div>
          </div>
          <div className="compact-list bounded-scroll max-h-[70vh]">
            {items.map((item: AdminMTProtoAssignment) => (
              <article key={item.id} className="list-row">
              <div className="row-main">
                <div className="min-w-0">
                  <h2 className="row-title">{item.user_display_name || item.user_email || `User #${item.user_id}`}</h2>
                  <p className="row-subtitle break-all">{item.sni}</p>
                </div>
                <span className={statusClass(item.status)}>{item.status}</span>
              </div>

              <div className="row-meta">
                <div className="meta-cell">
                  <span className="meta-label">Assignment</span>
                  <span className="meta-value">#{item.id}</span>
                </div>
                <div className="meta-cell">
                  <span className="meta-label">User</span>
                  <span className="meta-value">{item.user_email || `ID #${item.user_id}`}</span>
                </div>
                <div className="meta-cell">
                  <span className="meta-label">Rotation</span>
                  <span className="meta-value">{item.rotation_marker}</span>
                </div>
                <div className="meta-cell">
                  <span className="meta-label">Updated</span>
                  <span className="meta-value">{formatDate(item.updated_at)}</span>
                </div>
              </div>

              <div className="action-row">
                <button onClick={() => openAction('reissue', item)} className="btn-secondary">
                  <RefreshCw className="h-4 w-4" />
                  Reissue
                </button>
                <button
                  onClick={() => openAction('revoke', item)}
                  disabled={item.status === 'disabled'}
                  className="btn-danger"
                >
                  <Power className="h-4 w-4" />
                  Revoke
                </button>
              </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {pendingAction ? (
        <div
          className="confirm-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="mtproto-action-title"
          data-log-marker="[M-047][admin_mtproto_ui][CONFIRM_ACTION]"
          data-phase54-confirmation="[M-047][phase54_mtproto_admin][CONFIRMATIONS_SAFE]"
        >
          <div className="confirm-sheet">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p id="mtproto-action-title" className="text-lg font-bold text-white">
                  {actionCopy[pendingAction.type].title}
                </p>
                <p className="mt-2 text-sm muted">{actionCopy[pendingAction.type].description}</p>
              </div>
              <button onClick={() => setPendingAction(null)} className="btn-secondary px-2" aria-label="Закрыть подтверждение">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 grid gap-2 rounded-lg border border-white/10 bg-white/5 p-3 text-sm">
              <div>
                <span className="meta-label">Assignment</span>
                <span className="meta-value">#{pendingAction.assignment.id}</span>
              </div>
              <div>
                <span className="meta-label">User</span>
                <span className="meta-value">{pendingAction.assignment.user_email || `ID #${pendingAction.assignment.user_id}`}</span>
              </div>
              <div>
                <span className="meta-label">Scope</span>
                <span className="meta-value">Только MTProto assignment</span>
              </div>
            </div>

            <div className="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button onClick={() => setPendingAction(null)} disabled={isMutating} className="btn-secondary">
                Отмена
              </button>
              <button
                onClick={runConfirmedAction}
                disabled={isMutating}
                className={actionCopy[pendingAction.type].tone === 'danger' ? 'btn-danger' : 'btn-primary'}
              >
                {isMutating ? 'Выполняю...' : `Подтвердить ${actionCopy[pendingAction.type].label}`}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
// END_BLOCK: MTProtoPage
