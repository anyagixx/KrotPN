// FILE: frontend-admin/src/components/Layout.tsx
// VERSION: 1.2.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact Matrix admin layout shell with responsive operator navigation, header meta, and route outlet
//   SCOPE: Desktop rail, mobile tab bar, page metadata display, MTProto admin entry, compact admin identity, logout, Phase-54 route-safety markers
//   DEPENDS: M-010 (frontend-admin), M-037 (mobile-admin-console), M-038 (compact-ui-system), M-047 (mtproto-admin-ops), M-070 (matrix-visual-runtime), M-071 (matrix-style-system), auth store, react-router-dom
//   LINKS: M-010, M-037, M-038, M-047, M-070, M-071, Phase-54
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   navItems - Admin navigation menu configuration (route, icon, label, hint)
//   pageMeta - Route-to-title/description mapping for compact header display
//   Layout - Default export: compact admin shell with desktop rail, mobile tab bar, header, and outlet
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v3.4.0 - Phase-54 Matrix admin shell markers and compact route hints for mobile-safe operations.
//   LAST_CHANGE: v3.2.0 - Added Phase-33 compact MTProto admin navigation entry
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.9.0 - Phase-24 compact mobile admin shell with phone-safe navigation and reduced panels
// END_CHANGE_SUMMARY

import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  BarChart3,
  CreditCard,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Server,
  Shield,
  ShieldAlert,
  Users,
} from 'lucide-react'
import { useAuthStore } from '../stores/auth'

// START_BLOCK: navItems
// Navigation menu configuration for desktop rail and mobile tab bar
// Each item: to (route), icon (Lucide), label (display name), hint (tooltip description)
// DEPENDS: react-router-dom NavLink routing
const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Обзор', hint: 'Статус' },
  { to: '/users', icon: Users, label: 'Пользователи', hint: 'Аккаунты' },
  { to: '/devices', icon: ShieldAlert, label: 'Устройства', hint: 'Peer control' },
  { to: '/mtproto', icon: KeyRound, label: 'MTProto', hint: 'Proxy ops' },
  { to: '/analytics', icon: BarChart3, label: 'Аналитика', hint: 'Деньги' },
  { to: '/servers', icon: Server, label: 'Ноды', hint: 'Маршруты' },
  { to: '/plans', icon: CreditCard, label: 'Тарифы', hint: 'Планы' },
]
// END_BLOCK: navItems

// START_BLOCK: pageMeta
// Route-to-page-metadata mapping used in compact header title/description display
// KEY: pathname, VALUE: { title, description }
const pageMeta: Record<string, { title: string; description: string }> = {
  '/': { title: 'Операционный центр', description: 'Здоровье сервиса, подписки, выручка и быстрый доступ к рискам.' },
  '/users': { title: 'Пользователи', description: 'Поиск аккаунтов, роли, статус и последние входы.' },
  '/devices': { title: 'Устройства', description: 'Device-bound peers, сигналы и точечные действия.' },
  '/mtproto': { title: 'MTProto', description: 'Выдачи proxy, runtime health и безопасные reissue/revoke действия.' },
  '/servers': { title: 'Ноды и маршруты', description: 'Entry, exit и route topology.' },
  '/plans': { title: 'Тарифы', description: 'Подписки, лимиты и цены.' },
  '/analytics': { title: 'Аналитика', description: 'Выручка, подписки, рефералы и конверсия.' },
}
// END_BLOCK: pageMeta

// START_BLOCK: Layout
// Compact admin layout component: desktop rail + mobile tab bar + header + route outlet
// DEPENDS: useAuthStore (auth state), react-router-dom (Outlet, NavLink, useLocation, useNavigate)
export default function Layout() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const meta = pageMeta[location.pathname] ?? pageMeta['/']
  const adminRole = user?.role || 'admin'
  const adminInitial = user?.email?.[0]?.toUpperCase() || 'A'

  return (
    <div
      className="app-shell"
      data-phase54-admin-shell="matrix-compact"
      data-log-marker="[MobileAdminConsole][Phase54][ROUTE_VIEWPORT_SAFE]"
    >
      <aside className="admin-rail" aria-label="Admin navigation">
        <div className="brand-mark" aria-label="KrotPN admin">
          <Shield className="h-5 w-5" />
        </div>

        <nav className="rail-nav">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              title={`${item.label}: ${item.hint}`}
              className={({ isActive }) => (isActive ? 'rail-link rail-link-active' : 'rail-link')}
            >
              <item.icon className="h-5 w-5" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <button onClick={handleLogout} className="rail-link rail-logout" title="Выйти">
          <LogOut className="h-5 w-5" />
          <span>Выйти</span>
        </button>
      </aside>

      <div className="admin-content">
        <header className="topbar" data-log-marker="[FrontendAdmin][Phase54][ROUTE_MATRIX_READY]">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase text-emerald-200">
              <span>KrotPN</span>
              <span className="text-slate-600">/</span>
              <span className="truncate">{adminRole}</span>
            </div>
            <h1 className="mt-1 truncate text-xl font-bold text-white sm:text-2xl">{meta.title}</h1>
            <p className="mt-1 line-clamp-2 text-sm muted">{meta.description}</p>
          </div>

          <div className="operator-chip">
            <span className="operator-avatar">{adminInitial}</span>
            <span className="hidden min-w-0 sm:block">
              <span className="block truncate text-sm font-semibold">{user?.email || 'Администратор'}</span>
              <span className="block text-xs muted">{adminRole}</span>
            </span>
          </div>
        </header>

        <main className="admin-main">
          <Outlet />
        </main>
      </div>

      <nav className="mobile-tabbar" aria-label="Mobile admin navigation">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            title={`${item.label}: ${item.hint}`}
            className={({ isActive }) => (isActive ? 'mobile-tab mobile-tab-active' : 'mobile-tab')}
          >
            <item.icon className="h-5 w-5" />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
// END_BLOCK: Layout
