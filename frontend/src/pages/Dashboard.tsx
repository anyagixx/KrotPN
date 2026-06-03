// FILE: frontend/src/pages/Dashboard.tsx
// VERSION: 1.6.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Premium compact Matrix command center showing VPN status, config action, subscription, MTProto proxy, traffic, device summary, and Phase-59 feedback
//   SCOPE: Mobile first-screen workflow, primary config/subscription CTA, MTProto owner actions, active device summary, compact traffic and connection facts, copy microinteractions, and status transitions
//   DEPENDS: M-009 (frontend-user), M-002 (auth API), M-003 (vpn stats API), M-004 (billing API), M-022 (device API), M-036 (mobile-user-cabinet), M-045 (mtproto-user-cabinet), M-051 (mtproto-availability-diagnostics), M-071 (matrix-style-system), M-075 (premium-user-cabinet), M-077 (matrix-motion-interactions)
//   LINKS: M-009 (frontend-user), M-036 (mobile-user-cabinet), M-045, M-051, M-071, M-075, M-077, Phase-59
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   DashboardPage - Premium command dashboard component with mobile-first primary actions, MTProto owner card, and device summary
//   buildMtprotoTelegramAppLink - Builds tg://proxy action link from the owner payload for Telegram app opening
//   buildMtprotoBrowserLink - Builds https://t.me/proxy browser/copy link from the owner payload
//   mtprotoIntroText - Builds a non-duplicating MTProto card intro line
//   BLOCK_DASHBOARD_PAGE - DashboardPage default export with Phase-57 VPN, subscription, MTProto, config, device command surfaces, and Phase-59 feedback markers
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v3.6.0 - Added Phase-59 MTProto copy feedback, status transition markers, and motion-safe action classes.
//   LAST_CHANGE: v3.5.0 - Added Phase-57 premium command center, one/two-tap protected route actions, and dense first-screen task strip.
//   LAST_CHANGE: v3.4.0 - Applied Phase-53 compact Matrix dashboard surfaces without changing API refresh contracts.
//   LAST_CHANGE: v3.3.0 - Added Phase-46 MTProto tg/browser link split, Russian labels, and bounded status refresh marker.
//   LAST_CHANGE: v3.2.0 - Added Phase-45 pending trial state and subscription countdown summary.
//   LAST_CHANGE: v3.1.1 - Avoid rendering pending/degraded MTProto safe_message twice in the dashboard card.
//   LAST_CHANGE: v3.1.0 - Added Phase-39 primary Telegram web-link action and full-link copy flow
//   LAST_CHANGE: v3.0.0 - Added Phase-31 compact MTProto proxy owner card
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.9.0 - Reworked dashboard into compact Phase-23 mobile home workflow
// END_CHANGE_SUMMARY
//
// START_BLOCK_DASHBOARD_PAGE
import { useEffect, useState } from 'react'
import { useQuery } from 'react-query'
import { useTranslation } from 'react-i18next'
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Calendar,
  Check,
  Clock,
  Copy,
  ExternalLink,
  FileCode2,
  KeyRound,
  Link2,
  QrCode,
  Server,
  Shield,
  Smartphone,
  Zap,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import { useAuthStore } from '../stores/auth'
import { billingApi, deviceApi, mtprotoApi, MTProtoProxyResponse, SubscriptionStatus, vpnApi } from '../lib/api'
import Loading from '../components/Loading'

const MTPROTO_CARD_RENDER_MARKER = '[M-045][dashboard_mtproto_card][CARD_RENDER]'
const MTPROTO_COPY_ACTION_MARKER = '[M-045][dashboard_mtproto_card][COPY_ACTION]'
const MTPROTO_OPEN_TELEGRAM_MARKER = '[M-045][dashboard_mtproto_card][OPEN_TELEGRAM]'
const MTPROTO_STATUS_REFRESH_MS = 30000

type MTProtoCopyField = 'link' | 'server' | 'port' | 'secret'

function hasOwnerProxy(payload?: MTProtoProxyResponse): payload is MTProtoProxyResponse & {
  server: string
  port: number
  secret: string
  tg_link: string
} {
  return payload?.status === 'activated' && !!payload.server && !!payload.port && !!payload.secret && !!payload.tg_link
}

