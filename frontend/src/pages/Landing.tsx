// FILE: frontend/src/pages/Landing.tsx
// VERSION: 1.3.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Phase-67 public KrotPN splash route with a large unframed logo animation and automatic redirect to /login
//   SCOPE: Splash-only public root route, visible KrotPN brand mark, reduced-motion-aware redirect timing, no marketing/tariff/product content, and no auth/API side effects
//   DEPENDS: M-073 (premium-public-site), M-009 (frontend-user), M-070 (matrix runtime), M-071 (matrix styles), M-074 (responsive-device-adaptation), M-080 (visible-brand-logo-integration)
//   LINKS: M-073, M-080, V-M-073, V-M-080, docs/plans/Phase-67.xml
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   Landing - Splash-only root component that animates the KrotPN logo and redirects to /login
//   BLOCK_SPLASH_REDIRECT - Reduced-motion-aware redirect scheduling
//   BLOCK_LANDING_PAGE - Public root splash rendering
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.3.0 - Replaced the Phase-56 marketing landing with a Phase-67 splash-only logo redirect to /login.
//   LAST_CHANGE: v1.2.0 - Switched public nav to Phase-63 BrandMark while preserving Phase-56 logo regression markers.
//   LAST_CHANGE: v1.1.0 - Added Phase-62 public/auth compactness markers and folded secondary value/proof content.
//   LAST_CHANGE: v1.0.0 - Added Phase-56 premium public entry route without changing backend billing or registration semantics
// END_CHANGE_SUMMARY
//
// START_BLOCK_SPLASH_REDIRECT
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import BrandMark from '../components/BrandMark'

const SPLASH_REDIRECT_DELAY_MS = 1450
const REDUCED_MOTION_REDIRECT_DELAY_MS = 520

function prefersReducedMotion() {
  return Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)
}
// END_BLOCK_SPLASH_REDIRECT

// START_BLOCK_LANDING_PAGE
export default function Landing() {
  const navigate = useNavigate()

  useEffect(() => {
    const delay = prefersReducedMotion() ? REDUCED_MOTION_REDIRECT_DELAY_MS : SPLASH_REDIRECT_DELAY_MS
    const timer = window.setTimeout(() => {
      navigate('/login', { replace: true })
    }, delay)

    return () => window.clearTimeout(timer)
  }, [navigate])

  return (
    <main
      className="matrix-public-page matrix-splash-page"
      data-phase56-public-route="landing"
      data-phase56-logo="true"
      data-phase56-email-proof-copy="phase67-splash-supersedes-visible-copy"
      data-phase62-public-auth="[CompactDeletionAudit][phase62][PUBLIC_AUTH_CLARITY_PRESERVED]"
      data-phase62-collapse="[CompactDeletionAudit][phase62][USER_SURFACES_PRUNED]"
      data-phase67-splash-route="[PremiumPublicSite][phase67][SPLASH_REDIRECT_READY]"
    >
      <section className="matrix-splash-stage" aria-label="KrotPN">
        <BrandMark
          size="lg"
          className="matrix-auth-brand-lockup phase67-auth-logo phase67-splash-logo"
          marker="[VisibleBrandLogo][phase67][LARGE_UNFRAMED_AUTH_LOGO]"
          data-phase56-logo="true"
          data-phase56-legacy-src="/brand/email-logo.png"
          data-phase63-public-auth-logo="landing-splash"
          data-phase67-large-logo="[VisibleBrandLogo][phase67][LOGO_NO_OVERLAP]"
        />
        <div className="matrix-splash-pulse" aria-hidden="true" />
        <p className="sr-only">Переход ко входу в KrotPN</p>
      </section>
    </main>
  )
}
// END_BLOCK_LANDING_PAGE
