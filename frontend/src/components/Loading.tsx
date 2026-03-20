import { Loader2 } from 'lucide-react'

interface LoadingProps {
  text?: string
}

export default function Loading({ text = 'Loading...' }: LoadingProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <Loader2 className="w-8 h-8 text-primary-500 animate-spin" />
      <p className="mt-4 text-dark-400">{text}</p>
    </div>
  )
}
