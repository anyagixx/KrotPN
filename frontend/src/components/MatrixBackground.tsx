// FILE: frontend/src/components/MatrixBackground.tsx
// VERSION: 1.0.0
// ROLE: UI_COMPONENT
// MAP_MODE: EXPORTS
// START_MODULE_CONTRACT
//   PURPOSE: React Matrix rain canvas runtime for the KrotPN user frontend visual shell
//   SCOPE: Canvas context guards, resize recomputation, pointer influence, reduced-motion fallback, animation lifecycle, and cleanup
//   DEPENDS: M-070 (matrix-visual-runtime), M-071 (matrix-style-system), React
//   LINKS: docs/modules/M-070.xml, docs/verification/V-M-070.xml
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   MatrixBackground - Fixed pointer-events-none Matrix rain canvas component
//   createDrop - Drop state factory for one Matrix column
//   createDrops - Viewport column factory
//   renderStaticMatrixFrame - Reduced-motion and fallback renderer
//   BLOCK_MATRIX_BACKGROUND - Runtime lifecycle, canvas drawing, motion policy, and cleanup
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.0.1 - Strengthened visible Matrix trails for Phase-52 screenshot and mobile viewport checks.
//   LAST_CHANGE: v1.0.0 - Added Phase-52 Matrix canvas runtime with reduced-motion and cleanup guards.
// END_CHANGE_SUMMARY

// START_BLOCK_MATRIX_BACKGROUND
import { useEffect, useRef } from 'react'

type Drop = {
  y: number
  speedY: number
  speedX: number
  delay: number
  started: boolean
}

const CHARS = '01#$%@&*+-=/'
const FONT_SIZE = 10
const LARGE_FONT_SIZE = 14
const TRAIL_LENGTH = 7
const MAX_DPR = 2

function createDrop(): Drop {
  return {
    y: Math.random() * 80,
    speedY: 0.85 + Math.random() * 0.45,
    speedX: 0,
    delay: Math.random() * 700,
    started: false,
  }
}

function resetDrop(drop: Drop) {
  drop.y = -Math.random() * 24
  drop.speedY = 0.85 + Math.random() * 0.45
  drop.speedX = 0
  drop.delay = Math.random() * 700
  drop.started = false
}

function createDrops(width: number): Drop[] {
  const columns = Math.ceil(width / FONT_SIZE)
  return Array.from({ length: columns }, createDrop)
}

function renderStaticMatrixFrame(ctx: CanvasRenderingContext2D, width: number, height: number, drops: Drop[]) {
  ctx.fillStyle = 'rgba(0, 7, 3, 0.86)'
  ctx.fillRect(0, 0, width, height)
  ctx.font = `${FONT_SIZE}px ui-monospace, SFMono-Regular, Menlo, monospace`
  ctx.fillStyle = '#60ff9b'

  for (let i = 0; i < drops.length; i += 3) {
    const x = i * FONT_SIZE
    const rows = Math.ceil(height / (FONT_SIZE * 9))

    for (let row = 0; row < rows; row += 1) {
      const char = CHARS.charAt((i + row) % CHARS.length)
      ctx.fillText(char, x, (row * 9 + 1) * FONT_SIZE)
    }
  }
}

function hasReducedMotion() {
  return Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)
}

