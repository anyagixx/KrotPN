// FILE: frontend/src/components/VisualShell.tsx
// VERSION: 1.0.0
// ROLE: UI_COMPONENT
// MAP_MODE: EXPORTS
// START_MODULE_CONTRACT
//   PURPOSE: Root visual shell that mounts Matrix runtime and CRT overlays behind the user frontend
//   SCOPE: MatrixBackground, scanline overlay, vignette overlay, and content z-index boundary
//   DEPENDS: M-070 (matrix-visual-runtime), M-071 (matrix-style-system), React
//   LINKS: docs/modules/M-070.xml, docs/modules/M-071.xml
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   VisualShell - Wraps routed user frontend content with Matrix visual layers
//   default - React component default export
//   BLOCK_VISUAL_SHELL - Visual shell markup and layer ordering
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.0.0 - Added Phase-52 Matrix visual shell for user frontend route tree.
// END_CHANGE_SUMMARY

// START_BLOCK_VISUAL_SHELL
import type { ReactNode } from 'react'
import MatrixBackground from './MatrixBackground'

type VisualShellProps = {
  children: ReactNode
}

export default function VisualShell({ children }: VisualShellProps) {
  return (
    <div className="matrix-visual-shell">
      <MatrixBackground />
      <div className="matrix-scanline-overlay" aria-hidden="true" />
      <div className="matrix-vignette" aria-hidden="true" />
      <div className="matrix-visual-content">{children}</div>
    </div>
  )
}
// END_BLOCK_VISUAL_SHELL
