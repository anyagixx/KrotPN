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
    <div className="panel p-5">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div className="rounded-2xl bg-emerald-300/10 p-3 text-emerald-200 ring-1 ring-emerald-200/10">
          {icon}
        </div>
        {trend ? (
          <span className={trend.positive ? 'metric-pill' : 'danger-pill'}>
            {trend.positive ? '+' : ''}
            {trend.value}%
          </span>
        ) : null}
      </div>

      <div className="text-3xl font-extrabold tracking-tight text-white">
        {value}
        {suffix ? <span className="ml-1 text-lg text-cyan-100">{suffix}</span> : null}
      </div>
      <div className="mt-2 text-sm muted">{label}</div>
    </div>
  )
}
