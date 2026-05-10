// FILE: frontend/src/components/Layout.tsx
// VERSION: 1.1.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact application layout with phone-safe navigation, user identity, logout, and routed page outlet
//   SCOPE: Desktop compact sidebar, mobile top bar, mobile bottom navigation, logout action, Outlet for routed pages
//   DEPENDS: M-009 (frontend-user), M-002 (auth API), M-036 (mobile-user-cabinet), M-038 (compact-ui-system)
//   LINKS: M-009 (frontend-user), M-036 (mobile-user-cabinet), M-038 (compact-ui-system)
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   Layout - Compact responsive layout component with desktop sidebar and mobile bars
//   navItems - Route metadata for the compact user cabinet
//   BLOCK_LAYOUT - Layout default export with responsive shell and navigation
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
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
  { to: '/', icon: LayoutDashboard, labelKey: 'dashboard' },
  { to: '/config', icon: FileCode, labelKey: 'config' },
  { to: '/subscription', icon: CreditCard, labelKey: 'subscription' },
  { to: '/referrals', icon: Gift, labelKey: 'referrals' },
  { to: '/settings', icon: Settings, labelKey: 'settings' },
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
    <div className="app-shell">
      <div className="mx-auto flex min-h-[calc(100vh-1rem)] max-w-[1180px] gap-3 lg:min-h-[calc(100vh-2rem)]">
        <aside className="panel hidden w-64 shrink-0 flex-col overflow-hidden lg:flex">
          <div className="flex items-center gap-3 border-b border-white/5 px-4 py-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-300/12 text-emerald-200 ring-1 ring-emerald-200/12">
              <Shield className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-lg font-extrabold">{t('appName')}</h1>
              <p className="truncate text-xs muted">Личный кабинет</p>
            </div>
          </div>

          <div className="border-b border-white/5 px-4 py-3">
            <p className="truncate text-sm font-semibold">{displayName}</p>
            <p className="mt-0.5 truncate text-xs muted">{accountLabel}</p>
          </div>

          <nav className="grid gap-1.5 px-3 py-3">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  [
                    'group flex min-h-11 items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition',
                    isActive
                      ? 'bg-emerald-300/12 text-emerald-100 ring-1 ring-emerald-200/12'
                      : 'text-slate-300 hover:bg-white/5 hover:text-white',
                  ].join(' ')
                }
              >
                <item.icon className="h-4 w-4 shrink-0" />
                <span className="min-w-0 truncate font-semibold">{t(item.labelKey)}</span>
              </NavLink>
            ))}
          </nav>

          <div className="mt-auto border-t border-white/5 p-3">
            <button onClick={handleLogout} className="btn-secondary min-h-11 w-full justify-start rounded-xl px-3 py-2.5 text-sm">
              <LogOut className="h-4 w-4" />
              {t('logout')}
            </button>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="panel mb-3 flex items-center justify-between gap-3 px-3 py-3 lg:hidden">
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-300/12 text-emerald-200">
                <Shield className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-bold">{t('appName')}</p>
                <p className="truncate text-xs muted">{accountLabel}</p>
              </div>
            </div>
            <button onClick={handleLogout} className="btn-secondary h-10 w-10 shrink-0 rounded-xl p-0" aria-label={t('logout')}>
              <LogOut className="h-4 w-4" />
            </button>
          </header>

          <main className="panel min-w-0 flex-1 overflow-hidden">
            <div className="p-3 pb-24 sm:p-4 lg:p-5 lg:pb-5">
              <Outlet />
            </div>
          </main>
        </div>

        <nav className="fixed inset-x-3 bottom-3 z-40 grid grid-cols-5 rounded-2xl border border-white/10 bg-slate-950/95 p-1.5 shadow-[0_16px_40px_rgba(2,10,14,0.4)] backdrop-blur lg:hidden">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                [
                  'flex min-h-12 min-w-0 flex-col items-center justify-center gap-1 rounded-xl px-1 text-[10px] font-semibold transition',
                  isActive ? 'bg-emerald-300/10 text-emerald-100' : 'text-slate-400 hover:text-white',
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
