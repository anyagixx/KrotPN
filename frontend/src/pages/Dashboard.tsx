// FILE: frontend/src/pages/Dashboard.tsx
// VERSION: 1.8.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact Phase-68 dashboard showing the owner MTProto proxy first and the shared subscription/tariff/calendar block directly below it
//   SCOPE: MTProto owner actions, redacted copy/open workflow, bounded status refresh, embedded SubscriptionPanel, and removal of low-value dashboard folds
//   DEPENDS: M-009 (frontend-user), M-036 (mobile-user-cabinet), M-045 (mtproto-user-cabinet), M-063 (trial countdown), M-068 (paid tariff catalog), M-071 (matrix-style-system), M-074 (responsive-device-adaptation), M-075 (premium-user-cabinet), M-077 (matrix-motion-interactions)
//   LINKS: M-009, M-036, M-045, M-063, M-068, M-071, M-074, M-075, M-077, Phase-59, Phase-68
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   DashboardPage - Phase-68 compact dashboard with MTProto first and embedded subscription block
//   buildMtprotoTelegramAppLink - Builds tg://proxy action link from the owner payload for Telegram app opening
//   buildMtprotoBrowserLink - Builds https://t.me/proxy browser/copy link from the owner payload
//   mtprotoIntroText - Builds a non-duplicating MTProto card intro line
//   BLOCK_DASHBOARD_PAGE - DashboardPage default export with MTProto owner card and dashboard-owned SubscriptionPanel
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v3.8.0 - Executed Phase-68 dashboard compaction: removed command center and secondary fold, placed MTProto first, and embedded shared subscription panel.
//   LAST_CHANGE: v3.7.0 - Added Phase-62 dashboard deletion audit markers and folded duplicate traffic/device diagnostics behind a secondary surface.
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
  Check,
  Copy,
  ExternalLink,
  KeyRound,
  Link2,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { mtprotoApi, MTProtoProxyResponse } from '../lib/api'
import SubscriptionPanel from '../components/SubscriptionPanel'

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
  if (isLoading) return 'Проверяем выданный Telegram proxy.'
  if (isError) return 'Telegram proxy временно недоступен, остальные действия кабинета остаются доступны.'
  if (payload?.status === 'activated') return 'Постоянный бесплатный proxy доступен для Telegram.'
  if (payload?.status) return 'Состояние прокси отображается ниже.'
  return 'Proxy будет доступен после подготовки.'
}

export default function Dashboard() {
  const { t } = useTranslation()
  const [copiedMtprotoField, setCopiedMtprotoField] = useState<MTProtoCopyField | null>(null)
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
  const mtprotoReady = hasOwnerProxy(mtproto)
  const mtprotoTelegramAppLink = buildMtprotoTelegramAppLink(mtproto)
  const mtprotoBrowserLink = buildMtprotoBrowserLink(mtproto)

  useEffect(() => {
    if (mtproto?.status) {
      console.info(MTPROTO_CARD_RENDER_MARKER, { status: mtproto.status })
    }
  }, [mtproto?.status])

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
      data-phase62-user-surface="dashboard-compact"
      data-phase68-dashboard="mtproto-subscription-compact"
      data-phase59-status-transitions="[MatrixMotion][phase59][STATUS_TRANSITIONS_READY]"
    >
      <section
        className="phase57-card-compact"
        data-phase31-mtproto-card="true"
        data-phase53-mtproto-card="compact"
        data-phase57-mtproto-owner-card="redacted-actions"
        data-phase68-mtproto-card="primary-first"
        data-phase46-mtproto-status-refresh-ms={MTPROTO_STATUS_REFRESH_MS}
        data-mtproto-status={mtproto?.status || (mtprotoError ? 'degraded' : 'pending')}
        data-phase59-microinteractions="[MatrixMotion][phase59][MICROINTERACTIONS_READY]"
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h1 className="text-xl font-extrabold text-white">
              Ваш бесплатный постоянный <span className="text-emerald-100">Telegram MTProto</span> прокси
            </h1>
            <p className="mt-2 text-sm muted">
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

      <SubscriptionPanel compact />
    </div>
  )
}
// END_BLOCK_DASHBOARD_PAGE
