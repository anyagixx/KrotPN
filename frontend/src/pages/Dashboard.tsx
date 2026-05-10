// FILE: frontend/src/pages/Dashboard.tsx
// VERSION: 1.1.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact mobile-first dashboard showing VPN status, config action, subscription, traffic, and device summary
//   SCOPE: Mobile home workflow, primary config/subscription CTA, active device summary, compact traffic and connection facts
//   DEPENDS: M-009 (frontend-user), M-002 (auth API), M-003 (vpn stats API), M-004 (billing API), M-022 (device API), M-036 (mobile-user-cabinet)
//   LINKS: M-009 (frontend-user), M-036 (mobile-user-cabinet)
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   DashboardPage - Compact dashboard component with mobile-first primary actions and device summary
//   BLOCK_DASHBOARD_PAGE - DashboardPage default export with VPN, subscription, config, and device surfaces
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.9.0 - Reworked dashboard into compact Phase-23 mobile home workflow
// END_CHANGE_SUMMARY
//
// START_BLOCK_DASHBOARD_PAGE
import { useQuery } from 'react-query'
import { useTranslation } from 'react-i18next'
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Calendar,
  Clock,
  FileCode2,
  QrCode,
  Server,
  Shield,
  Smartphone,
  Zap,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuthStore } from '../stores/auth'
import { deviceApi, userApi, vpnApi } from '../lib/api'
import Loading from '../components/Loading'

