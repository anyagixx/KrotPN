// FILE: frontend-admin/src/pages/Devices.tsx
// VERSION: 1.1.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact admin page for device management with confirmation-safe block/unblock, rotate config, and revoke actions
//   SCOPE: List devices with search, anti-sharing signals, device-level actions, confirmation surface, and feedback
//   DEPENDS: M-010 (frontend-admin), M-006 (admin API), M-024 (device-admin-control), M-037 (mobile-admin-console), M-038 (compact-ui-system)
//   LINKS: M-010, M-024, M-037, M-038
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   DevicesPage - Main compact admin devices page component
//   formatDate - Helper: format date to ru-RU locale string
//   actionCopy - Labels and descriptions for confirmation-safe device actions
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.9.0 - Phase-24 compact mobile device rows with explicit one-peer action confirmation
// END_CHANGE_SUMMARY

import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import { Ban, RotateCw, Search, ShieldAlert, ShieldCheck, Trash2, X } from 'lucide-react'
import { adminApi } from '../lib/api'
import type { AdminDevice } from '../types'

type DeviceAction = 'block' | 'unblock' | 'rotate' | 'revoke'

interface PendingAction {
  type: DeviceAction
  device: AdminDevice
}

// START_BLOCK: actionCopy
// Action labels and confirmation copy for one-device peer mutations
// DEPENDS: DeviceAction union
const actionCopy: Record<DeviceAction, { label: string; title: string; description: string; tone: 'danger' | 'normal' }> = {
  block: {
    label: 'Block',
    title: 'Заблокировать устройство',
    description: 'Будет заблокирован только этот peer. Аккаунт пользователя и другие устройства не отключаются.',
    tone: 'danger',
  },
  unblock: {
    label: 'Unblock',
    title: 'Снять блокировку',
    description: 'Доступ возвращается только выбранному устройству.',
    tone: 'normal',
  },
  rotate: {
    label: 'Rotate',
    title: 'Перевыпустить конфиг',
    description: 'Текущий конфиг выбранного устройства станет неактуальным после ротации.',
    tone: 'normal',
  },
  revoke: {
    label: 'Revoke',
    title: 'Отозвать устройство',
    description: 'Будет отозван только выбранный device-bound peer. Остальные устройства пользователя не меняются.',
    tone: 'danger',
  },
}
// END_BLOCK: actionCopy

// START_BLOCK: formatDate
// Formats ISO date string to ru-RU locale or returns 'Нет данных'
// DEPENDS: none (pure function)
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

