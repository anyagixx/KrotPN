// FILE: frontend/src/components/Loading.tsx
// VERSION: 1.0.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Loading spinner component displayed during async operations
//   SCOPE: Simple loading indicator with shield icon and optional text
//   DEPENDS: M-009 (frontend-user)
//   LINKS: M-009 (frontend-user)
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   Loading - Loading component with spinner and text
//   BLOCK_LOADING - Loading default export (20 lines)
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY
//
// START_BLOCK_LOADING
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
// END_BLOCK_LOADING
