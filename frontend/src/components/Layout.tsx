// FILE: frontend/src/components/Layout.tsx
// VERSION: 1.9.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact premium Matrix application layout with phone/tablet-safe navigation, visible KrotPN logo, user identity, logout, and routed page outlet
//   SCOPE: Desktop Matrix sidebar, mobile top bar, touch-aware mobile bottom navigation, visible Phase-63 brand mark, logout action under Settings, safe-area responsive markers, Outlet for routed protected user pages
//   DEPENDS: M-009 (frontend-user), M-002 (auth API), M-036 (mobile-user-cabinet), M-038 (compact-ui-system), M-071 (matrix-style-system), M-074 (responsive-device-adaptation), M-075 (premium-user-cabinet), M-080 (visible-brand-logo-integration)
//   LINKS: M-009 (frontend-user), M-036 (mobile-user-cabinet), M-038 (compact-ui-system), M-071, M-074, M-075, M-080, Phase-63
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   Layout - Compact premium Matrix responsive layout component with desktop sidebar, mobile bars, visible Phase-63 logo, Phase-72 logout placement, and Phase-61 responsive markers
//   navItems - Route metadata for the compact user cabinet
//   BLOCK_LAYOUT - Layout default export with responsive shell and Phase-57 protected cabinet navigation
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.9.0 - Moved desktop logout directly under Settings and added Phase-72 mobile dock markers.
//   LAST_CHANGE: v1.8.0 - Added Phase-71 localized user-shell subtitle and final frameless logo marker.
//   LAST_CHANGE: v1.7.0 - Applied Phase-68 frameless user-shell logo styling without changing brand assets or navigation.
//   LAST_CHANGE: v1.6.0 - Added Phase-63 visible KrotPN logo marks to desktop and mobile protected user shell without changing navigation.
//   LAST_CHANGE: v1.5.0 - Added Phase-61 phone/tablet responsive shell, safe-area, and protected-route static proof markers.
//   LAST_CHANGE: v1.4.0 - Added Phase-57 premium user cabinet layout markers and compact protected-route shell ownership
//   LAST_CHANGE: v1.3.1 - Moved user cabinet navigation to /dashboard routes and kept dashboard active state exact for Phase-56 public landing
//   LAST_CHANGE: v3.0.0 - Reworked protected user shell into Phase-53 compact Matrix navigation surfaces
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.9.0 - Reworked user cabinet shell into compact mobile-first navigation for Phase-23
// END_CHANGE_SUMMARY
//
// START_BLOCK_LAYOUT
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  CreditCard,
  FileCode,
  Gift,
  LayoutDashboard,
  LogOut,
  Settings,
} from 'lucide-react'
import BrandMark from './BrandMark'
import { useAuthStore } from '../stores/auth'

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, labelKey: 'dashboard' },
  { to: '/dashboard/config', icon: FileCode, labelKey: 'config' },
  { to: '/dashboard/subscription', icon: CreditCard, labelKey: 'subscription' },
  { to: '/dashboard/referrals', icon: Gift, labelKey: 'referrals' },
  { to: '/dashboard/settings', icon: Settings, labelKey: 'settings' },
]

