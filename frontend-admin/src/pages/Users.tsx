// FILE: frontend-admin/src/pages/Users.tsx
// VERSION: 1.4.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact Matrix admin users inventory with expandable device management, search, pagination, role/status display, mobile account summary, and Phase-75 unified Users/Devices proof
//   SCOPE: Paginated user list with search, compact rows, role badges, active/blocked status, grouped device rows, confirmation-safe device actions, bounded scrolling, phone-safe metadata, and dense operator filters
//   DEPENDS: M-010 (frontend-admin), M-006 (admin API), M-024 (device-admin-control), M-037 (mobile-admin-console), M-038 (compact-ui-system), M-071 (matrix-style-system), M-074 (responsive-device-adaptation), M-076 (premium-admin-cockpit), M-077 (matrix-motion-interactions)
//   LINKS: M-010, M-006, M-024, M-037, M-038, M-071, M-074, M-076, M-077, Phase-54, Phase-58, Phase-59, Phase-75
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   UsersPage - Main compact admin users page component with expandable per-user device management
//   actionCopy - Labels and descriptions for confirmation-safe device actions
//   formatDate - Helper: format date to ru-RU locale string
//   roleClass - Helper: choose role badge class
//   deviceStatusClass - Helper: choose device status badge class
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v3.2.0 - Phase-75 unified Users and Devices into expandable user inventory with preserved device actions and confirmation guards.
//   LAST_CHANGE: v3.1.0 - Phase-58 added premium bounded inventory markers and denser user search frame.
//   LAST_CHANGE: v3.0.0 - Phase-54 added Matrix route markers and bounded compact inventory behavior for large user sets.
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.9.0 - Phase-24 compact mobile user search rows without table-only dependency
// END_CHANGE_SUMMARY

import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import {
  Ban,
  ChevronDown,
  ChevronRight,
  RotateCw,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  UserCheck,
  UserRound,
  UserX,
  X,
} from 'lucide-react'
import { adminApi } from '../lib/api'
import type { AdminDevice, AdminUser, PaginatedResponse } from '../types'

type DeviceAction = 'block' | 'unblock' | 'rotate' | 'revoke'

interface PendingAction {
  type: DeviceAction
  device: AdminDevice
}

interface AdminDeviceResponse {
  items: AdminDevice[]
  total: number
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
// Formats ISO date string to ru-RU locale or returns fallback
// DEPENDS: none (pure function)
function formatDate(value?: string | null, fallback = 'Никогда') {
  if (!value) return fallback
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
// END_BLOCK: formatDate

// START_BLOCK: roleClass
// Returns compact badge class for admin role visibility
// DEPENDS: none (pure function)
function roleClass(role: string) {
  if (role === 'superadmin') return 'danger-pill'
  if (role === 'admin') return 'metric-pill'
  return 'neutral-pill'
}
// END_BLOCK: roleClass

// START_BLOCK: deviceStatusClass
// Returns compact badge class for device status visibility
// DEPENDS: none (pure function)
function deviceStatusClass(status: string) {
  if (status === 'blocked' || status === 'revoked') return 'danger-pill motion-status shrink-0'
  if (status === 'active') return 'metric-pill motion-status shrink-0'
  return 'neutral-pill motion-status shrink-0'
}
// END_BLOCK: deviceStatusClass

// START_BLOCK: Users
// Main compact admin users page: paginated user list with expandable per-user device rows and confirmation-safe peer actions
// DEPENDS: M-010 (frontend-admin), M-006/M-024 (admin API via adminApi)
//   - adminApi.getUsers, adminApi.getDevices
//   - adminApi.blockDevice, adminApi.unblockDevice
//   - adminApi.rotateDevice, adminApi.revokeDevice
export default function Users() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [expandedUserId, setExpandedUserId] = useState<number | null>(null)
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null)
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery<{ data: PaginatedResponse<AdminUser> }>(
    ['admin-users', page, search],
    () => adminApi.getUsers(page, search),
    { keepPreviousData: true }
  )

  const {
    data: devicesData,
    isLoading: devicesLoading,
    error: devicesError,
  } = useQuery<{ data: AdminDeviceResponse }>(
    ['admin-devices', 'phase75-unified-users'],
    () => adminApi.getDevices(''),
    { keepPreviousData: true }
  )

