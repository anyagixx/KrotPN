// FILE: frontend/src/pages/Dashboard.tsx
// VERSION: 1.3.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact mobile-first dashboard showing VPN status, config action, subscription, MTProto proxy, traffic, and device summary
//   SCOPE: Mobile home workflow, primary config/subscription CTA, MTProto owner actions, active device summary, compact traffic and connection facts
//   DEPENDS: M-009 (frontend-user), M-002 (auth API), M-003 (vpn stats API), M-004 (billing API), M-022 (device API), M-036 (mobile-user-cabinet), M-045 (mtproto-user-cabinet), M-051 (mtproto-availability-diagnostics)
//   LINKS: M-009 (frontend-user), M-036 (mobile-user-cabinet), M-045, M-051
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   DashboardPage - Compact dashboard component with mobile-first primary actions, MTProto owner card, and device summary
//   buildMtprotoTelegramAppLink - Builds tg://proxy action link from the owner payload for Telegram app opening
//   buildMtprotoBrowserLink - Builds https://t.me/proxy browser/copy link from the owner payload
//   mtprotoIntroText - Builds a non-duplicating MTProto card intro line
//   BLOCK_DASHBOARD_PAGE - DashboardPage default export with VPN, subscription, MTProto, config, and device surfaces
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
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
  if (isLoading || payload?.status === 'pending') return 'status-badge-warning w-fit'
  if (isError || payload?.status === 'degraded' || payload?.status === 'reissue_required') return 'status-badge-error w-fit'
  if (payload?.status === 'activated') return 'status-badge-success w-fit'
  return 'status-badge-warning w-fit'
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
      className="btn-secondary min-h-10 min-w-0 rounded-lg px-2 py-2 text-sm"
      aria-label={`Copy MTProto ${field}`}
      title={`Copy MTProto ${field}`}
      disabled={!value}
    >
      {copiedMtprotoField === field ? <Check className="h-4 w-4 text-emerald-200" /> : <Copy className="h-4 w-4" />}
      <span className="truncate">{label}</span>
    </button>
  )

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
                  ? subscriptionPending
                    ? 'Скачайте конфиг: trial начнется после первого VPN подключения.'
                    : 'Конфиг, QR и устройства доступны из главного действия.'
                  : 'Активируйте подписку, чтобы получить рабочий конфиг.'}
              </p>
            </div>
            <span className={isConnected ? 'status-badge-success w-fit' : 'status-badge-warning w-fit'}>
              {isConnected ? t('connected') : t('disconnected')}
            </span>
          </div>

          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            <Link to={hasSubscription ? '/config' : '/subscription'} className="btn-primary min-h-12 justify-start rounded-lg px-3 py-3">
              {hasSubscription ? <QrCode className="h-5 w-5" /> : <Zap className="h-5 w-5" />}
              {hasSubscription ? 'QR и .conf' : 'Активировать'}
            </Link>
            <Link to="/config" className="btn-secondary min-h-12 justify-start rounded-lg px-3 py-3">
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
                {formatSubscriptionRemaining(subscription)}
              </p>
              <p className="mt-1 text-xs muted">{subscriptionHint(subscription)}</p>
            </div>
            <Calendar className="h-5 w-5 shrink-0 text-cyan-100" />
          </div>
          <Link to="/subscription" className={hasSubscription ? 'btn-secondary mt-4 min-h-11 w-full rounded-lg px-3 py-2.5' : 'btn-primary mt-4 min-h-11 w-full rounded-lg px-3 py-2.5'}>
            {hasSubscription ? 'Продлить' : 'Выбрать тариф'}
          </Link>
        </article>
      </section>

      <section
        className="panel p-4 sm:p-5"
        data-phase31-mtproto-card="true"
        data-phase46-mtproto-status-refresh-ms={MTPROTO_STATUS_REFRESH_MS}
        data-mtproto-status={mtproto?.status || (mtprotoError ? 'degraded' : 'pending')}
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
            <dl className="mt-3 grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[minmax(0,1fr)_88px_minmax(0,1.2fr)]">
              <div className="min-w-0">
                <dt className="metric-label">Сервер</dt>
                <dd className="mt-1 break-all font-semibold text-slate-50">{mtproto.server}</dd>
              </div>
              <div className="min-w-0">
                <dt className="metric-label">Порт</dt>
                <dd className="mt-1 font-semibold text-slate-50">{mtproto.port}</dd>
              </div>
              <div className="min-w-0">
                <dt className="metric-label">Секрет</dt>
                <dd className="mt-1 break-all font-mono text-xs font-semibold text-slate-50">{mtproto.secret}</dd>
              </div>
            </dl>

            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
              <a
                href={mtprotoTelegramAppLink || mtproto.tg_link}
                className="btn-primary min-h-10 min-w-0 rounded-lg px-2 py-2 text-sm"
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
          <div className="mt-3 flex items-start gap-3 text-sm text-slate-100">
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
              <Link to="/config" className="btn-secondary mt-4 min-h-11 w-full justify-start rounded-lg px-3 py-2.5">
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
            <Link to="/subscription" className="btn-primary min-h-11 shrink-0 rounded-lg px-3 py-2.5">
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