export default function Layout() {
  const { t } = useTranslation()
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const displayName = user?.display_name || user?.email || 'Пользователь'
  const accountLabel = user?.email || 'Private account'

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="app-shell" data-phase53-layout="user-matrix" data-phase57-layout="premium-user-cabinet" data-phase61-layout="phone-tablet-safe">
      <div className="matrix-layout-frame" data-phase61-viewport-frame="[ResponsiveAdaptation][phase61][VIEWPORT_MATRIX_READY]">
        <aside className="matrix-sidebar">
          <div className="matrix-sidebar-header flex items-center gap-3 border-b px-4 py-4">
            <BrandMark
              size="md"
              className="phase68-shell-logo h-10 w-10"
              marker="[VisibleBrandLogo][phase63][USER_SHELL_LOGO_SAFE]"
              data-phase63-user-shell-logo="desktop"
              data-phase68-user-shell-logo="frameless"
            />
            <div className="min-w-0">
              <h1 className="truncate text-lg font-extrabold">{t('appName')}</h1>
              <p className="truncate text-xs muted">{t('personalCabinet')}</p>
            </div>
          </div>

          <div className="matrix-sidebar-user border-b px-4 py-3">
            <p className="truncate text-sm font-semibold">{displayName}</p>
            <p className="mt-0.5 truncate text-xs muted">{accountLabel}</p>
          </div>

          <nav className="grid gap-1.5 px-3 py-3" data-phase72-desktop-nav="[PremiumUserCabinet][phase72][LOGOUT_UNDER_SETTINGS]">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  [
                    'matrix-nav-link',
                    isActive ? 'matrix-nav-link-active' : 'matrix-nav-link-idle',
                  ].join(' ')
                }
                end={item.to === '/dashboard'}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                <span className="min-w-0 truncate font-semibold">{t(item.labelKey)}</span>
              </NavLink>
            ))}
            <button
              onClick={handleLogout}
              className="matrix-nav-link matrix-nav-link-idle motion-interactive mt-1 w-full justify-start"
              data-phase72-desktop-logout="[PremiumUserCabinet][phase72][DESKTOP_LOGOUT_VISIBLE]"
            >
              <LogOut className="h-4 w-4 shrink-0" />
              <span className="min-w-0 truncate font-semibold">{t('logout')}</span>
            </button>
          </nav>

          <div className="matrix-sidebar-footer mt-auto border-t p-3" />
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="panel mb-2 flex items-center justify-between gap-3 px-3 py-3 lg:hidden" data-phase61-mobile-header="safe-area-compact">
            <div className="flex min-w-0 items-center gap-3">
              <BrandMark
                size="md"
                className="phase68-shell-logo h-10 w-10"
                marker="[VisibleBrandLogo][phase63][USER_SHELL_LOGO_SAFE]"
                data-phase63-user-shell-logo="mobile"
                data-phase68-user-shell-logo="frameless"
              />
              <div className="min-w-0">
                <p className="truncate text-sm font-bold">{t('appName')}</p>
                <p className="truncate text-xs muted">{accountLabel}</p>
              </div>
            </div>
            <button onClick={handleLogout} className="btn-secondary h-10 w-10 shrink-0 rounded-lg p-0" aria-label={t('logout')}>
              <LogOut className="h-4 w-4" />
            </button>
          </header>

          <main className="matrix-main-panel" data-phase57-protected-main="dashboard-routes" data-phase61-protected-user-static="[ResponsiveAdaptation][phase61][PROTECTED_USER_STATIC_PROOF]">
            <div className="p-3 pb-24 sm:p-4 lg:p-5 lg:pb-5">
              <Outlet />
            </div>
          </main>
        </div>

        <nav
          className="matrix-bottom-nav phase72-touch-dock"
          data-phase61-mobile-nav="[ResponsiveAdaptation][phase61][SAFE_AREA_PASS]"
          data-phase72-mobile-nav="[MobileUserCabinet][phase72][BOTTOM_NAV_SAFE]"
          data-phase72-touch-nav="[MatrixMotion][phase72][TOUCH_NAV_REVEAL_SAFE]"
        >
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/dashboard'}
              className={({ isActive }) =>
                [
                  'flex min-h-12 min-w-0 flex-col items-center justify-center gap-1 rounded-lg px-1 text-[10px] font-semibold transition',
                  isActive ? 'matrix-nav-link-active' : 'matrix-nav-link-idle',
                ].join(' ')
              }
            >
              <item.icon className="h-4 w-4 shrink-0" />
              <span className="max-w-full truncate">{t(item.labelKey)}</span>
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  )
}
// END_BLOCK_LAYOUT
