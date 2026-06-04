// FILE: frontend/src/pages/Config.tsx
// VERSION: 1.7.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Premium compact Matrix KPN configuration page for selected-device config download/copy/QR and device lifecycle controls
//   SCOPE: Device CRUD (create/rotate/revoke), selected-device read-only config actions, truthful AmneziaWG QR modal, AmneziaVPN .conf guidance, compact master-detail UX, copy/download microinteractions, and mobile-safe sticky actions
//   DEPENDS: M-009 (frontend-user), M-003 (vpn config API), M-002 (auth API), M-022 (device provisioning API), M-036 (mobile-user-cabinet), M-038 (compact-ui-system), M-071 (matrix-style-system), M-074 (responsive-device-adaptation), M-075 (premium-user-cabinet), M-077 (matrix-motion-interactions)
//   LINKS: M-009 (frontend-user), M-036 (mobile-user-cabinet), M-038, M-071, M-074, M-075, M-077, Phase-59, Phase-62, Phase-70, Phase-71, Phase-73
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ConfigPage - Premium master-detail config page component with selected-device config, AmneziaWG QR modal, tariff-aware limit copy, and secondary lifecycle controls
//   QRModal - Server-backed selected-device AmneziaWG QR modal with icon-only close, client-side payload fallback, and AmneziaVPN .conf guidance
//   buildConfigDownloadBlob - Creates octet-stream config download blobs
//   buildConfigDownloadFilename - Creates safe .conf download filenames
//   deviceStatusLabel - Localizes compact device status labels
//   getDisplayTariffLabel - Maps backend subscription plan names to user-facing tariff labels for display-only limit copy
//   BLOCK_CONFIG_PAGE - ConfigPage default export with Phase-71 selected-device workflow markers
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v3.8.0 - Executed Phase-73 KPN copy, tariff-aware device-limit messaging, and removed non-working AmneziaVPN QR advertising in favor of .conf import guidance.
//   LAST_CHANGE: v3.7.1 - Restored Phase-62 collapse compatibility marker on the Phase-71 master-detail surface.
//   LAST_CHANGE: v3.7.0 - Executed Phase-71 selected-device master-detail UX, per-device download/QR API usage, icon-only QR close, and secondary destructive actions.
//   LAST_CHANGE: v3.6.0 - Added Phase-70 QR parity markers and lighter QR rendering settings.
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
import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import { useTranslation } from 'react-i18next'
import {
  AlertTriangle,
  Check,
  Copy,
  Download,
  Laptop2,
  MoreVertical,
  Plus,
  QrCode,
  RotateCw,
  ShieldCheck,
  Trash2,
  X,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import QRCodeCanvas from 'qrcode.react'
import { CONFIG_DOWNLOAD_MIME_TYPE, billingApi, deviceApi, type SubscriptionStatus, type UserDevice } from '../lib/api'
import Loading from '../components/Loading'

const CONFIG_DOWNLOAD_FALLBACK_FILENAME = 'krotpn.conf'
const QR_ERROR_CORRECTION_LEVEL = 'M' as const
const QR_CANVAS_SIZE = 224
const QR_INCLUDE_MARGIN = true

const TARIFF_DISPLAY_ALIASES: Record<string, string> = {
  'KrotPN 1': 'KrotPN Self',
  'KrotPN 6': 'KrotPN Family',
  'KrotPN 9': 'KrotPN Team',
}

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

function deviceStatusLabel(status: string, t: (key: string) => string) {
  if (status === 'active') return t('deviceStatusActive')
  if (status === 'blocked') return t('deviceStatusBlocked')
  if (status === 'revoked') return t('deviceStatusRevoked')
  return status
}

function firstSelectableDevice(devices: UserDevice[]) {
  return devices.find((device) => device.status === 'active') || devices[0] || null
}

// START_CONTRACT: getDisplayTariffLabel
//   PURPOSE: Return the visible current tariff name used only in device-limit copy.
//   INPUTS: subscription: SubscriptionStatus | null | undefined - backend subscription state; t: translation function.
//   OUTPUTS: string - user-facing tariff label with Phase-68 aliases where possible.
//   SIDE_EFFECTS: none.
// END_CONTRACT: getDisplayTariffLabel
function getDisplayTariffLabel(
  subscription: SubscriptionStatus | null | undefined,
  t: (key: string) => string,
): string {
  const rawPlanName = subscription?.plan_name?.trim()
  if (rawPlanName?.toLowerCase() === 'trial') return t('trial')
  if (rawPlanName) return TARIFF_DISPLAY_ALIASES[rawPlanName] || rawPlanName
  if (subscription?.is_trial) return t('trial')
  return t('currentPlan')
}

export default function Config() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [copied, setCopied] = useState(false)
  const [showQR, setShowQR] = useState(false)
  const [selectedDeviceId, setSelectedDeviceId] = useState<number | null>(null)
  const [newDeviceName, setNewDeviceName] = useState('')
  const [newDevicePlatform, setNewDevicePlatform] = useState('')

  const { data: devicesData, isLoading: devicesLoading, error: devicesError } = useQuery('device-list', () => deviceApi.list(), {
    retry: false,
  })
  const { data: subscriptionData } = useQuery('config-subscription', () => billingApi.getSubscription(), {
    retry: false,
    refetchInterval: 30000,
  })

  const deviceList = devicesData?.data?.devices || []
  const consumedSlots = devicesData?.data?.consumed_slots || 0
  const deviceLimit = devicesData?.data?.device_limit || 0
  const activeDeviceCount = deviceList.filter((device) => device.status === 'active').length
  const tariffLabel = getDisplayTariffLabel(subscriptionData?.data, t)
  const deviceLimitMessage = t('deviceLimitReachedWithTariff', { tariff: tariffLabel })
  const selectedDevice = useMemo(
    () => deviceList.find((device) => device.id === selectedDeviceId) || firstSelectableDevice(deviceList),
    [deviceList, selectedDeviceId],
  )
  const selectedDeviceIsActive = selectedDevice?.status === 'active'
  const canCreateDevice = deviceLimit <= 0 || consumedSlots < deviceLimit

  useEffect(() => {
    if (!deviceList.length) {
      if (selectedDeviceId !== null) setSelectedDeviceId(null)
      return
    }

    const stillPresent = selectedDeviceId !== null && deviceList.some((device) => device.id === selectedDeviceId)
    if (!stillPresent) {
      setSelectedDeviceId(firstSelectableDevice(deviceList)?.id || null)
    }
  }, [deviceList, selectedDeviceId])

  const selectedConfigQuery = useQuery(
    ['device-config', selectedDevice?.id],
    () => deviceApi.getConfig(selectedDevice!.id),
    {
      enabled: Boolean(selectedDevice?.id && selectedDeviceIsActive),
      retry: false,
    },
  )

  const selectedConfig = selectedConfigQuery.data?.data || null

  const createDeviceMutation = useMutation(
    (payload: { name: string; platform?: string }) => deviceApi.create(payload),
    {
      onSuccess: ({ data }) => {
        setNewDeviceName('')
        setNewDevicePlatform('')
        setSelectedDeviceId(data.device.id)
        queryClient.setQueryData(['device-config', data.device.id], { data })
        void queryClient.invalidateQueries('device-list')
        toast.success(t('deviceCreated'))
      },
      onError: (requestError: any) => {
        toast.error(requestError?.response?.data?.detail || t('deviceCreateFailed'))
      },
    },
  )

  const rotateDeviceMutation = useMutation(
    (deviceId: number) => deviceApi.rotate(deviceId),
    {
      onSuccess: ({ data }) => {
        setSelectedDeviceId(data.device.id)
        queryClient.setQueryData(['device-config', data.device.id], { data })
        void queryClient.invalidateQueries('device-list')
        toast.success(t('deviceRotated'))
      },
      onError: (requestError: any) => {
        toast.error(requestError?.response?.data?.detail || t('deviceRotateFailed'))
      },
    },
  )

  const revokeDeviceMutation = useMutation(
    (deviceId: number) => deviceApi.revoke(deviceId),
    {
      onSuccess: ({ data }) => {
        if (selectedDeviceId === data.id) {
          setSelectedDeviceId(null)
        }
        void queryClient.invalidateQueries('device-list')
        void queryClient.invalidateQueries(['device-config', data.id])
        toast.success(t('deviceRevoked'))
      },
      onError: (requestError: any) => {
        toast.error(requestError?.response?.data?.detail || t('deviceRevokeFailed'))
      },
    },
  )

  // START_BLOCK_HANDLE_DOWNLOAD
  const handleDownload = async () => {
    if (!selectedDevice?.id || !selectedDeviceIsActive) {
      toast.error(t('deviceSelectActive'))
      return
    }

    try {
      const response = await deviceApi.downloadConfig(selectedDevice.id)
      const url = window.URL.createObjectURL(buildConfigDownloadBlob(response.data))
      const link = window.document.createElement('a')
      link.href = url
      link.setAttribute('download', buildConfigDownloadFilename(selectedDevice.device_key))
      window.document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      toast.success(t('configDownloaded'))
    } catch {
      toast.error(t('error'))
    }
  }
  // END_BLOCK_HANDLE_DOWNLOAD

  // START_BLOCK_HANDLE_COPY
  const handleCopy = async () => {
    if (!selectedConfig?.config) {
      toast.error(t('configUnavailable'))
      return
    }
    await navigator.clipboard.writeText(selectedConfig.config)
    setCopied(true)
    toast.success(t('copied'))
    setTimeout(() => setCopied(false), 2000)
  }
  // END_BLOCK_HANDLE_COPY

  // START_BLOCK_HANDLE_CREATE_DEVICE
  const handleCreateDevice = async () => {
    const name = newDeviceName.trim()
    if (!name) {
      toast.error(t('deviceNameRequired'))
      return
    }
    if (!canCreateDevice) {
      toast.error(deviceLimitMessage)
      return
    }
    await createDeviceMutation.mutateAsync({
      name,
      platform: newDevicePlatform.trim() || undefined,
    })
  }
  // END_BLOCK_HANDLE_CREATE_DEVICE

  const handleRotateDevice = async (device: UserDevice) => {
    if (!window.confirm(t('deviceRotateConfirm'))) return
    await rotateDeviceMutation.mutateAsync(device.id)
  }

  const handleRevokeDevice = async (device: UserDevice) => {
    if (!window.confirm(t('deviceRevokeConfirm'))) return
    await revokeDeviceMutation.mutateAsync(device.id)
  }

  if (devicesLoading) {
    return <Loading text={t('loading')} />
  }

  const requestError = devicesError as any
  const errorMessage = requestError?.response?.data?.detail as string | undefined

  if (requestError) {
    return (
      <div className="empty-state">
        <AlertTriangle className="h-10 w-10 text-red-200" />
        <div>
          <p className="text-lg font-semibold">{t('configLoadFailed')}</p>
          <p className="mt-1 text-sm muted">{errorMessage || t('tryRefreshLater')}</p>
        </div>
      </div>
    )
  }

  const selectedConfigError = selectedConfigQuery.error as any
  const selectedConfigErrorMessage = selectedConfigError?.response?.data?.detail as string | undefined
  const isSelectedActionBusy =
    Boolean(selectedDevice?.id) &&
    (
      rotateDeviceMutation.isLoading && rotateDeviceMutation.variables === selectedDevice?.id
      || revokeDeviceMutation.isLoading && revokeDeviceMutation.variables === selectedDevice?.id
    )

  return (
    <div
      className="content-section matrix-page animate-in"
      data-phase53-route="config"
      data-phase57-route="config"
      data-phase62-user-surface="config-compact"
      data-phase62-collapse="phase71-master-detail"
      data-phase71-route="device-master-detail"
    >
      <section
        className="phase57-command-center"
        data-phase57-config-workflow="qr-download-copy-device"
        data-phase62-keep="[CompactDeletionAudit][phase62][PRIMARY_WORKFLOWS_PRESERVED]"
        data-phase71-device-master-detail="[PremiumUserCabinet][phase71][DEVICE_MASTER_DETAIL_READY]"
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase text-cyan-100/70">{t('vpnConfig')}</p>
            <h1 className="mt-1 text-2xl font-extrabold">{t('devicesTitle')}</h1>
          </div>
          <Link to="/dashboard/subscription" className="btn-secondary motion-interactive min-h-11 shrink-0 rounded-lg px-3 py-2.5">
            <ShieldCheck className="h-5 w-5" />
            {t('subscription')}
          </Link>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
          <div className="phase57-signal-tile">
            <p className="muted">{t('devicesActive')}</p>
            <p className="mt-1 text-xl font-bold">{activeDeviceCount}</p>
          </div>
          <div className="phase57-signal-tile">
            <p className="muted">{t('devicesUsed')}</p>
            <p className="mt-1 text-xl font-bold">{consumedSlots}</p>
          </div>
          <div className="phase57-signal-tile">
            <p className="muted">{t('devicesLimit')}</p>
            <p className="mt-1 text-xl font-bold">{deviceLimit || '∞'}</p>
          </div>
        </div>
      </section>

      <section className="phase71-config-master-detail" data-phase71-selected-device-exports="[PremiumUserCabinet][phase71][SELECTED_DEVICE_EXPORTS_SAFE]">
        <article className="phase57-card-compact">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="text-lg font-bold">{t('devicesListTitle')}</h2>
              <p className="mt-1 text-sm muted">{t('devicesListHint')}</p>
            </div>
            <Laptop2 className="h-5 w-5 shrink-0 text-cyan-100" />
          </div>

          <div className="phase71-device-list phase57-scroll-list mt-4 grid gap-2" data-phase57-device-list="scroll-safe">
            {deviceList.length ? (
              deviceList.map((device) => {
                const isSelected = device.id === selectedDevice?.id
                const isActive = device.status === 'active'

                return (
                  <button
                    key={device.id}
                    type="button"
                    onClick={() => setSelectedDeviceId(device.id)}
                    className={[
                      'matrix-row phase71-device-row motion-interactive text-left',
                      isSelected ? 'phase71-device-row-selected' : '',
                    ].join(' ')}
                    data-phase71-device-row={isSelected ? 'selected' : 'idle'}
                  >
                    <div className="flex min-w-0 items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="max-w-full truncate font-bold">{device.name}</span>
                          <span className={isActive ? 'status-badge-success motion-status' : 'status-badge-warning motion-status'}>
                            {deviceStatusLabel(device.status, t)}
                          </span>
                        </div>
                        <p className="mt-1 text-sm muted">
                          {device.platform || t('platformNotSet')} · v{device.config_version}
                        </p>
                        <p className="mt-1 break-all text-xs muted">{device.device_key}</p>
                      </div>
                      {isSelected ? <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-200" /> : null}
                    </div>
                  </button>
                )
              })
            ) : (
              <div className="empty-state min-h-[180px]">
                <Laptop2 className="h-10 w-10 text-cyan-100" />
                <div>
                  <p className="text-lg font-semibold">{t('devicesEmpty')}</p>
                  <p className="mt-1 text-sm muted">{t('devicesEmptyHint')}</p>
                </div>
              </div>
            )}
          </div>
        </article>

        <article className="phase57-card-compact phase71-device-detail">
          {selectedDevice ? (
            <>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <p className="text-xs font-bold uppercase text-cyan-100/70">{t('selectedDevice')}</p>
                  <h2 className="mt-1 truncate text-xl font-extrabold">{selectedDevice.name}</h2>
                  <p className="mt-2 text-sm muted">
                    {selectedDevice.platform || t('platformNotSet')} · v{selectedDevice.config_version}
                  </p>
                  <p className="mt-1 break-all text-xs muted">{selectedDevice.device_key}</p>
                </div>
                <span className={selectedDeviceIsActive ? 'status-badge-success motion-status w-fit shrink-0' : 'status-badge-warning motion-status w-fit shrink-0'}>
                  {deviceStatusLabel(selectedDevice.status, t)}
                </span>
              </div>

              {selectedConfigQuery.isLoading ? (
                <div className="matrix-state-line mt-4">
                  <QrCode className="mt-0.5 h-4 w-4 shrink-0 text-cyan-100" />
                  <span>{t('configLoading')}</span>
                </div>
              ) : selectedConfigError ? (
                <div className="matrix-state-line mt-4 text-amber-100">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{selectedConfigErrorMessage || t('configUnavailable')}</span>
                </div>
              ) : (
                <div className="matrix-state-line mt-4">
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-200" />
                  <span>{selectedDeviceIsActive ? t('configReady') : t('deviceSelectActive')}</span>
                </div>
              )}

              <div
                className="matrix-action-grid phase71-sticky-actions mt-4 sm:grid-cols-3"
                data-phase57-config-actions="qr-download-copy"
                data-phase59-microinteractions="[MatrixMotion][phase59][MICROINTERACTIONS_READY]"
                data-phase59-status-transitions="[MatrixMotion][phase59][STATUS_TRANSITIONS_READY]"
                data-phase71-sticky-actions="[ResponsiveAdaptation][phase71][MOBILE_STICKY_ACTIONS_SAFE]"
              >
                <button
                  onClick={() => setShowQR(true)}
                  disabled={!selectedConfig?.config || !selectedDeviceIsActive}
                  className="btn-primary motion-interactive min-h-11 rounded-lg px-3 py-2.5"
                >
                  <QrCode className="h-5 w-5" />
                  QR
                </button>
                <button
                  onClick={handleDownload}
                  disabled={!selectedDeviceIsActive}
                  className="btn-secondary motion-interactive min-h-11 rounded-lg px-3 py-2.5"
                >
                  <Download className="h-5 w-5" />
                  .conf
                </button>
                <button
                  onClick={handleCopy}
                  disabled={!selectedConfig?.config || !selectedDeviceIsActive}
                  className={copied ? 'btn-secondary motion-interactive motion-copy-success min-h-11 rounded-lg px-3 py-2.5' : 'btn-secondary motion-interactive min-h-11 rounded-lg px-3 py-2.5'}
                >
                  {copied ? <Check className="h-5 w-5 text-emerald-200" /> : <Copy className="h-5 w-5" />}
                  {copied ? t('copied') : t('copyConfig')}
                </button>
              </div>

              <details className="phase71-device-menu mt-4" data-phase71-secondary-actions="[PremiumUserCabinet][phase71][DESTRUCTIVE_ACTIONS_SECONDARY]">
                <summary className="phase71-device-menu-summary motion-interactive">
                  <MoreVertical className="h-4 w-4" />
                  <span>{t('deviceSecondaryActions')}</span>
                </summary>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  <button
                    onClick={() => handleRotateDevice(selectedDevice)}
                    disabled={!selectedDeviceIsActive || isSelectedActionBusy}
                    className="btn-secondary motion-interactive min-h-10 rounded-lg px-3 py-2 text-sm"
                  >
                    <RotateCw className="h-4 w-4" />
                    {t('rotateConfig')}
                  </button>
                  <button
                    onClick={() => handleRevokeDevice(selectedDevice)}
                    disabled={!selectedDeviceIsActive || isSelectedActionBusy}
                    className="btn-danger motion-interactive min-h-10 rounded-lg px-3 py-2 text-sm"
                  >
                    <Trash2 className="h-4 w-4" />
                    {t('deleteDevice')}
                  </button>
                </div>
              </details>
            </>
          ) : (
            <div className="empty-state min-h-[220px]">
              <QrCode className="h-10 w-10 text-cyan-100" />
              <div>
                <p className="text-lg font-semibold">{t('deviceSelectPrompt')}</p>
                <p className="mt-1 text-sm muted">{t('deviceSelectPromptHint')}</p>
              </div>
            </div>
          )}
        </article>
      </section>

      <article className="phase57-card-compact">
        <div className="flex items-start gap-3">
          <Plus className="mt-1 h-5 w-5 shrink-0 text-emerald-200" />
          <div className="min-w-0">
            <h2 className="text-lg font-bold">{t('newDeviceConfig')}</h2>
            <p
              className="mt-1 text-sm muted"
              data-phase73-limit-message={!canCreateDevice ? '[MobileUserCabinet][phase73][LIMIT_MESSAGE_TARIFF_VISIBLE]' : undefined}
              data-phase73-tariff-copy={!canCreateDevice ? '[PremiumUserCabinet][phase73][DEVICE_LIMIT_TARIFF_COPY]' : undefined}
            >
              {canCreateDevice ? t('newDeviceHint') : deviceLimitMessage}
            </p>
          </div>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="grid gap-2">
            <span className="text-sm muted">{t('name')}</span>
            <input
              value={newDeviceName}
              onChange={(event) => setNewDeviceName(event.target.value)}
              placeholder={t('deviceNamePlaceholder')}
              className="input"
              disabled={!canCreateDevice}
            />
          </label>
          <label className="grid gap-2">
            <span className="text-sm muted">{t('platform')}</span>
            <input
              value={newDevicePlatform}
              onChange={(event) => setNewDevicePlatform(event.target.value)}
              placeholder="ios, android, macos, windows"
              className="input"
              disabled={!canCreateDevice}
            />
          </label>
        </div>
        <button
          onClick={handleCreateDevice}
          disabled={createDeviceMutation.isLoading || !canCreateDevice}
          className="btn-primary motion-interactive mt-4 min-h-11 w-full rounded-lg px-3 py-2.5"
        >
          <Plus className="h-5 w-5" />
          {t('createDevice')}
        </button>
      </article>

      {showQR && selectedDevice && selectedConfig?.config ? (
        <QRModal
          configText={selectedConfig.config}
          deviceId={selectedDevice.id}
          deviceName={selectedDevice.name}
          onDownload={handleDownload}
          onClose={() => setShowQR(false)}
        />
      ) : null}
    </div>
  )
}

// START_BLOCK_QR_MODAL
function QRModal({
  configText,
  deviceId,
  deviceName,
  onDownload,
  onClose,
}: {
  configText: string
  deviceId: number
  deviceName: string
  onDownload: () => void
  onClose: () => void
}) {
  const { t } = useTranslation()
  const [qrUrl, setQrUrl] = useState<string | null>(null)
  const qrQuery = useQuery(
    ['device-qr', deviceId, 'amneziawg'],
    () => deviceApi.getQRCode(deviceId),
    {
      retry: false,
    },
  )

  useEffect(() => {
    if (!qrQuery.data?.data) {
      setQrUrl(null)
      return undefined
    }
    const url = window.URL.createObjectURL(qrQuery.data.data)
    setQrUrl(url)
    return () => {
      window.URL.revokeObjectURL(url)
    }
  }, [qrQuery.data])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm">
      <div className="glass w-full max-w-md p-5 sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h3 className="truncate text-xl font-bold">{t('scanQR')}</h3>
            <p className="mt-1 truncate text-sm muted">{deviceName}</p>
            <p className="mt-1 text-sm muted">{t('qrInstructionsWG')}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="phase71-icon-close motion-interactive"
            aria-label={t('close')}
            title={t('close')}
            data-phase71-qr-close="[MatrixMotion][phase71][QR_CLOSE_ICON_SAFE]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div
          className="mt-6 flex min-h-[256px] items-center justify-center rounded-lg bg-white p-4 sm:p-5"
          data-phase70-qr-parity="frontend-config-payload"
          data-phase70-qr-lightweight="level-m-margin"
          data-phase71-device-qr="server-backed-selected-device"
          data-phase73-payload-unchanged="[VPNConfig][phase73][PAYLOAD_UNCHANGED]"
          data-phase73-amneziawg-qr="[DeviceConfig][phase73][SELECTED_DEVICE_AMNEZIAWG_QR_SAFE]"
        >
          {qrQuery.isLoading ? (
            <span className="text-sm font-semibold text-slate-700">{t('loading')}</span>
          ) : qrUrl ? (
            <img src={qrUrl} alt="" className="h-56 w-56 object-contain" draggable={false} />
          ) : (
            <QRCodeCanvas
              value={configText}
              size={QR_CANVAS_SIZE}
              level={QR_ERROR_CORRECTION_LEVEL}
              includeMargin={QR_INCLUDE_MARGIN}
            />
          )}
        </div>

        <div
          className="mt-4 rounded-lg border border-cyan-100/15 bg-cyan-100/5 p-3 text-sm muted"
          data-phase73-amneziavpn-qr="[ConfigPage][phase73][AMNEZIA_VPN_QR_NOT_ADVERTISED]"
          data-phase73-amnezia-guidance="[MobileUserCabinet][phase73][AMNEZIA_CONF_GUIDANCE]"
          data-phase73-truthful-qr="[PremiumUserCabinet][phase73][AMNEZIA_QR_TRUTHFUL]"
        >
          <p>{t('qrInstructionsVPN')}</p>
          <button
            type="button"
            onClick={onDownload}
            className="btn-secondary motion-interactive mt-3 min-h-10 w-full rounded-lg px-3 py-2 text-sm"
          >
            <Download className="h-4 w-4" />
            {t('downloadConfig')}
          </button>
        </div>
      </div>
    </div>
  )
}
// END_BLOCK_QR_MODAL
// END_BLOCK_CONFIG_PAGE