function mtprotoStatusLabel(payload?: MTProtoProxyResponse, isLoading?: boolean, isError?: boolean) {
  if (isLoading) return 'Загрузка'
  if (isError) return 'Недоступно'
  if (!payload) return 'Ожидание'
  if (payload.status === 'activated') return 'Готов'
  if (payload.status === 'unverified') return 'Email'
  if (payload.status === 'reissue_required') return 'Перевыпуск'
  if (payload.status === 'pending') return 'Готовится'
  return 'Сбой'
}

function mtprotoStatusClass(payload?: MTProtoProxyResponse, isLoading?: boolean, isError?: boolean) {
  if (isLoading || payload?.status === 'pending') return 'status-badge-warning motion-status w-fit'
  if (isError || payload?.status === 'degraded' || payload?.status === 'reissue_required') return 'status-badge-error motion-status w-fit'
  if (payload?.status === 'activated') return 'status-badge-success motion-status w-fit'
  return 'status-badge-warning motion-status w-fit'
}

function buildMtprotoTelegramAppLink(payload?: MTProtoProxyResponse) {
  if (!hasOwnerProxy(payload)) return null

  const params = new URLSearchParams({
    server: payload.server,
    port: String(payload.port),
    secret: payload.secret,
  })
  return `tg://proxy?${params.toString()}`
}

function buildMtprotoBrowserLink(payload?: MTProtoProxyResponse) {
  if (!hasOwnerProxy(payload)) return null

  const params = new URLSearchParams({
    server: payload.server,
    port: String(payload.port),
    secret: payload.secret,
  })
  return `https://t.me/proxy?${params.toString()}`
}

function mtprotoIntroText(payload?: MTProtoProxyResponse, isLoading?: boolean, isError?: boolean) {
  if (isLoading) return 'Проверяем выданный proxy.'
  if (isError) return 'Telegram proxy временно недоступен, VPN действия остаются на месте.'
  if (payload?.status === 'activated') return 'Индивидуальный Telegram proxy готов к использованию.'
  if (payload?.status) return 'Состояние Telegram proxy отображается ниже.'
  return 'Proxy будет доступен после подготовки.'
}

function formatSubscriptionRemaining(subscription?: SubscriptionStatus) {
  if (!subscription?.has_subscription) return 'Нужна оплата'
  if (subscription.pending_activation) return 'Старт после VPN'
  if (!subscription.is_active) return 'Истекла'
  return `${subscription.remaining_days}д ${subscription.remaining_hours}ч ${subscription.remaining_minutes}м`
}

function subscriptionHint(subscription?: SubscriptionStatus) {
  if (!subscription?.has_subscription) return 'Выберите тариф, чтобы получить рабочий конфиг.'
  if (subscription.pending_activation) return 'Trial на 4 дня начнется после первого успешного VPN подключения.'
  if (subscription.is_active) return 'Оставшееся время рассчитано backend по серверному времени.'
  return 'Доступ закончился, продлите подписку для нового конфига.'
}

