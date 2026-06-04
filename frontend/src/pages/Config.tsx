// FILE: frontend/src/pages/Config.tsx
// VERSION: 1.5.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Premium compact Matrix VPN configuration page for device registry, config download/copy/QR, Phase-59 action feedback, and Phase-62 folded install guidance
//   SCOPE: Device CRUD (create/rotate/revoke), selected config actions, QR modal, secondary install guidance, copy/download microinteractions, and status transitions
//   DEPENDS: M-009 (frontend-user), M-003 (vpn config API), M-002 (auth API), M-022 (device provisioning API), M-036 (mobile-user-cabinet), M-038 (compact-ui-system), M-071 (matrix-style-system), M-074 (responsive-device-adaptation), M-075 (premium-user-cabinet), M-077 (matrix-motion-interactions)
//   LINKS: M-009 (frontend-user), M-036 (mobile-user-cabinet), M-038, M-071, M-074, M-075, M-077, Phase-59, Phase-62
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ConfigPage - Premium compact config page component with device management, QR modal, and Phase-62 folded guidance
//   QRModal - Client-side QR modal with AmneziaWG and AmneziaVPN guidance
//   buildConfigDownloadBlob - Creates octet-stream config download blobs
//   buildConfigDownloadFilename - Creates safe .conf download filenames
//   BLOCK_CONFIG_PAGE - ConfigPage default export with Phase-57 compact device/config workflow and Phase-59 feedback markers
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v3.5.0 - Removed Phase-68 visible raw config fallback and config diagnostics while preserving QR/download/copy/device workflows.
//   LAST_CHANGE: v3.4.0 - Added Phase-62 config deletion audit markers and folded install diagnostics behind compact details surfaces.
//   LAST_CHANGE: v3.3.0 - Added Phase-59 copy/download microinteraction markers and status transition classes.
//   LAST_CHANGE: v3.2.0 - Added Phase-57 compact config command surface, protected subscription link, scroll-safe device list, and workflow markers.
//   LAST_CHANGE: v3.1.0 - Applied Phase-53 compact Matrix config/device surfaces without changing download semantics.
//   LAST_CHANGE: v3.0.0 - Hardened frontend .conf downloads with octet-stream Blob type and safe filenames.
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.8.1 - Fixed QR code not showing: removed disabled={Boolean(managedBundle)} from QR button so device-bound configs can also display QR
//   LAST_CHANGE: v2.9.0 - Reworked device/config management into compact mobile-first Phase-23 workflow
// END_CHANGE_SUMMARY
//
// START_BLOCK_CONFIG_PAGE
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import { useTranslation } from 'react-i18next'
import { AlertTriangle, Check, Copy, Download, Laptop2, Monitor, Plus, QrCode, RotateCw, Smartphone, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import QRCodeCanvas from 'qrcode.react'
import { CONFIG_DOWNLOAD_MIME_TYPE, deviceApi, type DeviceConfigBundle, vpnApi } from '../lib/api'
import Loading from '../components/Loading'

const CONFIG_DOWNLOAD_FALLBACK_FILENAME = 'krotpn.conf'

// START_CONTRACT: buildConfigDownloadBlob
//   PURPOSE: Create a browser download Blob that mobile browsers do not reinterpret as .txt.
//   INPUTS: source: string | Blob - generated VPN config text or backend Blob response.
//   OUTPUTS: Blob - application/octet-stream Blob preserving source bytes.
//   SIDE_EFFECTS: none.
// END_CONTRACT: buildConfigDownloadBlob
function buildConfigDownloadBlob(source: string | Blob): Blob {
  return new Blob([source], { type: CONFIG_DOWNLOAD_MIME_TYPE })
}

// START_CONTRACT: buildConfigDownloadFilename
//   PURPOSE: Create compact ASCII .conf filenames for frontend-managed device configs.
//   INPUTS: deviceKey: string | null | undefined - optional device key from registry.
//   OUTPUTS: string - filename ending with exactly one .conf suffix.
//   SIDE_EFFECTS: none.
// END_CONTRACT: buildConfigDownloadFilename
function buildConfigDownloadFilename(deviceKey?: string | null): string {
  const rawName = deviceKey ? `krotpn-${deviceKey}` : CONFIG_DOWNLOAD_FALLBACK_FILENAME
  const withoutTxt = rawName.replace(/\.txt$/i, '')
  const withoutConf = withoutTxt.replace(/(\.conf)+$/i, '')
  const safeBase = withoutConf
    .replace(/[\\/]+/g, '-')
    .replace(/[^A-Za-z0-9_-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^[-_]+|[-_]+$/g, '')

  return `${safeBase || 'krotpn'}.conf`
}

export default function Config() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [copied, setCopied] = useState(false)
  const [showQR, setShowQR] = useState(false)
  const [managedBundle, setManagedBundle] = useState<DeviceConfigBundle | null>(null)
  const [newDeviceName, setNewDeviceName] = useState('')
  const [newDevicePlatform, setNewDevicePlatform] = useState('')

  const { data: configData, isLoading, error } = useQuery('vpn-config', () => vpnApi.getConfig())
  const { data: devicesData } = useQuery('device-list', () => deviceApi.list(), {
    retry: false,
  })

  const createDeviceMutation = useMutation(
    (payload: { name: string; platform?: string }) => deviceApi.create(payload),
    {
      onSuccess: ({ data }) => {
        setManagedBundle(data)
        setNewDeviceName('')
        setNewDevicePlatform('')
        void queryClient.invalidateQueries('device-list')
        toast.success('Устройство создано и конфиг готов')
      },
      onError: (requestError: any) => {
        toast.error(requestError?.response?.data?.detail || 'Не удалось создать устройство')
      },
    },
  )

  const rotateDeviceMutation = useMutation(
    (deviceId: number) => deviceApi.rotate(deviceId),
    {
      onSuccess: ({ data }) => {
        setManagedBundle(data)
        void queryClient.invalidateQueries('device-list')
        toast.success('Конфиг устройства перевыпущен')
      },
      onError: (requestError: any) => {
        toast.error(requestError?.response?.data?.detail || 'Не удалось перевыпустить конфиг')
      },
    },
  )

  const revokeDeviceMutation = useMutation(
    (deviceId: number) => deviceApi.revoke(deviceId),
    {
      onSuccess: ({ data }) => {
        if (managedBundle?.device.id === data.id) {
          setManagedBundle(null)
        }
        void queryClient.invalidateQueries('device-list')
        toast.success('Устройство отозвано')
      },
      onError: (requestError: any) => {
        toast.error(requestError?.response?.data?.detail || 'Не удалось отозвать устройство')
      },
    },
  )

  // Fetch QR code as blob on demand

  // START_BLOCK_HANDLE_DOWNLOAD
  const handleDownload = async () => {
    try {
      const activeConfig = managedBundle?.config ? managedBundle.config : null
      const blobSource = activeConfig ? activeConfig : (await vpnApi.downloadConfig()).data
      const url = window.URL.createObjectURL(buildConfigDownloadBlob(blobSource))
      const link = window.document.createElement('a')
      link.href = url
      link.setAttribute('download', buildConfigDownloadFilename(managedBundle?.device.device_key))
      window.document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      toast.success('Конфиг скачан')
    } catch {
      toast.error(t('error'))
    }
  }
  // END_BLOCK_HANDLE_DOWNLOAD

  // START_BLOCK_HANDLE_COPY
  const handleCopy = async () => {
    const activeConfig = managedBundle?.config || configData?.data?.config
    if (!activeConfig) {
      toast.error('Конфигурация пока недоступна')
      return
    }
    await navigator.clipboard.writeText(activeConfig)
    setCopied(true)
    toast.success(t('copied'))
    setTimeout(() => setCopied(false), 2000)
  }
  // END_BLOCK_HANDLE_COPY

  // START_BLOCK_HANDLE_CREATE_DEVICE
  const handleCreateDevice = async () => {
    const name = newDeviceName.trim()
    if (!name) {
      toast.error('Введите название устройства')
      return
    }
    await createDeviceMutation.mutateAsync({
      name,
      platform: newDevicePlatform.trim() || undefined,
    })
  }
  // END_BLOCK_HANDLE_CREATE_DEVICE

  if (isLoading) {
    return <Loading text={t('loading')} />
  }

  const config = managedBundle || configData?.data
  const requestError = error as any
  const errorMessage = requestError?.response?.data?.detail as string | undefined
  const hasNoConfig = requestError?.response?.status === 404
  const isForbidden = requestError?.response?.status === 403
  const deviceList = devicesData?.data?.devices || []
  const consumedSlots = devicesData?.data?.consumed_slots || 0
  const deviceLimit = devicesData?.data?.device_limit || 0
  const activeDeviceCount = deviceList.filter((device) => device.status === 'active').length
  const selectedDeviceName = managedBundle?.device.name || 'Текущий конфиг'
  const selectedDeviceKey = managedBundle?.device.device_key || null

  if (hasNoConfig || isForbidden) {
    return (
      <div className="content-section matrix-page animate-in" data-phase53-route="config" data-phase57-route="config" data-phase62-user-surface="config-compact">
        <section className="phase57-command-center" data-phase57-config-empty-state="true">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-bold uppercase text-cyan-100/70">{t('vpnConfig')}</p>
              <h1 className="mt-1 text-2xl font-extrabold">
                {isForbidden ? 'Доступ к VPN сейчас отключён' : 'Конфигурация ещё не выдана'}
              </h1>
              <p className="mt-2 text-sm muted">
                {errorMessage || 'Сначала нужен активный доступ, после этого кабинет сможет выдать конфиг и QR-код.'}
              </p>
            </div>
            <Link to="/dashboard/subscription" className="btn-primary motion-interactive min-h-11 shrink-0 rounded-lg px-3 py-2.5">
              <Download className="h-5 w-5" />
              Открыть подписку
            </Link>
          </div>
        </section>
      </div>
    )
  }

  if (requestError) {
    return (
      <div className="empty-state">
        <AlertTriangle className="h-10 w-10 text-red-200" />
        <div>
          <p className="text-lg font-semibold">Не удалось загрузить конфигурацию</p>
          <p className="mt-1 text-sm muted">{errorMessage || 'Попробуй обновить страницу чуть позже.'}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="content-section matrix-page animate-in" data-phase53-route="config" data-phase57-route="config" data-phase62-user-surface="config-compact">
      <section
        className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(260px,0.75fr)]"
        data-phase57-config-workflow="qr-download-copy-device"
        data-phase62-keep="[CompactDeletionAudit][phase62][PRIMARY_WORKFLOWS_PRESERVED]"
      >
        <article className="phase57-command-center">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-bold uppercase text-cyan-100/70">{t('vpnConfig')}</p>
              <h1 className="mt-1 truncate text-2xl font-extrabold">{selectedDeviceName}</h1>
              <p className="mt-2 text-sm muted">
                QR, `.conf`, copy и device-bound действия доступны без перехода в desktop layout.
              </p>
              {selectedDeviceKey ? (
                <p className="mt-2 break-all text-xs muted">key: {selectedDeviceKey}</p>
              ) : null}
            </div>
            <span className="status-badge-success motion-status w-fit shrink-0">config ready</span>
          </div>

          <div
            className="matrix-action-grid mt-4 sm:grid-cols-3"
            data-phase57-config-actions="qr-download-copy"
            data-phase59-microinteractions="[MatrixMotion][phase59][MICROINTERACTIONS_READY]"
            data-phase59-status-transitions="[MatrixMotion][phase59][STATUS_TRANSITIONS_READY]"
          >
            <button onClick={() => setShowQR(true)} disabled={!config?.config} className="btn-primary motion-interactive min-h-11 rounded-lg px-3 py-2.5">
              <QrCode className="h-5 w-5" />
              QR
            </button>
            <button onClick={handleDownload} className="btn-secondary motion-interactive min-h-11 rounded-lg px-3 py-2.5">
              <Download className="h-5 w-5" />
              .conf
            </button>
            <button onClick={handleCopy} className={copied ? 'btn-secondary motion-interactive motion-copy-success min-h-11 rounded-lg px-3 py-2.5' : 'btn-secondary motion-interactive min-h-11 rounded-lg px-3 py-2.5'}>
              {copied ? <Check className="h-5 w-5 text-emerald-200" /> : <Copy className="h-5 w-5" />}
              {copied ? t('copied') : t('copyConfig')}
            </button>
          </div>
        </article>

        <article className="phase57-card-compact">
          <p className="text-xs font-bold uppercase text-cyan-100/70">Устройства</p>
          <div className="mt-3 grid grid-cols-3 gap-2 text-sm">
            <div>
              <p className="muted">Активные</p>
              <p className="mt-1 text-xl font-bold">{activeDeviceCount}</p>
            </div>
            <div>
              <p className="muted">Занято</p>
              <p className="mt-1 text-xl font-bold">{consumedSlots}</p>
            </div>
            <div>
              <p className="muted">Лимит</p>
              <p className="mt-1 text-xl font-bold">{deviceLimit || '∞'}</p>
            </div>
          </div>
        </article>
      </section>

      <section className="grid gap-3 xl:grid-cols-[minmax(0,1.15fr)_minmax(260px,0.85fr)]">
        <article className="phase57-card-compact">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="text-lg font-bold">Device-bound список</h2>
              <p className="mt-1 text-sm muted">Перевыпускайте или удаляйте только нужное устройство.</p>
            </div>
            <Laptop2 className="h-5 w-5 shrink-0 text-cyan-100" />
          </div>

          <div className="phase57-scroll-list mt-4 grid gap-2" data-phase57-device-list="scroll-safe">
            {deviceList.length ? (
              deviceList.map((device) => {
                const isBusy =
                  rotateDeviceMutation.isLoading && rotateDeviceMutation.variables === device.id
                  || revokeDeviceMutation.isLoading && revokeDeviceMutation.variables === device.id

                return (
                  <div key={device.id} className="matrix-row">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="max-w-full truncate font-bold">{device.name}</p>
                          <span className={device.status === 'active' ? 'status-badge-success motion-status' : 'status-badge-warning motion-status'}>
                            {device.status}
                          </span>
                        </div>
                        <p className="mt-1 text-sm muted">
                          {device.platform || 'platform not set'} · v{device.config_version}
                        </p>
                        <p className="mt-1 break-all text-xs muted">key: {device.device_key}</p>
                        {device.block_reason ? (
                          <p className="mt-2 text-xs text-amber-200">Причина ограничения: {device.block_reason}</p>
                        ) : null}
                      </div>

                      <div className="grid grid-cols-2 gap-2 sm:flex sm:shrink-0">
                        <button
                          onClick={() => rotateDeviceMutation.mutate(device.id)}
                          disabled={device.status !== 'active' || isBusy}
                          className="btn-secondary motion-interactive min-h-10 rounded-lg px-3 py-2 text-sm"
                        >
                          <RotateCw className="h-4 w-4" />
                          Обновить
                        </button>
                        <button
                          onClick={() => revokeDeviceMutation.mutate(device.id)}
                          disabled={device.status !== 'active' || isBusy}
                          className="btn-danger motion-interactive min-h-10 rounded-lg px-3 py-2 text-sm"
                        >
                          <Trash2 className="h-4 w-4" />
                          Удалить
                        </button>
                      </div>
                    </div>
                  </div>
                )
              })
            ) : (
              <div className="empty-state min-h-[180px]">
                <Laptop2 className="h-10 w-10 text-cyan-100" />
                <div>
                  <p className="text-lg font-semibold">Устройств пока нет</p>
                  <p className="mt-1 text-sm muted">Создайте первый device-bound конфиг для телефона, ноутбука или домашнего компьютера.</p>
                </div>
              </div>
            )}
          </div>
        </article>

        <article className="phase57-card-compact">
          <div className="flex items-start gap-3">
            <Plus className="mt-1 h-5 w-5 shrink-0 text-emerald-200" />
            <div className="min-w-0">
              <h2 className="text-lg font-bold">Новый конфиг</h2>
              <p className="mt-1 text-sm muted">Создайте отдельный peer под телефон, ноутбук или планшет.</p>
            </div>
          </div>
          <div className="mt-4 grid gap-3">
              <label className="grid gap-2">
                <span className="text-sm muted">Название</span>
                <input
                  value={newDeviceName}
                  onChange={(event) => setNewDeviceName(event.target.value)}
                  placeholder="Например: iPhone 16 Pro"
                  className="input"
                />
              </label>
              <label className="grid gap-2">
                <span className="text-sm muted">Платформа</span>
                <input
                  value={newDevicePlatform}
                  onChange={(event) => setNewDevicePlatform(event.target.value)}
                  placeholder="ios, android, macos, windows"
                  className="input"
                />
              </label>
          </div>
          <button
            onClick={handleCreateDevice}
            disabled={createDeviceMutation.isLoading}
            className="btn-primary motion-interactive mt-4 min-h-11 w-full rounded-lg px-3 py-2.5"
          >
            <Plus className="h-5 w-5" />
            Создать устройство
          </button>
        </article>
      </section>

      <details
        className="phase62-secondary-fold"
        data-phase62-collapse="[CompactDeletionAudit][phase62][USER_SURFACES_PRUNED]"
        data-phase62-config-guidance="folded-install-help"
      >
        <summary className="phase62-fold-summary">
          <span className="flex min-w-0 items-center gap-2">
            <Smartphone className="h-4 w-4 shrink-0 text-emerald-200" />
            <span className="truncate font-semibold">Инструкции импорта</span>
          </span>
          <span className="text-xs muted">телефон / компьютер</span>
        </summary>

        <section className="mt-3 grid gap-3 lg:grid-cols-2">
          <article className="phase57-card-compact">
            <div className="flex items-start gap-3">
              <Smartphone className="mt-1 h-5 w-5 shrink-0 text-emerald-200" />
              <div className="min-w-0">
                <h2 className="text-lg font-bold">Телефон и планшет</h2>
                <p className="mt-1 text-sm muted">Android и iPhone через QR или импорт файла.</p>
              </div>
            </div>
            <ol className="mt-4 space-y-2 text-sm text-slate-200">
              <li>1. Установите клиент AmneziaWG.</li>
              <li>2. Откройте QR-код или импортируйте конфигурационный файл.</li>
              <li>3. Активируйте профиль и включите туннель.</li>
            </ol>
            <button
              onClick={() => setShowQR(true)}
              className="btn-secondary motion-interactive mt-4 min-h-11 w-full rounded-lg px-3 py-2.5"
            >
              <QrCode className="h-5 w-5" />
              Показать QR-код
            </button>
          </article>

          <article className="phase57-card-compact">
            <div className="flex items-start gap-3">
              <Monitor className="mt-1 h-5 w-5 shrink-0 text-cyan-100" />
              <div className="min-w-0">
                <h2 className="text-lg font-bold">Компьютер</h2>
                <p className="mt-1 text-sm muted">Windows, macOS и Linux через `.conf`.</p>
              </div>
            </div>
            <ol className="mt-4 space-y-2 text-sm text-slate-200">
              <li>1. Скачайте AmneziaVPN или совместимый клиент.</li>
              <li>2. Импортируйте выданный конфиг.</li>
              <li>3. Сохраните профиль и нажмите подключение.</li>
            </ol>
            <button onClick={handleDownload} className="btn-primary motion-interactive mt-4 min-h-11 w-full rounded-lg px-3 py-2.5">
              <Download className="h-5 w-5" />
              {t('downloadConfig')}
            </button>
          </article>
        </section>
      </details>

      {showQR ? (
        <QRModal
          configText={config?.config || ''}
          onClose={() => setShowQR(false)}
        />
      ) : null}

    </div>
  )
}

// START_BLOCK_QR_MODAL
function QRModal({
  configText,
  onClose,
}: {
  configText: string
  onClose: () => void
}) {
  const { t } = useTranslation()
  const [qrType, setQrType] = useState<'amneziawg' | 'amneziavpn'>('amneziawg')

  // AmneziaVPN doesn't accept raw WireGuard configs — users must import .conf file
  // Show a message instead of a broken QR
  const showQR = qrType === 'amneziawg'

  // 100% client-side QR generation — no server fetch, no blob, no CORS issues
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm">
      <div className="glass w-full max-w-md p-5 sm:p-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-xl font-bold">{t('scanQR')}</h3>
            <p className="mt-1 text-sm muted">
              {qrType === 'amneziawg'
                ? t('qrInstructionsWG')
                : t('qrInstructionsVPN')}
            </p>
          </div>
          <button onClick={onClose} className="btn-secondary motion-interactive px-3 py-2">
            {t('close')}
          </button>
        </div>

        {/* Tab switcher */}
        <div className="mt-4 flex rounded-lg border border-slate-700/50 p-1">
          <button
            onClick={() => setQrType('amneziawg')}
            className={`flex-1 rounded-lg py-2 text-sm font-semibold transition-colors ${
              qrType === 'amneziawg'
                ? 'bg-cyan-500/20 text-cyan-100'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            AmneziaWG
          </button>
          <button
            onClick={() => setQrType('amneziavpn')}
            className={`flex-1 rounded-lg py-2 text-sm font-semibold transition-colors ${
              qrType === 'amneziavpn'
                ? 'bg-cyan-500/20 text-cyan-100'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            AmneziaVPN
          </button>
        </div>

        <div className="mt-6 flex justify-center rounded-lg bg-white p-5">
          {showQR ? (
            <QRCodeCanvas
              value={configText}
              size={240}
              level="H"
              includeMargin={false}
            />
          ) : (
            <div className="text-center py-8 px-4">
              <p className="text-sm font-semibold text-slate-700">AmneziaVPN не поддерживает QR-коды для WireGuard</p>
              <p className="mt-2 text-xs text-slate-500">Скачайте <code className="bg-slate-100 px-1 rounded">.conf</code> файл и импортируйте его в AmneziaVPN через <strong>Импорт конфига</strong></p>
            </div>
          )}
        </div>

        <p className="mt-3 text-center text-xs muted">
          {qrType === 'amneziawg'
            ? 'Сканируйте приложением AmneziaWG'
            : 'Скачайте .conf файл ниже и импортируйте в AmneziaVPN'}
        </p>
      </div>
    </div>
  )
}
// END_BLOCK_QR_MODAL
// END_BLOCK_CONFIG_PAGE
