import { ReactNode } from 'react'

interface Props {
  icon: ReactNode
  label: string
  value: string | number
  suffix?: string
  trend?: { value: number; positive: boolean }
}

export default function StatCard({ icon, label, value, suffix, trend }: Props) {
  return (
    <div className="stat-card">
      <div className="flex items-center justify-between mb-4">
        <div className="p-3 rounded-xl bg-primary-500/10">{icon}</div>
        {trend && (
          <span className={`text-sm ${trend.positive ? 'text-green-400' : 'text-red-400'}`}>
            {trend.positive ? '+' : ''}{trend.value}%
          </span>
        )}
      </div>
      <div className="stat-value">
        {value}{suffix && <span className="text-lg ml-1">{suffix}</span>}
      </div>
      <div className="stat-label">{label}</div>
    </div>
  )
}