export default function Dashboard() {
  const { t } = useTranslation()
  const { user } = useAuthStore()
  const [copiedMtprotoField, setCopiedMtprotoField] = useState<MTProtoCopyField | null>(null)

  const { data: vpnStats, isLoading: statsLoading, isError: statsError } = useQuery('vpn-stats', () => vpnApi.getStats(), {
    refetchInterval: 10000,
  })

  const { data: subscriptionData, isLoading: subscriptionLoading, isError: subscriptionError } = useQuery(
    'dashboard-subscription',
    () => billingApi.getSubscription(),
    {
      refetchInterval: 30000,
    }
  )
  const { data: devicesData, isLoading: devicesLoading, isError: devicesError } = useQuery('dashboard-devices', () => deviceApi.list(), {
    retry: false,
  })
  const { data: mtprotoProxy, isLoading: mtprotoLoading, isError: mtprotoError } = useQuery(
    'mtproto-proxy',
    () => mtprotoApi.getProxy(),
    {
      retry: false,
      refetchInterval: MTPROTO_STATUS_REFRESH_MS,
      refetchIntervalInBackground: false,
      staleTime: 10000,
    }
  )

  const mtproto = mtprotoProxy?.data

  useEffect(() => {
    if (mtproto?.status) {
      console.info(MTPROTO_CARD_RENDER_MARKER, { status: mtproto.status })
    }
  }, [mtproto?.status])

  if (statsLoading || subscriptionLoading) {
    return <Loading text={t('loading')} />
  }

  if (statsError || subscriptionError) {
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
  const subscription = subscriptionData?.data
  const isConnected = !!stats?.is_connected
  const hasSubscription = !!subscription?.has_subscription && (subscription.is_active || subscription.pending_activation)
  const subscriptionPending = !!subscription?.pending_activation
  const deviceList = devicesData?.data?.devices || []
  const activeDevices = deviceList.filter((device) => device.status === 'active').length
  const consumedSlots = devicesData?.data?.consumed_slots || activeDevices
  const deviceLimit = devicesData?.data?.device_limit || 0
  const lastHandshake = stats?.last_handshake_at ? new Date(stats.last_handshake_at).toLocaleString('ru-RU') : 'Нет данных'
  const mtprotoReady = hasOwnerProxy(mtproto)
  const mtprotoTelegramAppLink = buildMtprotoTelegramAppLink(mtproto)
  const mtprotoBrowserLink = buildMtprotoBrowserLink(mtproto)

  const handleMtprotoCopy = async (field: MTProtoCopyField, value?: string | number | null) => {
    if (value === null || value === undefined || value === '') {
      toast.error('Данные Telegram proxy пока недоступны')
      return
    }

    await navigator.clipboard.writeText(String(value))
    setCopiedMtprotoField(field)
    console.info(MTPROTO_COPY_ACTION_MARKER, { field })
    toast.success(t('copied'))
    window.setTimeout(() => setCopiedMtprotoField(null), 1600)
  }

  const renderMtprotoCopyButton = (field: MTProtoCopyField, label: string, value?: string | number | null) => (
    <button
      type="button"
      onClick={() => handleMtprotoCopy(field, value)}
      className={copiedMtprotoField === field ? 'btn-secondary motion-interactive motion-copy-success min-h-10 min-w-0 rounded-lg px-2 py-2 text-sm' : 'btn-secondary motion-interactive min-h-10 min-w-0 rounded-lg px-2 py-2 text-sm'}
      aria-label={`Copy MTProto ${field}`}
      title={`Copy MTProto ${field}`}
      disabled={!value}
    >
      {copiedMtprotoField === field ? <Check className="h-4 w-4 text-emerald-200" /> : <Copy className="h-4 w-4" />}
      <span className="truncate">{label}</span>
    </button>
  )

  return (
    <div
      className="content-section matrix-page animate-in"
      data-phase53-route="dashboard"
      data-phase57-route="dashboard"
      data-phase59-status-transitions="[MatrixMotion][phase59][STATUS_TRANSITIONS_READY]"
    >
      <section
        className="phase57-command-center"
        data-phase57-command-center="true"
        data-phase57-first-screen-tasks="vpn subscription mtproto devices"
      >
        <div className="phase57-command-header">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase text-cyan-100/70">VPN доступ</p>
            <h1 className="mt-1 truncate text-2xl font-extrabold text-white">
              {user?.display_name || user?.email || 'Личный кабинет'}
            </h1>
            <p className="mt-2 text-sm muted">
              {hasSubscription
                ? subscriptionPending
                  ? 'Скачайте конфиг: trial начнется после первого VPN подключения.'
                  : 'Конфиг, QR, устройства и Telegram proxy доступны на первом экране.'
                : 'Активируйте подписку, чтобы получить рабочий конфиг.'}
            </p>
          </div>
          <span className={isConnected ? 'status-badge-success motion-status w-fit shrink-0' : 'status-badge-warning motion-status w-fit shrink-0'}>
            {isConnected ? t('connected') : t('disconnected')}
          </span>
        </div>

        <div className="phase57-signal-strip mt-3" data-phase57-dashboard-signal-strip="true">
          <div className="phase57-signal-tile" data-phase57-task="vpn">
            <p className="metric-label">VPN</p>
            <p className="mt-1 truncate font-bold">{isConnected ? stats?.server_name || 'online' : 'ожидает'}</p>
          </div>
          <div className="phase57-signal-tile" data-phase57-task="subscription">
            <p className="metric-label">Подписка</p>
            <p className="mt-1 truncate font-bold">{formatSubscriptionRemaining(subscription)}</p>
          </div>
          <div className="phase57-signal-tile" data-phase57-task="mtproto">
            <p className="metric-label">MTProto</p>
            <p className="mt-1 truncate font-bold">{mtprotoStatusLabel(mtproto, mtprotoLoading, mtprotoError)}</p>
          </div>
          <div className="phase57-signal-tile" data-phase57-task="devices">
            <p className="metric-label">Устройства</p>
            <p className="mt-1 truncate font-bold">
              {devicesLoading ? 'Загрузка' : devicesError ? 'Недоступно' : `${consumedSlots}/${deviceLimit || '∞'}`}
            </p>
          </div>
        </div>

        <div className="phase57-primary-actions mt-3" data-phase57-primary-actions-reachable="true">
          <Link
            to={hasSubscription ? '/dashboard/config' : '/dashboard/subscription'}
            className="btn-primary motion-interactive min-h-11 justify-start rounded-lg px-3 py-2.5"
            data-phase57-primary-action="vpn-config"
          >
            {hasSubscription ? <QrCode className="h-5 w-5" /> : <Zap className="h-5 w-5" />}
            {hasSubscription ? 'QR и .conf' : 'Активировать'}
          </Link>
          <Link to="/dashboard/config" className="btn-secondary motion-interactive min-h-11 justify-start rounded-lg px-3 py-2.5" data-phase57-primary-action="devices">
            <FileCode2 className="h-5 w-5" />
            Устройства
          </Link>
          <Link to="/dashboard/subscription" className="btn-secondary motion-interactive min-h-11 justify-start rounded-lg px-3 py-2.5" data-phase57-primary-action="subscription">
            <Calendar className="h-5 w-5" />
            {hasSubscription ? 'Продлить' : 'Тарифы'}
          </Link>
          <button
            type="button"
            onClick={() => handleMtprotoCopy('link', mtprotoBrowserLink)}
            className={copiedMtprotoField === 'link' ? 'btn-secondary motion-interactive motion-copy-success min-h-11 justify-start rounded-lg px-3 py-2.5' : 'btn-secondary motion-interactive min-h-11 justify-start rounded-lg px-3 py-2.5'}
            disabled={!mtprotoBrowserLink}
            data-phase57-primary-action="mtproto-copy"
            data-phase59-microinteractions="[MatrixMotion][phase59][MICROINTERACTIONS_READY]"
          >
            <Link2 className="h-5 w-5" />
            Proxy
          </button>
        </div>

        <p className="mt-3 text-xs muted">{subscriptionHint(subscription)}</p>
      </section>

      <section
        className="phase57-card-compact"
        data-phase31-mtproto-card="true"
        data-phase53-mtproto-card="compact"
        data-phase57-mtproto-owner-card="redacted-actions"
        data-phase46-mtproto-status-refresh-ms={MTPROTO_STATUS_REFRESH_MS}
        data-mtproto-status={mtproto?.status || (mtprotoError ? 'degraded' : 'pending')}
        data-phase59-microinteractions="[MatrixMotion][phase59][MICROINTERACTIONS_READY]"
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase text-cyan-100/70">Telegram MTProto</p>
            <h2 className="mt-1 text-xl font-extrabold text-white">Личный proxy</h2>
            <p className="mt-1 text-sm muted">
              {mtprotoIntroText(mtproto, mtprotoLoading, mtprotoError)}
            </p>
          </div>
          <span className={mtprotoStatusClass(mtproto, mtprotoLoading, mtprotoError)}>
            {mtprotoStatusLabel(mtproto, mtprotoLoading, mtprotoError)}
          </span>
        </div>

        {mtprotoReady ? (
          <>
            <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-[minmax(0,1fr)_88px_minmax(0,1.2fr)]">
              <div className="min-w-0">
                <dt className="metric-label">Сервер</dt>
                <dd className="matrix-copy-box mt-1 break-all font-semibold text-slate-50">{mtproto.server}</dd>
              </div>
              <div className="min-w-0">
                <dt className="metric-label">Порт</dt>
                <dd className="matrix-copy-box mt-1 font-semibold text-slate-50">{mtproto.port}</dd>
              </div>
              <div className="min-w-0">
                <dt className="metric-label">Секрет</dt>
                <dd className="matrix-terminal mt-1 max-h-20 break-all font-semibold">{mtproto.secret}</dd>
              </div>
            </dl>

            <div className="matrix-action-grid mt-3 grid-cols-2 sm:grid-cols-5" data-phase57-mtproto-actions="tg-browser-copy-fields">
              <a
                href={mtprotoTelegramAppLink || mtproto.tg_link}
                className="btn-primary motion-interactive min-h-10 min-w-0 rounded-lg px-2 py-2 text-sm"
                aria-label="Open MTProto proxy in Telegram"
                title="Open MTProto proxy in Telegram"
                onClick={() => console.info(MTPROTO_OPEN_TELEGRAM_MARKER, { field: 'telegram_app_link' })}
              >
                <ExternalLink className="h-4 w-4" />
                <span className="truncate">Telegram</span>
              </a>
              {renderMtprotoCopyButton('link', 'Ссылка', mtprotoBrowserLink)}
              {renderMtprotoCopyButton('server', 'Сервер', mtproto.server)}
              {renderMtprotoCopyButton('port', 'Порт', mtproto.port)}
              {renderMtprotoCopyButton('secret', 'Секрет', mtproto.secret)}
            </div>
          </>
        ) : (
          <div className="matrix-state-line mt-3">
            {mtproto?.status === 'unverified' ? (
              <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-amber-100" />
            ) : (
              <Link2 className="mt-0.5 h-4 w-4 shrink-0 text-cyan-100" />
            )}
            <span className="min-w-0 break-words">
              {mtprotoLoading
                ? 'Состояние появится через несколько секунд.'
                : mtprotoError
                  ? 'Обновите страницу позже или продолжайте пользоваться VPN кабинетом.'
                  : mtproto?.safe_message || 'Proxy пока не выдан.'}
            </span>
          </div>
        )}
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" data-phase57-dashboard-metrics="compact">
        <article className="metric-card" data-phase53-dashboard-metric="vpn-status" data-phase57-dashboard-metric="vpn-status">
          <div className="flex items-center gap-3">
            <Shield className="h-5 w-5 shrink-0 text-emerald-200" />
            <div className="min-w-0">
              <p className="metric-label">{t('status')}</p>
              <p className="truncate font-bold">{isConnected ? t('connected') : t('disconnected')}</p>
            </div>
          </div>
        </article>

        <article className="metric-card" data-phase53-dashboard-metric="devices" data-phase57-dashboard-metric="devices">
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

        <article className="metric-card" data-phase53-dashboard-metric="upload" data-phase57-dashboard-metric="upload">
          <div className="flex items-center gap-3">
            <ArrowUp className="h-5 w-5 shrink-0 text-emerald-200" />
            <div className="min-w-0">
              <p className="metric-label">{t('upload')}</p>
              <p className="truncate font-bold">{stats?.total_upload_formatted || '0 B'}</p>
            </div>
          </div>
        </article>

        <article className="metric-card" data-phase53-dashboard-metric="download" data-phase57-dashboard-metric="download">
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
        <article className="phase57-card-compact">
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

        <article className="phase57-card-compact">
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
              <Link to="/dashboard/config" className="btn-secondary motion-interactive mt-4 min-h-11 w-full justify-start rounded-lg px-3 py-2.5">
                <FileCode2 className="h-5 w-5" />
                Открыть конфигурацию
              </Link>
            </div>
          </div>
        </article>
      </section>

      {!hasSubscription ? (
        <section className="phase57-card-compact">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <h2 className="text-lg font-bold">Подписка нужна для рабочего конфига</h2>
              <p className="mt-1 text-sm muted">После оплаты появятся QR-код, `.conf` и управление устройствами.</p>
            </div>
            <Link to="/dashboard/subscription" className="btn-primary motion-interactive min-h-11 shrink-0 rounded-lg px-3 py-2.5">
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
