import { Loader2, Shield } from 'lucide-react'

interface LoadingProps {
  text?: string
}

export default function Loading({ text = 'Loading...' }: LoadingProps) {
  return (
    <div className="empty-state">
      <div className="rounded-[28px] bg-emerald-300/12 p-4 text-emerald-200">
        <Shield className="h-8 w-8" />
      </div>
      <Loader2 className="h-8 w-8 animate-spin text-cyan-100" />
      <div>
        <p className="text-lg font-semibold">Подготавливаем данные</p>
        <p className="mt-1 text-sm muted">{text}</p>
      </div>
    </div>
  )
}
