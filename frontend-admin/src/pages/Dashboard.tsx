import { useQuery } from 'react-query'
import { Users, CreditCard, DollarSign, Server, TrendingUp, Activity } from 'lucide-react'
import { adminApi } from '../lib/api'
import StatCard from '../components/StatCard'

export default function Dashboard() {
  const { data: stats, isLoading } = useQuery('admin-stats', () => adminApi.getStats())
  const { data: health } = useQuery('system-health', () => adminApi.getSystemHealth())
  
  const s = stats?.data
  
  if (isLoading) return <div className="text-center py-12">Загрузка...</div>
  
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-gray-400 mt-1">Обзор системы KrotVPN</p>
      </div>
      
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<Users className="w-6 h-6 text-primary-400" />}
          label="Всего пользователей"
          value={s?.users?.total || 0}
        />
        <StatCard
          icon={<CreditCard className="w-6 h-6 text-green-400" />}
          label="Активных подписок"
          value={s?.subscriptions?.active || 0}
        />
        <StatCard
          icon={<DollarSign className="w-6 h-6 text-yellow-400" />}
          label="Выручка за месяц"
          value={s?.revenue?.this_month?.toLocaleString() || 0}
          suffix="₽"
        />
        <StatCard
          icon={<Server className="w-6 h-6 text-blue-400" />}
          label="Онлайн серверов"
          value={s?.vpn?.online_servers || 0}
        />
      </div>
      
      {/* Secondary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="stat-card">
          <div className="flex items-center gap-3 mb-4">
            <TrendingUp className="w-5 h-5 text-green-400" />
            <span className="text-gray-400">Новых за месяц</span>
          </div>
          <p className="text-2xl font-bold">{s?.users?.new_this_month || 0}</p>
        </div>
        
        <div className="stat-card">
          <div className="flex items-center gap-3 mb-4">
            <CreditCard className="w-5 h-5 text-purple-400" />
            <span className="text-gray-400">Триальных подписок</span>
          </div>
          <p className="text-2xl font-bold">{s?.subscriptions?.trial || 0}</p>
        </div>
        
        <div className="stat-card">
          <div className="flex items-center gap-3 mb-4">
            <Activity className="w-5 h-5 text-blue-400" />
            <span className="text-gray-400">Активных VPN клиентов</span>
          </div>
          <p className="text-2xl font-bold">{s?.vpn?.active_clients || 0}</p>
        </div>
      </div>
      
      {/* System Health */}
      {health?.data && (
        <div className="stat-card">
          <h3 className="font-semibold mb-4">Состояние системы</h3>
          <div className="grid grid-cols-3 gap-6">
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-gray-400">CPU</span>
                <span>{health.data.cpu_percent}%</span>
              </div>
              <div className="h-2 bg-dark-700 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-blue-500 rounded-full transition-all"
                  style={{ width: `${health.data.cpu_percent}%` }}
                />
              </div>
            </div>
            
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-gray-400">RAM</span>
                <span>{health.data.memory.percent}%</span>
              </div>
              <div className="h-2 bg-dark-700 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-purple-500 rounded-full transition-all"
                  style={{ width: `${health.data.memory.percent}%` }}
                />
              </div>
            </div>
            
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-gray-400">Диск</span>
                <span>{health.data.disk.percent}%</span>
              </div>
              <div className="h-2 bg-dark-700 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-green-500 rounded-full transition-all"
                  style={{ width: `${health.data.disk.percent}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