  const users = data?.data?.items || []
  const total = data?.data?.total || 0
  const pages = data?.data?.pages || 1
  const devices = devicesData?.data?.items || []

  const devicesByUser = useMemo(() => {
    return devices.reduce<Record<number, AdminDevice[]>>((acc, device) => {
      if (!acc[device.user_id]) acc[device.user_id] = []
      acc[device.user_id].push(device)
      return acc
    }, {})
  }, [devices])

  const counters = useMemo(() => {
    return users.reduce(
      (acc: { active: number; admins: number; blocked: number }, user: AdminUser) => {
        if (user.is_active) acc.active += 1
        else acc.blocked += 1
        if (user.role === 'admin' || user.role === 'superadmin') acc.admins += 1
        return acc
      },
      { active: 0, admins: 0, blocked: 0 }
    )
  }, [users])

  const deviceCounters = useMemo(() => {
    return devices.reduce(
      (acc: { active: number; blocked: number; suspicious: number }, device: AdminDevice) => {
        if (device.status === 'blocked') acc.blocked += 1
        if (device.status === 'active') acc.active += 1
        if ((device.recent_event_types ?? []).some((event) => event.includes('suspicious') || event.includes('concurrent'))) {
          acc.suspicious += 1
        }
        return acc
      },
      { active: 0, blocked: 0, suspicious: 0 }
    )
  }, [devices])

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
    <div
      className="page-shell"
      data-phase54-admin-route="users"
      data-phase58-route="users"
      data-phase75-admin-users-devices="[FrontendAdmin][phase75][USERS_DEVICES_UNIFIED]"
      data-phase75-single-users-nav="[MobileAdminConsole][phase75][SINGLE_USERS_NAV]"
      data-phase75-responsive="[ResponsiveAdaptation][phase75][UNIFIED_INVENTORY_NO_OVERFLOW]"
      data-phase75-cockpit="[PremiumAdminCockpit][phase75][USERS_INVENTORY_UNIFIED]"
      data-log-marker="[MobileAdminConsole][Phase54][PRIMARY_ACTIONS_REACHABLE]"
    >
      <div className="page-header">
        <div>
          <h1 className="page-title">Пользователи</h1>
          <p className="page-subtitle">Аккаунты и устройства объединены в один компактный список.</p>
        </div>

        <div className="grid gap-2 sm:min-w-[420px]" data-log-marker="[MobileAdminConsole][Phase54][ROUTE_VIEWPORT_SAFE]">
          <div className="metric-strip phase58-signal-strip">
            <div className="metric-strip-item">
              <span className="metric-label">Активные</span>
              <span className="block text-base font-bold">{counters.active}</span>
            </div>
            <div className="metric-strip-item">
              <span className="metric-label">Устройства</span>
              <span className="block text-base font-bold">{devices.length}</span>
            </div>
            <div className="metric-strip-item">
              <span className="metric-label">Блок peers</span>
              <span className="block text-base font-bold">{deviceCounters.blocked}</span>
            </div>
          </div>

