// FILE: frontend/src/components/Loading.tsx
// VERSION: 1.1.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact Matrix loading spinner component displayed during async operations
//   SCOPE: Simple loading indicator with shield icon and optional text
//   DEPENDS: M-009 (frontend-user), M-071 (matrix-style-system)
//   LINKS: M-009 (frontend-user), M-071
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   Loading - Loading component with spinner and text
//   BLOCK_LOADING - Loading default export (20 lines)
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v3.0.0 - Replaced oversized rounded loading tile with Phase-53 Matrix icon tile
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
      <div className="matrix-icon-tile h-12 w-12">
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
