import { useState } from 'react'
import { useQuery } from 'react-query'
import { useTranslation } from 'react-i18next'
import { 
  Download, 
  Copy, 
  QrCode, 
  Check,
  FileCode,
  Smartphone,
  Monitor
} from 'lucide-react'
import toast from 'react-hot-toast'
import { vpnApi } from '../lib/api'
import Loading from '../components/Loading'

export default function Config() {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  const [showQR, setShowQR] = useState(false)
  
  const { data: configData, isLoading } = useQuery(
    'vpn-config',
    () => vpnApi.getConfig()
  )
  
  const { data: qrData } = useQuery(
    'vpn-qr',
    () => vpnApi.getQRCode(),
    { enabled: showQR }
  )
  
  const handleDownload = async () => {
    try {
      const response = await vpnApi.downloadConfig()
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = window.document.createElement('a')
      link.href = url
      link.setAttribute('download', 'krotvpn.conf')
      window.document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      toast.success(t('success'))
    } catch {
      toast.error(t('error'))
    }
  }
  
  const handleCopy = async () => {
    if (configData?.data?.config) {
      await navigator.clipboard.writeText(configData.data.config)
      setCopied(true)
      toast.success(t('copied'))
      setTimeout(() => setCopied(false), 2000)
    }
  }
  
  if (isLoading) {
    return <Loading text={t('loading')} />
  }
  
  const config = configData?.data
  
  return (
    <div className="space-y-8 animate-in max-w-4xl">
      <div>
        <h1 className="text-3xl font-bold">{t('vpnConfig')}</h1>
        <p className="text-dark-400 mt-2">
          {t('configInstructions')}
        </p>
      </div>
      
      {/* Platform Instructions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="glass-card">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-3 rounded-xl bg-primary-500/10">
              <Smartphone className="w-6 h-6 text-primary-400" />
            </div>
            <div>
              <h3 className="font-semibold">Мобильные устройства</h3>
              <p className="text-sm text-dark-400">Android, iOS</p>
            </div>
          </div>
          <ol className="space-y-2 text-sm text-dark-300">
            <li>1. Скачайте AmneziaWG из магазина приложений</li>
            <li>2. Отсканируйте QR-код или импортируйте файл</li>
            <li>3. Нажмите "Подключить"</li>
          </ol>
          <button
            onClick={() => setShowQR(true)}
            className="btn-secondary w-full mt-4"
          >
            <QrCode className="w-5 h-5" />
            Показать QR-код
          </button>
        </div>
        
        <div className="glass-card">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-3 rounded-xl bg-purple-500/10">
              <Monitor className="w-6 h-6 text-purple-400" />
            </div>
            <div>
              <h3 className="font-semibold">Компьютер</h3>
              <p className="text-sm text-dark-400">Windows, macOS, Linux</p>
            </div>
          </div>
          <ol className="space-y-2 text-sm text-dark-300">
            <li>1. Скачайте AmneziaVPN с amnezia.org</li>
            <li>2. Импортируйте файл конфигурации</li>
            <li>3. Нажмите "Подключить"</li>
          </ol>
          <button
            onClick={handleDownload}
            className="btn-primary w-full mt-4"
          >
            <Download className="w-5 h-5" />
            {t('downloadConfig')}
          </button>
        </div>
      </div>
      
      {/* QR Code Modal */}
      {showQR && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="glass-card max-w-md w-full mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold">{t('scanQR')}</h3>
              <button
                onClick={() => setShowQR(false)}
                className="text-dark-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            {qrData?.data && (
              <div className="bg-white rounded-xl p-4">
                <img
                  src={URL.createObjectURL(qrData.data)}
                  alt="QR Code"
                  className="w-full"
                />
              </div>
            )}
            <p className="text-center text-dark-400 text-sm mt-4">
              {t('qrInstructions')}
            </p>
          </div>
        </div>
      )}
      
      {/* Config File */}
      <div className="glass-card">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <FileCode className="w-5 h-5 text-dark-400" />
            <h3 className="font-semibold">krotvpn.conf</h3>
          </div>
          <div className="flex gap-2">
            <button onClick={handleCopy} className="btn-secondary">
              {copied ? <Check className="w-5 h-5 text-green-400" /> : <Copy className="w-5 h-5" />}
              {copied ? t('copied') : t('copyConfig')}
            </button>
            <button onClick={handleDownload} className="btn-primary">
              <Download className="w-5 h-5" />
              {t('downloadConfig')}
            </button>
          </div>
        </div>
        <pre className="bg-dark-800 rounded-xl p-4 overflow-x-auto text-sm font-mono text-primary-300">
          {config?.config || 'Loading...'}
        </pre>
      </div>
      
      {/* Server Info */}
      {config && (
        <div className="glass-card">
          <h3 className="font-semibold mb-4">Информация о сервере</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-sm text-dark-400">Сервер</p>
              <p className="font-medium">{config.server_name}</p>
            </div>
            <div>
              <p className="text-sm text-dark-400">Локация</p>
              <p className="font-medium">{config.server_location}</p>
            </div>
            <div>
              <p className="text-sm text-dark-400">IP адрес</p>
              <p className="font-mono">{config.address}</p>
            </div>
            <div>
              <p className="text-sm text-dark-400">Создан</p>
              <p className="font-medium">
                {new Date(config.created_at).toLocaleDateString()}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