          <div className="relative">
            <Search className="input-icon-left" />
            <input
              type="text"
              className="input input-with-icon-left"
              placeholder="Поиск по email или имени"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(1)
              }}
            />
          </div>
        </div>
      </div>

      {feedback ? (
        <div
          className={feedback.tone === 'success' ? 'surface motion-feedback-success px-3 py-2 text-sm text-emerald-100' : 'surface motion-feedback-error px-3 py-2 text-sm text-amber-100'}
          data-phase59-microinteractions="[MatrixMotion][phase59][MICROINTERACTIONS_READY]"
        >
          {feedback.text}
        </div>
      ) : null}

      {isLoading ? (
        <div className="empty-state">
          <UserRound className="h-9 w-9 text-cyan-200" />
          <div>
            <p className="text-base font-semibold">Загружаем список пользователей</p>
            <p className="mt-1 text-sm muted">Тянем страницу и статус аккаунтов из admin API.</p>
          </div>
        </div>
      ) : users.length === 0 ? (
        <div className="empty-state">
          <Search className="h-9 w-9 text-cyan-200" />
          <div>
            <p className="text-base font-semibold">Ничего не найдено</p>
            <p className="mt-1 text-sm muted">Измени поисковый запрос или сбрось фильтр.</p>
          </div>
        </div>
      ) : (
        <div
          className="compact-list bounded-scroll phase58-inventory-list phase58-scroll-rail"
          data-phase58-inventory="[PremiumAdminCockpit][phase58][INVENTORIES_BOUNDED]"
          data-phase75-inventory="[PremiumAdminCockpit][phase75][BOUNDED_EXPANDED_DEVICES]"
        >
          {users.map((user: AdminUser) => {
            const userDevices = devicesByUser[user.id] || []
            const expanded = expandedUserId === user.id
            return (
              <article key={user.id} className="list-row phase75-user-device-row">
                <div className="row-main">
                  <div className="flex min-w-0 items-start gap-3">
                    <button
                      type="button"
                      className="phase75-expand-button"
                      aria-label={expanded ? 'Скрыть устройства пользователя' : 'Показать устройства пользователя'}
                      aria-expanded={expanded}
                      onClick={() => setExpandedUserId(expanded ? null : user.id)}
                      data-phase75-expand="[MatrixMotion][phase75][EXPAND_COLLAPSE_MOTION_SAFE]"
                    >
                      {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    </button>

                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white/10 font-bold text-cyan-100">
                      {user.display_name?.[0] || user.email?.[0] || '?'}
                    </div>
                    <div className="min-w-0">
                      <h2 className="row-title">{user.display_name || 'Без имени'}</h2>
                      <p className="row-subtitle">{user.telegram_username ? `@${user.telegram_username}` : `ID #${user.id}`}</p>
                    </div>
                  </div>

                  <div className="flex shrink-0 flex-wrap justify-end gap-2">
                    <span className="neutral-pill">{userDevices.length} устройств</span>
                    <span className={user.is_active ? 'metric-pill shrink-0' : 'danger-pill shrink-0'}>
                      {user.is_active ? <UserCheck className="h-3.5 w-3.5" /> : <UserX className="h-3.5 w-3.5" />}
                      {user.is_active ? 'Активен' : 'Блок'}
                    </span>
                  </div>
                </div>

                <div className="row-meta">
                  <div className="meta-cell">
                    <span className="meta-label">Email</span>
                    <span className="meta-value">{user.email || '-'}</span>
                  </div>
                  <div className="meta-cell">
                    <span className="meta-label">Роль</span>
                    <span className={roleClass(user.role)}>
                      {user.role === 'superadmin' ? <Shield className="h-3.5 w-3.5" /> : null}
                      {user.role}
                    </span>
                  </div>
                  <div className="meta-cell">
                    <span className="meta-label">Последний вход</span>
                    <span className="meta-value">{formatDate(user.last_login_at)}</span>
                  </div>
                  <div className="meta-cell">
                    <span className="meta-label">Создан</span>
                    <span className="meta-value">{formatDate(user.created_at)}</span>
                  </div>
                </div>

                {expanded ? (
                  <div
                    className="phase75-device-panel"
                    data-phase75-device-rows="[FrontendAdmin][phase75][EXPANDABLE_USER_DEVICE_ROWS]"
                    data-phase75-device-list="[ResponsiveAdaptation][phase75][EXPANDED_DEVICES_BOUNDED]"
                    data-phase75-mobile-actions="[MobileAdminConsole][phase75][DEVICE_ACTIONS_REACHABLE]"
                  >
                    <div className="phase75-device-panel-header">
                      <div>
                        <p className="text-sm font-bold text-white">Устройства пользователя</p>
                        <p className="text-xs muted">Действия применяются только к выбранному device-bound peer.</p>
                      </div>
                      <span className="neutral-pill">{userDevices.length} / {devices.length}</span>
                    </div>

                    {devicesLoading ? (
                      <div className="phase75-device-empty">
                        <ShieldAlert className="h-5 w-5 text-cyan-200" />
                        Загружаем устройства
                      </div>
                    ) : devicesError ? (
                      <div className="phase75-device-empty text-amber-100">
                        <ShieldAlert className="h-5 w-5" />
                        Не удалось загрузить устройства
                      </div>
                    ) : userDevices.length === 0 ? (
                      <div className="phase75-device-empty">У этого пользователя пока нет устройств.</div>
                    ) : (
                      <div
                        className="phase75-device-list phase58-scroll-rail"
                        data-phase75-scroll="[ResponsiveAdaptation][phase75][EXPANDED_DEVICES_BOUNDED]"
                      >
                        {userDevices.map((device) => (
                          <div
                            key={device.id}
                            className="phase75-device-row"
                            data-phase75-device-actions="[DeviceAdminControl][phase75][DEVICE_ACTIONS_IN_USER_EXPANSION]"
                          >
                            <div className="phase75-device-status-row">
                              <div className="min-w-0">
                                <p className="row-title">{device.name}</p>
                                <p className="row-subtitle">{device.platform || 'platform not set'} · config v{device.config_version}</p>
                              </div>
                              <span className={deviceStatusClass(device.status)}>
                                {device.status === 'blocked' ? <Ban className="h-3.5 w-3.5" /> : <ShieldCheck className="h-3.5 w-3.5" />}
                                {device.status}
                              </span>
                            </div>

                            <div className="row-meta">
                              <div className="meta-cell">
                                <span className="meta-label">Endpoint</span>
                                <span className="meta-value">{device.last_endpoint || 'Нет endpoint'}</span>
                              </div>
                              <div className="meta-cell">
                                <span className="meta-label">Handshake</span>
                                <span className="meta-value">{formatDate(device.last_handshake_at, 'Нет данных')}</span>
                              </div>
                              <div className="meta-cell">
                                <span className="meta-label">User</span>
                                <span className="meta-value">{device.user_email || `ID #${device.user_id}`}</span>
                              </div>
                              <div className="meta-cell">
                                <span className="meta-label">Events</span>
                                <span className="meta-value">{(device.recent_event_types ?? []).join(', ') || 'Нет сигналов'}</span>
                              </div>
                            </div>

                            {device.block_reason ? <p className="mt-2 text-xs text-amber-100">reason: {device.block_reason}</p> : null}

                            <div className="phase75-device-action-row">
                              {device.status === 'blocked' ? (
                                <button onClick={() => openAction('unblock', device)} className="btn-secondary">
                                  <ShieldCheck className="h-4 w-4" />
                                  Unblock
                                </button>
                              ) : (
                                <button onClick={() => openAction('block', device)} className="btn-secondary">
                                  <Ban className="h-4 w-4" />
                                  Block
                                </button>
                              )}
                              <button onClick={() => openAction('rotate', device)} className="btn-secondary">
                                <RotateCw className="h-4 w-4" />
                                Rotate
                              </button>
                              <button onClick={() => openAction('revoke', device)} className="btn-danger">
                                <Trash2 className="h-4 w-4" />
                                Revoke
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : null}
              </article>
            )
          })}
        </div>
      )}

      {pages > 1 ? (
        <div className="flex items-center justify-between gap-3">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="btn-secondary"
          >
            Назад
          </button>
          <p className="text-sm muted">
            {page} / {pages}
          </p>
          <button
            onClick={() => setPage((p) => Math.min(pages, p + 1))}
            disabled={page === pages}
            className="btn-secondary"
          >
            Вперёд
          </button>
        </div>
      ) : null}

      {pendingAction ? (
        <div
          className="confirm-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="device-action-title"
          data-log-marker="[MobileAdminConsole][Phase54][CONFIRMATIONS_READABLE] [MobileAdminConsole][phase75][CONFIRMATIONS_READABLE]"
          data-phase58-confirmation="[PremiumAdminCockpit][phase58][CONFIRMATION_GUARDS]"
          data-phase75-confirmation="[DeviceAdminControl][phase75][CONFIRMATION_GUARDS_PRESERVED]"
          data-phase75-audit="[DeviceAdminControl][phase75][AUDIT_CONTRACT_UNCHANGED]"
          data-phase75-pointer="[MatrixMotion][phase75][CONFIRMATION_POINTER_SAFE]"
        >
          <div className="confirm-sheet phase58-confirmation-surface phase75-confirmation-surface">
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
// END_BLOCK: Users