export default function Dashboard() {
  const { t } = useTranslation()
  const { user } = useAuthStore()

  const { data: vpnStats, isLoading: statsLoading, isError: statsError } = useQuery('vpn-stats', () => vpnApi.getStats(), {
    refetchInterval: 10000,
  })

  const { data: userStats, isLoading: userStatsLoading, isError: userStatsError } = useQuery('user-stats', () => userApi.getStats())
  const { data: devicesData, isLoading: devicesLoading, isError: devicesError } = useQuery('dashboard-devices', () => deviceApi.list(), {
    retry: false,
  })

  if (statsLoading || userStatsLoading) {
    return <Loading text={t('loading')} />
  }

  if (statsError || userStatsError) {
    return (
      <div className="empty-state">
        <AlertTriangle className="h-10 w-10 text-red-200" />
        <div>
          <p className="text-lg font-semibold">Не удалось загрузить сводку</p>
          <p className="mt-1 text-sm muted">Проверь доступность backend или обнови страницу позже.</p>
        </div>
      </div>
    )
  }

  const stats = vpnStats?.data
  const uStats = userStats?.data
  const isConnected = !!stats?.is_connected
  const hasSubscription = !!uStats?.has_active_subscription
  const deviceList = devicesData?.data?.devices || []
  const activeDevices = deviceList.filter((device) => device.status === 'active').length
  const consumedSlots = devicesData?.data?.consumed_slots || activeDevices
  const deviceLimit = devicesData?.data?.device_limit || 0
  const lastHandshake = stats?.last_handshake_at ? new Date(stats.last_handshake_at).toLocaleString('ru-RU') : 'Нет данных'

  return (
    <div className="content-section animate-in">
      <section className="grid gap-3 lg:grid-cols-[minmax(0,1.25fr)_minmax(260px,0.75fr)]">
        <article className="panel p-4 sm:p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-bold uppercase text-cyan-100/70">VPN доступ</p>
              <h1 className="mt-1 truncate text-2xl font-extrabold text-white sm:text-3xl">
                {user?.display_name || user?.email || 'Личный кабинет'}
              </h1>
              <p className="mt-2 text-sm muted">
                {hasSubscription
                  ? 'Конфиг, QR и устройства доступны из главного действия.'
                  : 'Активируйте подписку, чтобы получить рабочий конфиг.'}
              </p>
            </div>
            <span className={isConnected ? 'status-badge-success w-fit' : 'status-badge-warning w-fit'}>
              {isConnected ? t('connected') : t('disconnected')}
            </span>
          </div>

          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            <Link to={hasSubscription ? '/config' : '/subscription'} className="btn-primary min-h-12 justify-start rounded-xl px-3 py-3">
              {hasSubscription ? <QrCode className="h-5 w-5" /> : <Zap className="h-5 w-5" />}
              {hasSubscription ? 'QR и .conf' : 'Активировать'}
            </Link>
            <Link to="/config" className="btn-secondary min-h-12 justify-start rounded-xl px-3 py-3">
              <FileCode2 className="h-5 w-5" />
              Устройства
            </Link>
          </div>
        </article>

        <article className="panel p-4 sm:p-5">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-bold uppercase text-cyan-100/70">Подписка</p>
              <p className="mt-1 truncate text-xl font-extrabold">
                {hasSubscription ? `${uStats?.subscription_days_left || 0} ${t('daysLeft')}` : 'Нужна оплата'}
              </p>
            </div>
            <Calendar className="h-5 w-5 shrink-0 text-cyan-100" />
          </div>
          <Link to="/subscription" className={hasSubscription ? 'btn-secondary mt-4 min-h-11 w-full rounded-xl px-3 py-2.5' : 'btn-primary mt-4 min-h-11 w-full rounded-xl px-3 py-2.5'}>
            {hasSubscription ? 'Продлить' : 'Выбрать тариф'}
          </Link>
        </article>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <article className="metric-card">
          <div className="flex items-center gap-3">
            <Shield className="h-5 w-5 shrink-0 text-emerald-200" />
            <div className="min-w-0">
              <p className="metric-label">{t('status')}</p>
              <p className="truncate font-bold">{isConnected ? t('connected') : t('disconnected')}</p>
            </div>
          </div>
        </article>

        <article className="metric-card">
          <div className="flex items-center gap-3">
            <Smartphone className="h-5 w-5 shrink-0 text-cyan-100" />
            <div className="min-w-0">
              <p className="metric-label">Устройства</p>
              <p className="truncate font-bold">
                {devicesLoading ? 'Загрузка' : devicesError ? 'Недоступно' : `${consumedSlots}/${deviceLimit || '∞'}`}
              </p>
            </div>
          </div>
        </article>

        <article className="metric-card">
          <div className="flex items-center gap-3">
            <ArrowUp className="h-5 w-5 shrink-0 text-emerald-200" />
            <div className="min-w-0">
              <p className="metric-label">{t('upload')}</p>
              <p className="truncate font-bold">{stats?.total_upload_formatted || '0 B'}</p>
            </div>
          </div>
        </article>

        <article className="metric-card">
          <div className="flex items-center gap-3">
            <ArrowDown className="h-5 w-5 shrink-0 text-cyan-100" />
            <div className="min-w-0">
              <p className="metric-label">{t('download')}</p>
              <p className="truncate font-bold">{stats?.total_download_formatted || '0 B'}</p>
            </div>
          </div>
        </article>
      </section>

      <section className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <article className="panel p-4 sm:p-5">
          <div className="flex items-start gap-3">
            <Server className="mt-1 h-5 w-5 shrink-0 text-cyan-100" />
            <div className="min-w-0">
              <h2 className="text-lg font-bold">Сервер и соединение</h2>
              <p className="mt-1 truncate text-sm muted">{isConnected ? stats?.server_name || 'Connected' : 'Ожидает активации'}</p>
              <div className="mt-3 flex items-start gap-3 text-sm text-slate-100">
                <Clock className="mt-0.5 h-4 w-4 shrink-0 text-cyan-100" />
                <span className="min-w-0 break-words">{lastHandshake}</span>
              </div>
            </div>
          </div>
        </article>

        <article className="panel p-4 sm:p-5">
          <div className="flex items-start gap-3">
            <Smartphone className="mt-1 h-5 w-5 shrink-0 text-cyan-100" />
            <div className="min-w-0 flex-1">
              <h2 className="text-lg font-bold">Device-bound конфиги</h2>
              <p className="mt-1 text-sm muted">
                {devicesError
                  ? 'Список устройств временно недоступен.'
                  : activeDevices
                    ? `${activeDevices} активных устройств. QR и .conf открываются в разделе конфигурации.`
                    : 'Создайте первое устройство, чтобы получить отдельный peer и конфиг.'}
              </p>
              <Link to="/config" className="btn-secondary mt-4 min-h-11 w-full justify-start rounded-xl px-3 py-2.5">
                <FileCode2 className="h-5 w-5" />
                Открыть конфигурацию
              </Link>
            </div>
          </div>
        </article>
      </section>

      {!hasSubscription ? (
        <section className="panel p-4 sm:p-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <h2 className="text-lg font-bold">Подписка нужна для рабочего конфига</h2>
              <p className="mt-1 text-sm muted">После оплаты появятся QR-код, `.conf` и управление устройствами.</p>
            </div>
            <Link to="/subscription" className="btn-primary min-h-11 shrink-0 rounded-xl px-3 py-2.5">
              <Zap className="h-5 w-5" />
              Выбрать тариф
            </Link>
          </div>
        </section>
      ) : null}
    </div>
  )
}
// END_BLOCK_DASHBOARD_PAGE
