import { useState } from 'react'
import { useQuery } from 'react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts'
import { adminApi } from '../lib/api'

export default function Analytics() {
  const [period, setPeriod] = useState(30)
  
  const { data: revenueData } = useQuery(
    ['revenue-analytics', period],
    () => adminApi.getRevenueAnalytics(period)
  )
  
  const { data: usersData } = useQuery(
    ['users-analytics', period],
    () => adminApi.getUsersAnalytics(period)
  )
  
  const { data: billingStats } = useQuery('billing-stats', () => adminApi.getBillingStats())
  const { data: referralStats } = useQuery('referral-stats', () => adminApi.getReferralStats())
  
  const revenue = revenueData?.data?.daily || []
  const users = usersData?.data?.daily || []
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Аналитика</h1>
          <p className="text-gray-400 mt-1">Статистика и отчёты</p>
        </div>
        <select 
          value={period}
          onChange={(e) => setPeriod(Number(e.target.value))}
          className="input w-40"
        >
          <option value={7}>7 дней</option>
          <option value={30}>30 дней</option>
          <option value={90}>90 дней</option>
          <option value={365}>Год</option>
        </select>
      </div>
      
      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="stat-card">
          <h3 className="font-semibold mb-4">Выручка</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={revenue}>
              <XAxis dataKey="date" tick={{ fill: '#9ca3af', fontSize: 12 }} />
              <YAxis tick={{ fill: '#9ca3af', fontSize: 12 }} />
              <Tooltip 
                contentStyle={{ background: '#1e293b', border: 'none', borderRadius: 8 }}
                labelStyle={{ color: '#fff' }}
              />
              <Bar dataKey="revenue" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        
        <div className="stat-card">
          <h3 className="font-semibold mb-4">Регистрации</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={users}>
              <XAxis dataKey="date" tick={{ fill: '#9ca3af', fontSize: 12 }} />
              <YAxis tick={{ fill: '#9ca3af', fontSize: 12 }} />
              <Tooltip 
                contentStyle={{ background: '#1e293b', border: 'none', borderRadius: 8 }}
                labelStyle={{ color: '#fff' }}
              />
              <Line type="monotone" dataKey="count" stroke="#10b981" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="stat-card">
          <h3 className="font-semibold mb-4">Подписки</h3>
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-400">Активных</span>
              <span className="font-bold">{billingStats?.data?.active_subscriptions || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Триальных</span>
              <span className="font-bold">{billingStats?.data?.trial_subscriptions || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Истекло за месяц</span>
              <span className="font-bold">{billingStats?.data?.expired_this_month || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Выручка за месяц</span>
              <span className="font-bold text-green-400">{billingStats?.data?.revenue_this_month?.toLocaleString() || 0} ₽</span>
            </div>
          </div>
        </div>
        
        <div className="stat-card">
          <h3 className="font-semibold mb-4">Рефералы</h3>
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-400">Всего кодов</span>
              <span className="font-bold">{referralStats?.data?.total_codes || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Рефералов</span>
              <span className="font-bold">{referralStats?.data?.total_referrals || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Оплативших</span>
              <span className="font-bold">{referralStats?.data?.paid_referrals || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Конверсия</span>
              <span className="font-bold">{referralStats?.data?.conversion_rate || 0}%</span>
            </div>
          </div>
        </div>
        
        <div className="stat-card">
          <h3 className="font-semibold mb-4">Конверсия</h3>
          <div className="flex items-center justify-center h-32">
            <div className="text-center">
              <p className="text-4xl font-bold text-primary-400">
                {billingStats?.data?.trial_subscriptions > 0 
                  ? Math.round((billingStats?.data?.active_subscriptions / billingStats?.data?.trial_subscriptions) * 100)
                  : 0}%
              </p>
              <p className="text-gray-400 mt-2">Trial → Paid</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
