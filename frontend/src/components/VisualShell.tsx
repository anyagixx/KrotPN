// FILE: frontend/src/components/VisualShell.tsx
// VERSION: 1.2.0
// ROLE: UI_COMPONENT
// MAP_MODE: EXPORTS
// START_MODULE_CONTRACT
//   PURPOSE: Root visual shell that mounts Matrix runtime, CSS rain fallback, CRT overlays, and Phase-59 route motion behind the user frontend
//   SCOPE: MatrixBackground, CSS fallback rain layer, scanline overlay, vignette overlay, content z-index boundary, route entrance markers, and pointer/focus safety markers
//   DEPENDS: M-070 (matrix-visual-runtime), M-071 (matrix-style-system), M-077 (matrix-motion-interactions), React
//   LINKS: docs/modules/M-070.xml, docs/modules/M-071.xml, docs/modules/M-077.xml, docs/plans/Phase-59.xml
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   VisualShell - Wraps routed user frontend content with Matrix visual layers and CSS rain fallback
//   default - React component default export
//   BLOCK_VISUAL_SHELL - Visual shell markup and layer ordering
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.2.0 - Moved route transform animation off the root shell and added a CSS rain fallback layer.
//   LAST_CHANGE: v1.1.0 - Added Phase-59 route motion and reduced-motion/pointer/focus safety markers.
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
    <div
      className="matrix-visual-shell"
      data-phase59-motion-budget="[MatrixMotion][phase59][MOTION_BUDGET_READY]"
      data-phase59-route-transition="[MatrixMotion][phase59][ROUTE_TRANSITIONS_FAST]"
      data-phase59-reduced-motion="[MatrixMotion][phase59][REDUCED_MOTION_PASS]"
      data-phase59-pointer-scroll="[MatrixMotion][phase59][POINTER_SCROLL_SAFE]"
      data-phase59-keyboard-focus="[MatrixMotion][phase59][KEYBOARD_FOCUS_SAFE]"
    >
      <MatrixBackground />
      <div className="matrix-rain-fallback" aria-hidden="true" data-matrix-rain-fallback="[MatrixVisualRuntime][fix][CSS_RAIN_FALLBACK_READY]" />
      <div className="matrix-scanline-overlay" aria-hidden="true" />
      <div className="matrix-vignette" aria-hidden="true" />
      <div className="matrix-visual-content motion-safe-layer motion-route-enter">{children}</div>
    </div>
  )
}
// END_BLOCK_VISUAL_SHELL
