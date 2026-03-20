import { useQuery } from 'react-query'
import { useTranslation } from 'react-i18next'
import { 
  ArrowUp, 
  ArrowDown, 
  Clock, 
  Server, 
  MapPin,
  Shield,
  Zap,
  Calendar
} from 'lucide-react'
import { useAuthStore } from '../stores/auth'
import { vpnApi, userApi } from '../lib/api'
import Loading from '../components/Loading'

export default function Dashboard() {
  const { t } = useTranslation()
  const { user } = useAuthStore()
  
  const { data: vpnStats, isLoading: statsLoading } = useQuery(
    'vpn-stats',
    () => vpnApi.getStats(),
    { refetchInterval: 10000 }
  )
  
  const { data: userStats, isLoading: userStatsLoading } = useQuery(
    'user-stats',
    () => userApi.getStats()
  )
  
  if (statsLoading || userStatsLoading) {
    return <Loading text={t('loading')} />
  }
  
  const stats = vpnStats?.data
  const uStats = userStats?.data
  
  return (
    <div className="space-y-8 animate-in">
      {/* Welcome */}
      <div>
        <h1 className="text-3xl font-bold">
          {t('welcome')}, <span className="gradient-text">{user?.display_name || 'User'}</span>!
        </h1>
        <p className="text-dark-400 mt-2">
          Управляйте своим VPN подключением
        </p>
      </div>
      
      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Connection Status */}
        <div className="glass-card">
          <div className="flex items-center justify-between mb-4">
            <span className="text-dark-400">{t('status')}</span>
            <div className={`w-3 h-3 rounded-full ${stats?.is_connected ? 'bg-green-500 animate-pulse' : 'bg-dark-500'}`} />
          </div>
          <div className="flex items-center gap-3">
            <div className={`p-3 rounded-xl ${stats?.is_connected ? 'bg-green-500/10' : 'bg-dark-700'}`}>
              <Shield className={`w-6 h-6 ${stats?.is_connected ? 'text-green-400' : 'text-dark-400'}`} />
            </div>
            <div>
              <p className="font-semibold">
                {stats?.is_connected ? t('connected') : t('disconnected')}
              </p>
              <p className="text-sm text-dark-400">
                {stats?.server_location || '—'}
              </p>
            </div>
          </div>
        </div>
        
        {/* Subscription */}
        <div className="glass-card">
          <div className="flex items-center justify-between mb-4">
            <span className="text-dark-400">{t('subscription')}</span>
            <Calendar className="w-5 h-5 text-dark-400" />
          </div>
          <div className="flex items-center gap-3">
            <div className={`p-3 rounded-xl ${uStats?.has_active_subscription ? 'bg-primary-500/10' : 'bg-red-500/10'}`}>
              <Zap className={`w-6 h-6 ${uStats?.has_active_subscription ? 'text-primary-400' : 'text-red-400'}`} />
            </div>
            <div>
              <p className="font-semibold">
                {uStats?.has_active_subscription 
                  ? `${uStats.subscription_days_left} ${t('daysLeft')}`
                  : t('subscriptionExpired')
                }
              </p>
              <p className="text-sm text-dark-400">
                {uStats?.has_active_subscription ? t('subscriptionActive') : 'Продлите подписку'}
              </p>
            </div>
          </div>
        </div>
        
        {/* Upload */}
        <div className="glass-card">
          <div className="flex items-center justify-between mb-4">
            <span className="text-dark-400">{t('upload')}</span>
            <ArrowUp className="w-5 h-5 text-green-400" />
          </div>
          <p className="text-2xl font-bold">{stats?.total_upload_formatted || '0 B'}</p>
          <p className="text-sm text-dark-400 mt-1">{t('traffic')}</p>
        </div>
        
        {/* Download */}
        <div className="glass-card">
          <div className="flex items-center justify-between mb-4">
            <span className="text-dark-400">{t('download')}</span>
            <ArrowDown className="w-5 h-5 text-blue-400" />
          </div>
          <p className="text-2xl font-bold">{stats?.total_download_formatted || '0 B'}</p>
          <p className="text-sm text-dark-400 mt-1">{t('traffic')}</p>
        </div>
      </div>
      
      {/* Server Info */}
      <div className="glass-card">
        <h2 className="text-lg font-semibold mb-4">{t('server')}</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="flex items-center gap-3">
            <Server className="w-5 h-5 text-dark-400" />
            <div>
              <p className="text-sm text-dark-400">{t('server')}</p>
              <p className="font-medium">{stats?.server_name || '—'}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <MapPin className="w-5 h-5 text-dark-400" />
            <div>
              <p className="text-sm text-dark-400">{t('location')}</p>
              <p className="font-medium">{stats?.server_location || '—'}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Clock className="w-5 h-5 text-dark-400" />
            <div>
              <p className="text-sm text-dark-400">{t('lastConnection')}</p>
              <p className="font-medium">
                {stats?.last_handshake_at 
                  ? new Date(stats.last_handshake_at).toLocaleString()
                  : '—'
                }
              </p>
            </div>
          </div>
        </div>
      </div>
      
      {/* Quick Actions */}
      <div className="glass-card">
        <h2 className="text-lg font-semibold mb-4">Быстрые действия</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <a href="/config" className="btn-secondary py-4">
            <Shield className="w-5 h-5" />
            Скачать конфиг
          </a>
          <a href="/subscription" className="btn-primary py-4">
            <Zap className="w-5 h-5" />
            Продлить подписку
          </a>
          <a href="/referrals" className="btn-secondary py-4">
            <span className="text-lg">🎁</span>
            Пригласить друга
          </a>
        </div>
      </div>
    </div>
  )
}