export default function MatrixBackground() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) {
      return undefined
    }

    const ctx = canvas.getContext('2d', { alpha: true })
    if (!ctx) {
      canvas.dataset.matrixState = 'context-unavailable'
      console.info('[MatrixVisualRuntime][fallback][CANVAS_CONTEXT_UNAVAILABLE] 2d context unavailable')
      return undefined
    }

    let disposed = false
    let reducedMotion = hasReducedMotion()
    let width = window.innerWidth
    let height = window.innerHeight
    let drops = createDrops(width)
    let lastTime = 0
    let timeElapsed = 0
    let animationFrame: number | null = null
    const mouse: { x: number | null; y: number | null; radius: number } = {
      x: null,
      y: null,
      radius: 28,
    }

    const stopAnimation = () => {
      if (animationFrame !== null) {
        window.cancelAnimationFrame(animationFrame)
        animationFrame = null
      }
      console.info('[MatrixVisualRuntime][cleanup][ANIMATION_STOPPED] matrix animation stopped')
    }

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR)
      width = window.innerWidth
      height = window.innerHeight
      canvas.width = Math.max(1, Math.floor(width * dpr))
      canvas.height = Math.max(1, Math.floor(height * dpr))
      canvas.style.width = `${width}px`
      canvas.style.height = `${height}px`
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      drops = createDrops(width)
      lastTime = 0
      timeElapsed = 0

      if (reducedMotion) {
        renderStaticMatrixFrame(ctx, width, height, drops)
      }

      console.info(`[MatrixVisualRuntime][resize][CANVAS_RESIZE] ${width}x${height}`)
    }

    const draw = (timestamp: number) => {
      if (disposed) {
        animationFrame = null
        return
      }

      if (reducedMotion) {
        renderStaticMatrixFrame(ctx, width, height, drops)
        animationFrame = null
        return
      }

      if (!lastTime) {
        lastTime = timestamp
      }

      const deltaTime = timestamp - lastTime
      lastTime = timestamp
      timeElapsed += deltaTime

      ctx.fillStyle = 'rgba(0, 7, 3, 0.075)'
      ctx.fillRect(0, 0, width, height)

      for (let i = 0; i < drops.length; i += 1) {
        const drop = drops[i]
        const baseX = i * FONT_SIZE

        if (!drop.started && timeElapsed >= drop.delay) {
          drop.started = true
        }

        if (!drop.started) {
          continue
        }

        const isLarge = Math.random() < 0.12
        const x = baseX + drop.speedX
        const y = drop.y * FONT_SIZE

        for (let trail = 0; trail < TRAIL_LENGTH; trail += 1) {
          const trailY = y - trail * FONT_SIZE
          if (trailY < 0 || trailY > height + FONT_SIZE) {
            continue
          }

          const char = CHARS.charAt(Math.floor(Math.random() * CHARS.length))
          const alpha = trail === 0 ? 0.95 : Math.max(0.14, 0.56 - trail * 0.07)

          ctx.globalAlpha = alpha
          ctx.font = `${trail === 0 && isLarge ? LARGE_FONT_SIZE : FONT_SIZE}px ui-monospace, SFMono-Regular, Menlo, monospace`
          ctx.fillStyle = trail === 0 ? '#d8f6e6' : trail % 3 === 0 ? '#68e8ff' : '#60ff9b'
          ctx.fillText(char, x, trailY)
        }

        ctx.globalAlpha = 1

        if (mouse.x !== null && mouse.y !== null) {
          const dx = mouse.x - x
          const dy = mouse.y - y
          const distance = Math.sqrt(dx * dx + dy * dy)

          if (distance > 0 && distance < mouse.radius) {
            const force = (mouse.radius - distance) / mouse.radius
            drop.speedX -= (dx / distance) * force * 4.8
            drop.speedY -= (dy / distance) * force * 2.2
          }
        }

        drop.y += drop.speedY
        drop.speedY += 0.00045
        drop.speedX *= 0.94

        if (y > height || x < -FONT_SIZE || x > width + FONT_SIZE) {
          resetDrop(drop)
        }
      }

      animationFrame = window.requestAnimationFrame(draw)
    }

    const startAnimation = () => {
      if (!reducedMotion && animationFrame === null && !document.hidden) {
        animationFrame = window.requestAnimationFrame(draw)
      }
    }

    const handlePointerMove = (event: PointerEvent) => {
      mouse.x = event.clientX
      mouse.y = event.clientY
    }

    const handleVisibility = () => {
      if (document.hidden) {
        stopAnimation()
      } else if (!reducedMotion) {
        lastTime = 0
        startAnimation()
      }
    }

    const motionQuery = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    const handleMotionChange = (event: MediaQueryListEvent) => {
      reducedMotion = event.matches
      console.info(`[MatrixVisualRuntime][motionPolicy][REDUCED_MOTION] active=${reducedMotion}`)
      stopAnimation()
      if (reducedMotion) {
        renderStaticMatrixFrame(ctx, width, height, drops)
      } else {
        lastTime = 0
        startAnimation()
      }
    }

    canvas.dataset.matrixState = 'ready'
    resize()
    window.addEventListener('resize', resize)
    window.addEventListener('pointermove', handlePointerMove, { passive: true })
    document.addEventListener('visibilitychange', handleVisibility)

    if (motionQuery?.addEventListener) {
      motionQuery.addEventListener('change', handleMotionChange)
    }

    if (reducedMotion) {
      console.info('[MatrixVisualRuntime][motionPolicy][REDUCED_MOTION] active=true')
      renderStaticMatrixFrame(ctx, width, height, drops)
    } else {
      startAnimation()
    }

    console.info('[MatrixVisualRuntime][init][CANVAS_READY] matrix canvas initialized')

    return () => {
      disposed = true
      stopAnimation()
      window.removeEventListener('resize', resize)
      window.removeEventListener('pointermove', handlePointerMove)
      document.removeEventListener('visibilitychange', handleVisibility)
      if (motionQuery?.removeEventListener) {
        motionQuery.removeEventListener('change', handleMotionChange)
      }
    }
  }, [])

  return <canvas ref={canvasRef} className="matrix-canvas" aria-hidden="true" data-matrix-canvas="true" />
}
// END_BLOCK_MATRIX_BACKGROUND
