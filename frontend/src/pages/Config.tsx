// FILE: frontend/src/pages/Config.tsx
// VERSION: 1.0.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: VPN configuration management page -- device registry, config download/copy/QR, route topology display
//   SCOPE: Device CRUD (create/rotate/revoke), config rendering, QR modal, route and node info cards
//   DEPENDS: M-009 (frontend-user), M-003 (vpn config API), M-002 (auth API)
//   LINKS: M-009 (frontend-user)
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ConfigPage - Main config page component with device management, QR modal, config display
//   BLOCK_CONFIG_PAGE - ConfigPage default export (545 lines)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.8.1 - Fixed QR code not showing: removed disabled={Boolean(managedBundle)} from QR button so device-bound configs can also display QR
// END_CHANGE_SUMMARY
//
// START_BLOCK_CONFIG_PAGE
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import { useTranslation } from 'react-i18next'
import { AlertTriangle, ArrowRightLeft, Check, Copy, Download, FileCode2, Laptop2, Monitor, Plus, QrCode, RotateCw, Smartphone, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import QRCodeCanvas from 'qrcode.react'
import { deviceApi, type DeviceConfigBundle, vpnApi } from '../lib/api'
import Loading from '../components/Loading'

export default function Config() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [copied, setCopied] = useState(false)
  const [showQR, setShowQR] = useState(false)
  const [managedBundle, setManagedBundle] = useState<DeviceConfigBundle | null>(null)
  const [newDeviceName, setNewDeviceName] = useState('')
  const [newDevicePlatform, setNewDevicePlatform] = useState('')

  const { data: configData, isLoading, error } = useQuery('vpn-config', () => vpnApi.getConfig())
  const { data: routesData } = useQuery('vpn-routes', () => vpnApi.getRoutes())
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
      const url = window.URL.createObjectURL(new Blob([blobSource]))
      const link = window.document.createElement('a')
      link.href = url
      const fileName = managedBundle?.device.device_key
        ? `krotvpn-${managedBundle.device.device_key}.conf`
        : 'krotvpn.conf'
      link.setAttribute('download', fileName)
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
  const routes = routesData?.data?.routes || []
  const deviceList = devicesData?.data?.devices || []
  const consumedSlots = devicesData?.data?.consumed_slots || 0
  const deviceLimit = devicesData?.data?.device_limit || 0
  const routeName = config?.route_name
  const entryName = config?.entry_server_name || config?.server_name
  const entryLocation = config?.entry_server_location || config?.server_location
  const exitName = config?.exit_server_name
  const exitLocation = config?.exit_server_location
  const getTunnelBadgeClass = (status?: string) => {
    if (status === 'up') return 'status-badge-success'
    if (status === 'host_managed') return 'status-badge-warning'
    return 'status-badge-error'
  }
  const getTunnelLabel = (status?: string) => {
    if (status === 'up') return 'tunnel up'
    if (status === 'host_managed') return 'host managed'
    return status || 'unknown'
  }

  if (hasNoConfig || isForbidden) {
    return (
      <div className="content-section animate-in">
        <div className="section-header">
          <div>
            <h1 className="section-title">{t('vpnConfig')}</h1>
            <p className="section-subtitle">Конфигурация появится сразу после активации доступа и назначения VPN-клиента.</p>
          </div>
        </div>

        <div className="glass p-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-100/70">Configuration unavailable</p>
              <h2 className="mt-3 text-2xl font-extrabold">
                {isForbidden ? 'Доступ к VPN сейчас отключён' : 'Конфигурация ещё не выдана'}
              </h2>
              <p className="mt-2 max-w-2xl text-sm muted">
                {errorMessage || 'Сначала нужен активный доступ, после этого кабинет сможет выдать конфиг и QR-код.'}
              </p>
            </div>
            <Link to="/subscription" className="btn-primary">
              <Download className="h-5 w-5" />
              Открыть подписку
            </Link>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {routes.map((route: any) => (
            <div key={route.id} className="metric-card">
              <div className="flex items-center justify-between">
                <span className="metric-label">Маршрут</span>
                <span className={getTunnelBadgeClass(route.tunnel_status)}>
                  {getTunnelLabel(route.tunnel_status)}
                </span>
              </div>
              <div className="mt-5 flex items-center gap-3">
                <div className="rounded-2xl bg-white/8 p-3 text-cyan-100">
                  <ArrowRightLeft className="h-5 w-5" />
                </div>
                <div>
                  <p className="font-bold">{route.name}</p>
                  <p className="text-sm muted">{route.entry_node_name} -&gt; {route.exit_node_name || 'Exit not set'}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
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
    <div className="content-section animate-in">
      <div className="section-header">
        <div>
          <h1 className="section-title">{t('vpnConfig')}</h1>
          <p className="section-subtitle">Управляйте устройствами, перевыпускайте конфиги и держите лимит слотов под контролем.</p>
        </div>
      </div>

      <section className="panel p-6">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-100/70">Device registry</p>
            <h2 className="mt-3 text-2xl font-extrabold">Устройства и лимит доступа</h2>
            <p className="mt-2 max-w-2xl text-sm muted">
              Каждый слот теперь соответствует отдельному peer и отдельному конфигу. Отзывайте старые устройства и перевыпускайте конфиг только для нужного устройства.
            </p>
          </div>

          <div className="grid min-w-[240px] gap-3 sm:grid-cols-2">
            <div className="panel-soft px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] muted">Занято слотов</p>
              <p className="mt-2 text-2xl font-bold">{consumedSlots}</p>
            </div>
            <div className="panel-soft px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] muted">Лимит тарифа</p>
              <p className="mt-2 text-2xl font-bold">{deviceLimit}</p>
            </div>
          </div>
        </div>

        <div className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
          <div className="grid gap-3">
            {deviceList.length ? (
              deviceList.map((device) => {
                const isBusy =
                  rotateDeviceMutation.isLoading && rotateDeviceMutation.variables === device.id
                  || revokeDeviceMutation.isLoading && revokeDeviceMutation.variables === device.id

                return (
                  <div key={device.id} className="panel-soft px-4 py-4">
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                      <div className="flex items-start gap-3">
                        <div className="rounded-2xl bg-white/8 p-3 text-cyan-100">
                          <Laptop2 className="h-5 w-5" />
                        </div>
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-bold">{device.name}</p>
                            <span className={device.status === 'active' ? 'status-badge-success' : 'status-badge-warning'}>
                              {device.status}
                            </span>
                          </div>
                          <p className="mt-1 text-sm muted">
                            {device.platform || 'platform not set'} · version {device.config_version}
                          </p>
                          <p className="mt-2 text-xs muted">
                            key: {device.device_key}
                          </p>
                          {device.block_reason ? (
                            <p className="mt-2 text-xs text-amber-200">Причина ограничения: {device.block_reason}</p>
                          ) : null}
                        </div>
                      </div>

                      <div className="flex flex-col gap-3 sm:flex-row">
                        <button
                          onClick={() => rotateDeviceMutation.mutate(device.id)}
                          disabled={device.status !== 'active' || isBusy}
                          className="btn-secondary"
                        >
                          <RotateCw className="h-4 w-4" />
                          Перевыпустить
                        </button>
                        <button
                          onClick={() => revokeDeviceMutation.mutate(device.id)}
                          disabled={device.status !== 'active' || isBusy}
                          className="btn-secondary"
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

          <div className="glass p-5">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-100/70">Add device</p>
            <h3 className="mt-3 text-xl font-bold">Новый конфиг под устройство</h3>
            <div className="mt-5 grid gap-3">
              <label className="grid gap-2">
                <span className="text-sm muted">Название</span>
                <input
                  value={newDeviceName}
                  onChange={(event) => setNewDeviceName(event.target.value)}
                  placeholder="Например: iPhone 16 Pro"
                  className="rounded-2xl border border-white/10 bg-slate-950/45 px-4 py-3 text-sm text-slate-100 outline-none transition focus:border-cyan-200/40"
                />
              </label>
              <label className="grid gap-2">
                <span className="text-sm muted">Платформа</span>
                <input
                  value={newDevicePlatform}
                  onChange={(event) => setNewDevicePlatform(event.target.value)}
                  placeholder="ios, android, macos, windows"
                  className="rounded-2xl border border-white/10 bg-slate-950/45 px-4 py-3 text-sm text-slate-100 outline-none transition focus:border-cyan-200/40"
                />
              </label>
            </div>
            <button
              onClick={handleCreateDevice}
              disabled={createDeviceMutation.isLoading}
              className="btn-primary mt-5 w-full"
            >
              <Plus className="h-5 w-5" />
              Создать устройство
            </button>
          </div>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="panel p-6">
          <div className="mb-5 flex items-center gap-3">
            <div className="rounded-2xl bg-emerald-300/12 p-3 text-emerald-200">
              <Smartphone className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold">Телефон и планшет</h2>
              <p className="text-sm muted">Android и iPhone через QR или импорт файла</p>
            </div>
          </div>
          <ol className="space-y-3 text-sm text-slate-200">
            <li>1. Установите клиент AmneziaWG.</li>
            <li>2. Откройте QR-код или импортируйте конфигурационный файл.</li>
            <li>3. Активируйте профиль и включите туннель.</li>
          </ol>
          <button
            onClick={() => setShowQR(true)}
            className="btn-secondary mt-5 w-full"
          >
            <QrCode className="h-5 w-5" />
            Показать QR-код
          </button>
        </div>

        <div className="panel p-6">
          <div className="mb-5 flex items-center gap-3">
            <div className="rounded-2xl bg-cyan-300/12 p-3 text-cyan-100">
              <Monitor className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold">Компьютер</h2>
              <p className="text-sm muted">Windows, macOS и Linux через `.conf`</p>
            </div>
          </div>
          <ol className="space-y-3 text-sm text-slate-200">
            <li>1. Скачайте AmneziaVPN или совместимый клиент.</li>
            <li>2. Импортируйте выданный конфиг.</li>
            <li>3. Сохраните профиль и нажмите подключение.</li>
          </ol>
          <button onClick={handleDownload} className="btn-primary mt-5 w-full">
            <Download className="h-5 w-5" />
            {t('downloadConfig')}
          </button>
        </div>
      </div>

      {showQR ? (
        <QRModal
          configText={config?.config || ''}
          onClose={() => setShowQR(false)}
        />
      ) : null}

      <div className="panel p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-white/8 p-3 text-cyan-100">
              <FileCode2 className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold">Конфигурационный файл</h2>
              <p className="text-sm muted">Готовый конфиг для ручного импорта и резервного копирования.</p>
            </div>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            <button onClick={handleCopy} className="btn-secondary">
              {copied ? <Check className="h-5 w-5 text-emerald-200" /> : <Copy className="h-5 w-5" />}
              {copied ? t('copied') : t('copyConfig')}
            </button>
            <button onClick={handleDownload} className="btn-primary">
              <Download className="h-5 w-5" />
              {t('downloadConfig')}
            </button>
          </div>
        </div>

        <pre className="mt-6 overflow-x-auto rounded-[24px] bg-slate-950/55 p-5 text-sm text-cyan-100">
          {config?.config || 'Конфигурация недоступна'}
        </pre>
      </div>

      {config ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <div className="metric-card">
            <p className="metric-label">Маршрут</p>
            <p className="metric-value text-2xl">{routeName || 'Legacy single-node'}</p>
          </div>
          <div className="metric-card">
            <p className="metric-label">Entry node</p>
            <p className="metric-value text-2xl">{entryName}</p>
          </div>
          <div className="metric-card">
            <p className="metric-label">Entry location</p>
            <p className="metric-value text-2xl">{entryLocation}</p>
          </div>
          <div className="metric-card">
            <p className="metric-label">Exit</p>
            <p className="metric-value text-2xl">{exitName || 'Не задан'}</p>
            <p className="mt-2 text-sm muted">{exitLocation || 'Маршрут ещё не замкнут'}</p>
          </div>
          <div className="metric-card">
            <p className="metric-label">VPN IP</p>
            <p className="metric-value text-2xl">{config.address}</p>
          </div>
        </div>
      ) : null}

      {config ? (
        <div className="panel p-6">
          <div className="mb-5 flex items-center gap-3">
            <div className="rounded-2xl bg-white/8 p-3 text-cyan-100">
              <ArrowRightLeft className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold">Топология маршрута</h2>
              <p className="text-sm muted">Клиент подключается к entry-ноде, а внешний трафик выходит через exit-ноду.</p>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <div className="panel-soft px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] muted">Entry</p>
              <p className="mt-2 text-lg font-bold">{entryName}</p>
              <p className="mt-1 text-sm muted">{entryLocation}</p>
            </div>
            <div className="panel-soft px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] muted">Route</p>
              <p className="mt-2 text-lg font-bold">{routeName || 'Legacy single-node'}</p>
              <p className="mt-1 text-sm muted">
                {exitName ? `${entryName} -> ${exitName}` : 'Пока используется только entry-узел'}
              </p>
            </div>
            <div className="panel-soft px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] muted">Exit</p>
              <p className="mt-2 text-lg font-bold">{exitName || 'Не задан'}</p>
              <p className="mt-1 text-sm muted">{exitLocation || 'Выходной узел не сконфигурирован'}</p>
            </div>
          </div>
        </div>
      ) : null}

      {config ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-2">
          <div className="metric-card">
            <p className="metric-label">Создан</p>
            <p className="metric-value text-2xl">{new Date(config.created_at).toLocaleDateString('ru-RU')}</p>
          </div>
        </div>
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

  // AmneziaVPN expects JSON with containers array, not raw WireGuard INI
  const qrValue = qrType === 'amneziavpn'
    ? JSON.stringify({
        containers: [{ container: 'amneziawg', config_data: configText }],
        default: 'amneziawg',
      })
    : configText

  // 100% client-side QR generation — no server fetch, no blob, no CORS issues
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm">
      <div className="glass w-full max-w-md p-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-xl font-bold">{t('scanQR')}</h3>
            <p className="mt-1 text-sm muted">
              {qrType === 'amneziawg'
                ? t('qrInstructionsWG')
                : t('qrInstructionsVPN')}
            </p>
          </div>
          <button onClick={onClose} className="btn-secondary px-3 py-2">
            {t('close')}
          </button>
        </div>

        {/* Tab switcher */}
        <div className="mt-4 flex rounded-xl border border-slate-700/50 p-1">
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

        <div className="mt-6 flex justify-center rounded-[24px] bg-white p-5">
          <QRCodeCanvas
            value={qrValue}
            size={240}
            level="H"
            includeMargin={false}
          />
        </div>

        <p className="mt-3 text-center text-xs muted">
          {qrType === 'amneziawg'
            ? 'Сканируйте приложением AmneziaWG'
            : 'Сканируйте приложением AmneziaVPN (формат containers JSON)'}
        </p>
      </div>
    </div>
  )
}
// END_BLOCK_QR_MODAL
// END_BLOCK_CONFIG_PAGE
