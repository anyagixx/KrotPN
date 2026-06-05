// FILE: frontend-admin/src/pages/Users.tsx
// VERSION: 1.4.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact Matrix admin users inventory with expandable device management, VPN abuse alert inbox, search, pagination, role/status display, mobile account summary, and Phase-75 unified Users/Devices proof
//   SCOPE: Paginated user list with search, compact rows, role badges, active/blocked status, grouped device rows, confirmation-safe device actions, VPN abuse inbox/archive, bounded scrolling, phone-safe metadata, and dense operator filters
//   DEPENDS: M-010 (frontend-admin), M-006 (admin API), M-024 (device-admin-control), M-037 (mobile-admin-console), M-038 (compact-ui-system), M-071 (matrix-style-system), M-074 (responsive-device-adaptation), M-076 (premium-admin-cockpit), M-077 (matrix-motion-interactions), M-081 (VPN device abuse alert inbox)
//   LINKS: M-010, M-006, M-024, M-037, M-038, M-071, M-074, M-076, M-077, M-081, Phase-54, Phase-58, Phase-59, Phase-75, Phase-78
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   UsersPage - Main compact admin users page component with VPN abuse alert inbox and expandable per-user device management
//   actionCopy - Labels and descriptions for confirmation-safe device actions
//   formatDate - Helper: format date to ru-RU locale string
//   roleClass - Helper: choose role badge class
//   deviceStatusClass - Helper: choose device status badge class
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v3.3.0 - Phase-78 added VPN device abuse alert inbox/archive with explicit one-device actions.
//   LAST_CHANGE: v3.2.0 - Phase-75 unified Users and Devices into expandable user inventory with preserved device actions and confirmation guards.
//   LAST_CHANGE: v3.1.0 - Phase-58 added premium bounded inventory markers and denser user search frame.
//   LAST_CHANGE: v3.0.0 - Phase-54 added Matrix route markers and bounded compact inventory behavior for large user sets.
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.9.0 - Phase-24 compact mobile user search rows without table-only dependency
// END_CHANGE_SUMMARY