// START_BLOCK: Devices
// Compact admin devices page: device registry, confirmation-safe block/unblock, rotate config, revoke
// DEPENDS: M-010 (frontend-admin), M-006/M-024 (admin API via adminApi)
//   - adminApi.getDevices, adminApi.blockDevice, adminApi.unblockDevice
//   - adminApi.rotateDevice, adminApi.revokeDevice
export default function Devices() {
  const [search, setSearch] = useState('')
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null)
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery(['admin-devices', search], () => adminApi.getDevices(search))

  const mutateAndRefresh = (message: string) => ({
    onSuccess: () => {
      void queryClient.invalidateQueries('admin-devices')
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

  const blockMutation = useMutation((id: number) => adminApi.blockDevice(id), mutateAndRefresh('Устройство заблокировано'))
  const unblockMutation = useMutation((id: number) => adminApi.unblockDevice(id), mutateAndRefresh('Блокировка снята'))
  const rotateMutation = useMutation((id: number) => adminApi.rotateDevice(id), mutateAndRefresh('Конфиг перевыпущен'))
  const revokeMutation = useMutation((id: number) => adminApi.revokeDevice(id), mutateAndRefresh('Устройство отозвано'))
  const isMutating = blockMutation.isLoading || unblockMutation.isLoading || rotateMutation.isLoading || revokeMutation.isLoading

  const items = data?.data?.items || []

  const counters = useMemo(() => {
    return items.reduce(
      (acc: { active: number; blocked: number; suspicious: number }, item: AdminDevice) => {
        if (item.status === 'blocked') acc.blocked += 1
        if (item.status === 'active') acc.active += 1
        if ((item.recent_event_types ?? []).some((event: string) => event.includes('suspicious') || event.includes('concurrent'))) {
          acc.suspicious += 1
        }
        return acc
      },
      { active: 0, blocked: 0, suspicious: 0 }
    )
  }, [items])

  const openAction = (type: DeviceAction, device: AdminDevice) => {
    setFeedback(null)
    setPendingAction({ type, device })
  }

  const runConfirmedAction = () => {
    if (!pendingAction) return
    const id = pendingAction.device.id

    if (pendingAction.type === 'block') blockMutation.mutate(id)
    if (pendingAction.type === 'unblock') unblockMutation.mutate(id)
    if (pendingAction.type === 'rotate') rotateMutation.mutate(id)
    if (pendingAction.type === 'revoke') revokeMutation.mutate(id)
  }

  return (
    <div className="page-shell">
      <div className="page-header">
        <div>
          <h1 className="page-title">Устройства</h1>
          <p className="page-subtitle">Device-bound peer inventory, anti-sharing сигналы и санкции строго на уровне одного устройства.</p>
        </div>

        <div className="grid gap-2 sm:min-w-[420px]">
          <div className="metric-strip">
            <div className="metric-strip-item">
              <span className="metric-label">Активные</span>
              <span className="block text-base font-bold">{counters.active}</span>
            </div>
            <div className="metric-strip-item">
              <span className="metric-label">Блок</span>
              <span className="block text-base font-bold">{counters.blocked}</span>
            </div>
            <div className="metric-strip-item">
              <span className="metric-label">Сигналы</span>
              <span className="block text-base font-bold">{counters.suspicious}</span>
            </div>
          </div>

          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              className="input pl-10"
              placeholder="Поиск по email, имени, платформе"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
        </div>
      </div>

      {feedback ? (
        <div className={feedback.tone === 'success' ? 'surface px-3 py-2 text-sm text-emerald-100' : 'surface px-3 py-2 text-sm text-amber-100'}>
          {feedback.text}
        </div>
      ) : null}

      {isLoading ? (
        <div className="empty-state">
          <ShieldAlert className="h-9 w-9 text-cyan-200" />
          <div>
            <p className="text-base font-semibold">Загружаем устройства и сигналы</p>
            <p className="mt-1 text-sm muted">Тянем device registry и свежие security events из admin API.</p>
          </div>
        </div>
      ) : items.length === 0 ? (
        <div className="empty-state">
          <Search className="h-9 w-9 text-cyan-200" />
          <div>
            <p className="text-base font-semibold">Устройства не найдены</p>
            <p className="mt-1 text-sm muted">Измени запрос или дождись первой device-bound выдачи.</p>
          </div>
        </div>
      ) : (
        <div className="compact-list">
          {items.map((item: AdminDevice) => (
            <article key={item.id} className="list-row">
              <div className="row-main">
                <div className="min-w-0">
                  <h2 className="row-title">{item.name}</h2>
                  <p className="row-subtitle">{item.user_display_name || item.user_email || `User #${item.user_id}`}</p>
                </div>

                <span className={item.status === 'blocked' ? 'danger-pill shrink-0' : 'metric-pill shrink-0'}>
                  {item.status === 'blocked' ? <Ban className="h-3.5 w-3.5" /> : <ShieldCheck className="h-3.5 w-3.5" />}
                  {item.status}
                </span>
              </div>

              <div className="row-meta">
                <div className="meta-cell">
                  <span className="meta-label">Пользователь</span>
                  <span className="meta-value">{item.user_email || `ID #${item.user_id}`}</span>
                </div>
                <div className="meta-cell">
                  <span className="meta-label">Платформа</span>
                  <span className="meta-value">{item.platform || 'platform not set'} · v{item.config_version}</span>
                </div>
                <div className="meta-cell">
                  <span className="meta-label">Endpoint</span>
                  <span className="meta-value">{item.last_endpoint || 'Нет endpoint'}</span>
                </div>
                <div className="meta-cell">
                  <span className="meta-label">Handshake</span>
                  <span className="meta-value">{formatDate(item.last_handshake_at)}</span>
                </div>
              </div>

              {item.block_reason ? <p className="mt-2 text-xs text-amber-100">reason: {item.block_reason}</p> : null}

              <div className="mt-3 flex flex-wrap gap-2">
                {(item.recent_event_types ?? []).length ? (
                  (item.recent_event_types ?? []).map((event: string) => (
                    <span key={`${item.id}-${event}`} className="warning-pill">
                      {event}
                    </span>
                  ))
                ) : (
                  <span className="neutral-pill">Нет сигналов</span>
                )}
              </div>

              <div className="action-row">
                {item.status === 'blocked' ? (
                  <button onClick={() => openAction('unblock', item)} className="btn-secondary">
                    <ShieldCheck className="h-4 w-4" />
                    Unblock
                  </button>
                ) : (
                  <button onClick={() => openAction('block', item)} className="btn-secondary">
                    <Ban className="h-4 w-4" />
                    Block
                  </button>
                )}
                <button onClick={() => openAction('rotate', item)} className="btn-secondary">
                  <RotateCw className="h-4 w-4" />
                  Rotate
                </button>
                <button onClick={() => openAction('revoke', item)} className="btn-danger">
                  <Trash2 className="h-4 w-4" />
                  Revoke
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      {pendingAction ? (
        <div className="confirm-backdrop" role="dialog" aria-modal="true" aria-labelledby="device-action-title">
          <div className="confirm-sheet">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p id="device-action-title" className="text-lg font-bold text-white">
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
                <span className="meta-label">Device</span>
                <span className="meta-value">{pendingAction.device.name}</span>
              </div>
              <div>
                <span className="meta-label">User</span>
                <span className="meta-value">{pendingAction.device.user_email || `ID #${pendingAction.device.user_id}`}</span>
              </div>
              <div>
                <span className="meta-label">Peer scope</span>
                <span className="meta-value">Только device #{pendingAction.device.id}</span>
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
// END_BLOCK: Devices
