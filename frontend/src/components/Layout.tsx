// FILE: frontend/src/components/Layout.tsx
// VERSION: 1.3.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact premium Matrix application layout with phone-safe navigation, user identity, logout, and routed page outlet
//   SCOPE: Desktop Matrix sidebar, mobile top bar, mobile bottom navigation, logout action, Outlet for routed protected user pages
//   DEPENDS: M-009 (frontend-user), M-002 (auth API), M-036 (mobile-user-cabinet), M-038 (compact-ui-system), M-071 (matrix-style-system), M-075 (premium-user-cabinet)
//   LINKS: M-009 (frontend-user), M-036 (mobile-user-cabinet), M-038 (compact-ui-system), M-071, M-075
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   Layout - Compact premium Matrix responsive layout component with desktop sidebar and mobile bars
//   navItems - Route metadata for the compact user cabinet
//   BLOCK_LAYOUT - Layout default export with responsive shell and Phase-57 protected cabinet navigation
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
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
  Shield,
} from 'lucide-react'
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
    <div className="app-shell" data-phase53-layout="user-matrix" data-phase57-layout="premium-user-cabinet">
      <div className="matrix-layout-frame">
        <aside className="matrix-sidebar">
          <div className="matrix-sidebar-header flex items-center gap-3 border-b px-4 py-4">
            <div className="matrix-brand-mark h-10 w-10">
              <Shield className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-lg font-extrabold">{t('appName')}</h1>
              <p className="truncate text-xs muted">Личный кабинет</p>
            </div>
          </div>

          <div className="matrix-sidebar-user border-b px-4 py-3">
            <p className="truncate text-sm font-semibold">{displayName}</p>
            <p className="mt-0.5 truncate text-xs muted">{accountLabel}</p>
          </div>

          <nav className="grid gap-1.5 px-3 py-3">
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
          </nav>

          <div className="matrix-sidebar-footer mt-auto border-t p-3">
            <button onClick={handleLogout} className="btn-secondary min-h-11 w-full justify-start rounded-lg px-3 py-2.5 text-sm">
              <LogOut className="h-4 w-4" />
              {t('logout')}
            </button>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="panel mb-2 flex items-center justify-between gap-3 px-3 py-3 lg:hidden">
            <div className="flex min-w-0 items-center gap-3">
              <div className="matrix-brand-mark h-10 w-10">
                <Shield className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-bold">{t('appName')}</p>
                <p className="truncate text-xs muted">{accountLabel}</p>
              </div>
            </div>
            <button onClick={handleLogout} className="btn-secondary h-10 w-10 shrink-0 rounded-lg p-0" aria-label={t('logout')}>
              <LogOut className="h-4 w-4" />
            </button>
          </header>

          <main className="matrix-main-panel" data-phase57-protected-main="dashboard-routes">
            <div className="p-3 pb-24 sm:p-4 lg:p-5 lg:pb-5">
              <Outlet />
            </div>
          </main>
        </div>

        <nav className="matrix-bottom-nav">
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