import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import {
  AlertTriangle,
  Archive,
  Ban,
  ChevronDown,
  ChevronRight,
  Eye,
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
import type { AdminDevice, AdminUser, AdminVPNDeviceAbuseAlert, PaginatedResponse } from '../types'

type DeviceAction = 'block' | 'unblock' | 'rotate' | 'revoke'
type VPNAbuseAlertAction = 'resolve' | 'rotate' | 'block'

interface PendingAction {
  type: DeviceAction
  device: AdminDevice
}

interface PendingVPNAbuseAlertAction {
  type: VPNAbuseAlertAction
  alert: AdminVPNDeviceAbuseAlert
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

// START_BLOCK: vpnAbuseAlertActionCopy
// Action labels and confirmation copy for Phase-78 VPN abuse alert decisions
// DEPENDS: VPNAbuseAlertAction union
const vpnAbuseAlertActionCopy: Record<VPNAbuseAlertAction, { label: string; title: string; description: string; tone: 'danger' | 'normal' }> = {
  resolve: {
    label: 'Закрыть alert',
    title: 'Закрыть VPN abuse alert',
    description: 'Alert уйдет в архив. Устройство, конфиг и аккаунт пользователя не изменятся.',
    tone: 'normal',
  },
  rotate: {
    label: 'Ротировать конфиг',
    title: 'Ротировать конфиг устройства',
    description: 'Будет перевыпущен только конфиг выбранного устройства. Другие устройства пользователя не меняются.',
    tone: 'normal',
  },
  block: {
    label: 'Заблокировать устройство',
    title: 'Заблокировать устройство',
    description: 'Будет заблокировано только устройство из этого alert. Аккаунт пользователя и остальные устройства не блокируются.',
    tone: 'danger',
  },
}
// END_BLOCK: vpnAbuseAlertActionCopy

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
  const [selectedVPNAlert, setSelectedVPNAlert] = useState<AdminVPNDeviceAbuseAlert | null>(null)
  const [pendingVPNAlertAction, setPendingVPNAlertAction] = useState<PendingVPNAbuseAlertAction | null>(null)
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

  const {
    data: vpnAbuseOpenData,
    isLoading: vpnAbuseOpenLoading,
  } = useQuery(
    ['admin-vpn-device-abuse-alerts', 'open'],
    () => adminApi.getVPNDeviceAbuseAlerts('open', 20),
    { keepPreviousData: true, refetchInterval: 15000 }
  )

  const {
    data: vpnAbuseArchiveData,
  } = useQuery(
    ['admin-vpn-device-abuse-alerts', 'resolved'],
    () => adminApi.getVPNDeviceAbuseAlerts('resolved', 20),
    { keepPreviousData: true }
  )

  const users = data?.data?.items || []
  const total = data?.data?.total || 0
  const pages = data?.data?.pages || 1
  const devices = devicesData?.data?.items || []
  const vpnAbuseOpenAlerts = vpnAbuseOpenData?.data?.items || []
  const vpnAbuseArchivedAlerts = vpnAbuseArchiveData?.data?.items || []
  const vpnAbuseOpenCount = vpnAbuseOpenData?.data?.open_count || 0
  const vpnAbuseResolvedCount = vpnAbuseOpenData?.data?.resolved_count ?? vpnAbuseArchiveData?.data?.resolved_count ?? 0

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

  const refreshVPNAbuseInbox = (message: string) => ({
    onSuccess: () => {
      void queryClient.invalidateQueries('admin-vpn-device-abuse-alerts')
      void queryClient.invalidateQueries('admin-devices')
      setFeedback({ tone: 'success', text: message })
      setPendingVPNAlertAction(null)
      setSelectedVPNAlert(null)
    },
    onError: (error: unknown) => {
      setFeedback({
        tone: 'error',
        text: (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Alert-действие не выполнено',
      })
    },
  })

  const resolveVPNAlertMutation = useMutation((id: number) => adminApi.resolveVPNDeviceAbuseAlert(id), refreshVPNAbuseInbox('Alert закрыт и перенесен в архив'))
  const rotateVPNAlertMutation = useMutation((id: number) => adminApi.rotateVPNDeviceAbuseAlert(id), refreshVPNAbuseInbox('Конфиг устройства перевыпущен, alert закрыт'))
  const blockVPNAlertMutation = useMutation((id: number) => adminApi.blockVPNDeviceAbuseAlert(id), refreshVPNAbuseInbox('Устройство заблокировано, alert закрыт'))
  const isVPNAlertMutating = resolveVPNAlertMutation.isLoading || rotateVPNAlertMutation.isLoading || blockVPNAlertMutation.isLoading

  const openAction = (type: DeviceAction, device: AdminDevice) => {
    setFeedback(null)
    setPendingAction({ type, device })
  }

  const openVPNAlertAction = (type: VPNAbuseAlertAction, alert: AdminVPNDeviceAbuseAlert) => {
    setFeedback(null)
    setPendingVPNAlertAction({ type, alert })
  }

  const runConfirmedAction = () => {
    if (!pendingAction) return
    const id = pendingAction.device.id

    if (pendingAction.type === 'block') blockMutation.mutate(id)
    if (pendingAction.type === 'unblock') unblockMutation.mutate(id)
    if (pendingAction.type === 'rotate') rotateMutation.mutate(id)
    if (pendingAction.type === 'revoke') revokeMutation.mutate(id)
  }

  const runConfirmedVPNAlertAction = () => {
    if (!pendingVPNAlertAction) return
    const id = pendingVPNAlertAction.alert.id

    if (pendingVPNAlertAction.type === 'resolve') resolveVPNAlertMutation.mutate(id)
    if (pendingVPNAlertAction.type === 'rotate') rotateVPNAlertMutation.mutate(id)
    if (pendingVPNAlertAction.type === 'block') blockVPNAlertMutation.mutate(id)
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

      <section
        className="surface grid gap-4 p-4"
        data-phase78-vpn-abuse="[FrontendAdmin][phase78][VPN_DEVICE_ABUSE_ALERT_INBOX]"
        data-phase78-vpn-abuse-archive="[FrontendAdmin][phase78][VPN_DEVICE_ABUSE_ALERT_ARCHIVE]"
        data-phase78-vpn-abuse-actions="[DeviceAdminControl][phase78][ONE_DEVICE_ALERT_ACTIONS]"
      >
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-200" />
              <h2 className="text-base font-bold text-white">VPN Abuse alerts</h2>
              <span className={vpnAbuseOpenCount > 0 ? 'danger-pill' : 'metric-pill'}>{vpnAbuseOpenCount} открыто</span>
              <span className="neutral-pill">
                <Archive className="h-3.5 w-3.5" />
                {vpnAbuseResolvedCount} архив
              </span>
            </div>
            <p className="mt-1 text-xs muted">
              Только подтвержденные ping-pong и multi-network сигналы. Автоблокировок нет.
            </p>
          </div>
          <div className="text-xs muted">
            Автообновление: 15 сек
          </div>
        </div>

        <div className="grid gap-3 xl:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.8fr)]">
          <div className="grid gap-2">
            {vpnAbuseOpenLoading ? (
              <div className="phase75-device-empty">
                <ShieldAlert className="h-5 w-5 text-cyan-200" />
                Загружаем VPN alerts
              </div>
            ) : vpnAbuseOpenAlerts.length === 0 ? (
              <div className="phase75-device-empty">
                <ShieldCheck className="h-5 w-5 text-emerald-200" />
                Открытых VPN abuse alerts нет
              </div>
            ) : (
              <div className="phase75-device-list phase58-scroll-rail max-h-[280px]">
                {vpnAbuseOpenAlerts.map((alert) => (
                  <article key={alert.id} className="phase75-device-row" data-phase78-alert-row="[M-081][ALERT_ROW]">
                    <div className="phase75-device-status-row">
                      <div className="min-w-0">
                        <p className="row-title">{alert.user_email || `User #${alert.user_id}`}</p>
                        <p className="row-subtitle">
                          {alert.device_name || `Device #${alert.device_id}`} · {alert.signal_type} · x{alert.occurrence_count}
                        </p>
                      </div>
                      <span className="danger-pill shrink-0">{alert.severity}</span>
                    </div>

                    <div className="row-meta">
                      <div className="meta-cell">
                        <span className="meta-label">Device</span>
                        <span className="meta-value">#{alert.device_id} · v{alert.config_version}</span>
                      </div>
                      <div className="meta-cell">
                        <span className="meta-label">Endpoint</span>
                        <span className="meta-value">{alert.last_endpoint || 'Нет endpoint'}</span>
                      </div>
                      <div className="meta-cell">
                        <span className="meta-label">Last seen</span>
                        <span className="meta-value">{formatDate(alert.last_seen_at, 'Нет данных')}</span>
                      </div>
                    </div>

                    <div className="phase75-device-action-row">
                      <button onClick={() => setSelectedVPNAlert(alert)} className="btn-secondary">
                        <Eye className="h-4 w-4" />
                        Посмотреть
                      </button>
                      <button onClick={() => openVPNAlertAction('resolve', alert)} className="btn-secondary">
                        <ShieldCheck className="h-4 w-4" />
                        Закрыть
                      </button>
                      <button onClick={() => openVPNAlertAction('rotate', alert)} className="btn-secondary">
                        <RotateCw className="h-4 w-4" />
                        Ротировать
                      </button>
                      <button onClick={() => openVPNAlertAction('block', alert)} className="btn-danger">
                        <Ban className="h-4 w-4" />
                        Блок
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>

          <aside className="phase75-device-row min-h-[180px]" data-phase78-alert-detail="[M-081][ALERT_DETAIL_DRAWER]">
            {selectedVPNAlert ? (
              <div className="grid gap-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-bold text-white">{selectedVPNAlert.title}</p>
                    <p className="text-xs muted">Alert #{selectedVPNAlert.id} · source event #{selectedVPNAlert.source_event_id || '-'}</p>
                  </div>
                  <button className="btn-secondary px-2" onClick={() => setSelectedVPNAlert(null)} aria-label="Закрыть VPN alert detail">
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <div className="row-meta">
                  <div className="meta-cell">
                    <span className="meta-label">User</span>
                    <span className="meta-value">{selectedVPNAlert.user_email || `ID #${selectedVPNAlert.user_id}`}</span>
                  </div>
                  <div className="meta-cell">
                    <span className="meta-label">Device</span>
                    <span className="meta-value">{selectedVPNAlert.device_name || `ID #${selectedVPNAlert.device_id}`}</span>
                  </div>
                  <div className="meta-cell">
                    <span className="meta-label">Handshake</span>
                    <span className="meta-value">{formatDate(selectedVPNAlert.last_handshake_at, 'Нет данных')}</span>
                  </div>
                  <div className="meta-cell">
                    <span className="meta-label">Статус</span>
                    <span className="meta-value">{selectedVPNAlert.device_status || selectedVPNAlert.status}</span>
                  </div>
                </div>
                <p className="text-xs muted">
                  Действия ниже затрагивают только устройство #{selectedVPNAlert.device_id}.
                </p>
                <div className="phase75-device-action-row">
                  <button onClick={() => openVPNAlertAction('resolve', selectedVPNAlert)} className="btn-secondary">Закрыть alert</button>
                  <button onClick={() => openVPNAlertAction('rotate', selectedVPNAlert)} className="btn-secondary">Ротировать</button>
                  <button onClick={() => openVPNAlertAction('block', selectedVPNAlert)} className="btn-danger">Заблокировать</button>
                </div>
              </div>
            ) : (
              <div className="grid h-full place-items-center text-center text-sm muted">
                Выбери alert, чтобы увидеть устройство и безопасные действия.
              </div>
            )}
          </aside>
        </div>

        {vpnAbuseArchivedAlerts.length > 0 ? (
          <details className="rounded-lg border border-white/10 bg-white/5 p-3">
            <summary className="cursor-pointer text-sm font-semibold text-white">Архив VPN alerts</summary>
            <div className="mt-3 grid gap-2">
              {vpnAbuseArchivedAlerts.slice(0, 8).map((alert) => (
                <div key={alert.id} className="flex flex-col gap-1 rounded-lg bg-black/20 p-2 text-xs sm:flex-row sm:items-center sm:justify-between">
                  <span className="text-white">{alert.user_email || `User #${alert.user_id}`} · {alert.device_name || `Device #${alert.device_id}`}</span>
                  <span className="muted">{alert.action_taken || 'reviewed'} · {formatDate(alert.resolved_at, 'Архив')}</span>
                </div>
              ))}
            </div>
          </details>
        ) : null}
      </section>

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

      {pendingVPNAlertAction ? (
        <div
          className="confirm-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="vpn-alert-action-title"
          data-phase78-confirmation="[DeviceAdminControl][phase78][VPN_ALERT_CONFIRMATION_GUARDS]"
          data-phase78-alert-action-scope="[DeviceAdminControl][phase78][ONE_DEVICE_ONLY]"
        >
          <div className="confirm-sheet phase58-confirmation-surface phase75-confirmation-surface">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p id="vpn-alert-action-title" className="text-lg font-bold text-white">
                  {vpnAbuseAlertActionCopy[pendingVPNAlertAction.type].title}
                </p>
                <p className="mt-2 text-sm muted">{vpnAbuseAlertActionCopy[pendingVPNAlertAction.type].description}</p>
              </div>
              <button onClick={() => setPendingVPNAlertAction(null)} className="btn-secondary px-2" aria-label="Закрыть подтверждение VPN alert">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 grid gap-2 rounded-lg border border-white/10 bg-white/5 p-3 text-sm">
              <div>
                <span className="meta-label">Alert</span>
                <span className="meta-value">#{pendingVPNAlertAction.alert.id} · {pendingVPNAlertAction.alert.signal_type}</span>
              </div>
              <div>
                <span className="meta-label">User</span>
                <span className="meta-value">{pendingVPNAlertAction.alert.user_email || `ID #${pendingVPNAlertAction.alert.user_id}`}</span>
              </div>
              <div>
                <span className="meta-label">Device scope</span>
                <span className="meta-value">Только device #{pendingVPNAlertAction.alert.device_id}</span>
              </div>
            </div>

            <div className="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button onClick={() => setPendingVPNAlertAction(null)} disabled={isVPNAlertMutating} className="btn-secondary">
                Отмена
              </button>
              <button
                onClick={runConfirmedVPNAlertAction}
                disabled={isVPNAlertMutating}
                className={vpnAbuseAlertActionCopy[pendingVPNAlertAction.type].tone === 'danger' ? 'btn-danger' : 'btn-primary'}
              >
                {isVPNAlertMutating ? 'Выполняю...' : vpnAbuseAlertActionCopy[pendingVPNAlertAction.type].label}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
// END_BLOCK: Users
