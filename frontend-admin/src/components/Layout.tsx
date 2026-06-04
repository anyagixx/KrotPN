// FILE: frontend-admin/src/components/Layout.tsx
// VERSION: 1.7.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact Matrix admin layout shell with phone/tablet-safe operator navigation, visible KrotPN logo, bounded scroll surfaces, header meta, route outlet, and Phase-75 single Users inventory navigation
//   SCOPE: Desktop rail without visible admin tariffs or separate Devices section, mobile tab bar, visible Phase-63 brand mark, page metadata display, MTProto admin entry, compact admin identity, logout under Nodes, Phase-54 route-safety markers, Phase-58 protected route shell, Phase-61 responsive static proof markers, Phase-74 bounded scroll markers, and Phase-75 unified Users/Devices navigation
//   DEPENDS: M-010 (frontend-admin), M-037 (mobile-admin-console), M-038 (compact-ui-system), M-047 (mtproto-admin-ops), M-070 (matrix-visual-runtime), M-071 (matrix-style-system), M-074 (responsive-device-adaptation), M-076 (premium-admin-cockpit), M-080 (visible-brand-logo-integration), auth store, react-router-dom
//   LINKS: M-010, M-037, M-038, M-047, M-070, M-071, M-074, M-076, M-080, Phase-54, Phase-58, Phase-61, Phase-63, Phase-74, Phase-75
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   navItems - Admin navigation menu configuration without the Phase-74-retired Tariffs section and Phase-75-retired visible Devices section
//   pageMeta - Route-to-title/description mapping for compact header display
//   Layout - Default export: compact admin shell with desktop rail, mobile tab bar, visible Phase-63 logo, header, outlet, Phase-61 responsive markers, Phase-74 scroll/nav markers, and Phase-75 single Users navigation
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v3.9.0 - Phase-75 removed the visible Devices navigation item because device controls now live inside Users.
//   LAST_CHANGE: v3.8.0 - Phase-74 removed visible admin Tariffs navigation, placed logout directly under Nodes, and marked bounded scroll surfaces.
//   LAST_CHANGE: v3.7.0 - Added Phase-63 visible KrotPN logo marks to desktop rail and mobile admin topbar without changing route controls.
//   LAST_CHANGE: v3.6.0 - Added Phase-61 phone/tablet responsive admin shell, safe-area, and static route proof markers.
//   LAST_CHANGE: v3.5.0 - Phase-58 marked the admin shell as premium cockpit routes with compact main density and protected route evidence.
//   LAST_CHANGE: v3.4.0 - Phase-54 Matrix admin shell markers and compact route hints for mobile-safe operations.
//   LAST_CHANGE: v3.2.0 - Added Phase-33 compact MTProto admin navigation entry
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.9.0 - Phase-24 compact mobile admin shell with phone-safe navigation and reduced panels
// END_CHANGE_SUMMARY

import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  BarChart3,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Server,
  Users,
} from 'lucide-react'
import BrandMark from './BrandMark'
import { useAuthStore } from '../stores/auth'

// START_BLOCK: navItems
// Navigation menu configuration for desktop rail and mobile tab bar
// Each item: to (route), icon (Lucide), label (display name), hint (tooltip description)
// DEPENDS: react-router-dom NavLink routing
const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Обзор', hint: 'Статус' },
  { to: '/users', icon: Users, label: 'Пользователи', hint: 'Аккаунты' },
  { to: '/mtproto', icon: KeyRound, label: 'MTProto', hint: 'Proxy ops' },
  { to: '/analytics', icon: BarChart3, label: 'Аналитика', hint: 'Деньги' },
  { to: '/servers', icon: Server, label: 'Ноды', hint: 'Маршруты' },
]
// END_BLOCK: navItems

// START_BLOCK: pageMeta
// Route-to-page-metadata mapping used in compact header title/description display
// KEY: pathname, VALUE: { title, description }
const pageMeta: Record<string, { title: string; description: string }> = {
  '/': { title: 'Операционный центр', description: 'Здоровье сервиса, подписки, выручка и быстрый доступ к рискам.' },
  '/users': { title: 'Пользователи', description: 'Поиск аккаунтов, роли, статусы и устройства пользователя.' },
  '/mtproto': { title: 'MTProto', description: 'Выдачи proxy, runtime health и безопасные reissue/revoke действия.' },
  '/servers': { title: 'Ноды и маршруты', description: 'Entry, exit и route topology.' },
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
      data-phase58-admin-shell="premium-cockpit"
      data-phase58-routes="[PremiumAdminCockpit][phase58][ROUTES_READY]"
      data-phase58-reduced-motion="[PremiumAdminCockpit][phase58][REDUCED_MOTION_SAFE]"
      data-phase61-layout="phone-tablet-safe"
      data-phase61-viewport-frame="[ResponsiveAdaptation][phase61][VIEWPORT_MATRIX_READY]"
      data-phase74-admin-shell="[FrontendAdmin][phase74][NO_TARIFFS_NAV]"
      data-phase74-scroll-pointer="[MatrixMotion][phase74][SCROLL_POINTER_SAFE]"
      data-phase75-admin-shell="[FrontendAdmin][phase75][NO_DEVICES_NAV]"
      data-log-marker="[MobileAdminConsole][Phase54][ROUTE_VIEWPORT_SAFE]"
    >
      <aside className="admin-rail" aria-label="Admin navigation" data-phase74-admin-rail="[ResponsiveAdaptation][phase74][ADMIN_RAIL_VIEWPORT_SAFE]">
        <BrandMark
          size="md"
          className="brand-mark"
          marker="[VisibleBrandLogo][phase63][ADMIN_SHELL_LOGO_SAFE]"
          data-phase63-admin-shell-logo="rail"
        />

        <nav
          className="rail-nav"
          data-phase74-nav-order="[PremiumAdminCockpit][phase74][LOGOUT_UNDER_NODES]"
          data-phase75-nav="[PremiumAdminCockpit][phase75][DEVICES_NAV_REMOVED]"
        >
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

        <button
          onClick={handleLogout}
          className="rail-link rail-logout"
          title="Выйти"
          data-phase74-desktop-logout="[MobileAdminConsole][phase74][ADMIN_LOGOUT_UNDER_NODES]"
          data-phase74-nav-motion="[MatrixMotion][phase74][ADMIN_NAV_MOTION_SAFE]"
        >
          <LogOut className="h-5 w-5" />
          <span>Выйти</span>
        </button>
      </aside>

      <div className="admin-content" data-phase74-content-scroll="[PremiumAdminCockpit][phase74][CONTENT_SCROLL_REPAIRED]">
        <header className="topbar" data-phase61-mobile-header="safe-area-compact" data-log-marker="[FrontendAdmin][Phase54][ROUTE_MATRIX_READY]">
          <div className="min-w-0">
            <div className="flex min-w-0 items-center gap-2 text-xs font-semibold uppercase text-emerald-200">
              <BrandMark
                size="sm"
                className="topbar-brand-mark"
                marker="[VisibleBrandLogo][phase63][ADMIN_SHELL_LOGO_SAFE]"
                data-phase63-admin-shell-logo="topbar"
              />
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

        <main
          className="phase58-cockpit-main"
          data-phase58-protected-main="admin-routes"
          data-phase61-admin-static="[ResponsiveAdaptation][phase61][ADMIN_STATIC_PROOF]"
          data-phase74-scroll-surface="[ResponsiveAdaptation][phase74][ADMIN_SCROLL_NO_OVERLAP]"
        >
          <Outlet />
        </main>
      </div>

      <nav
        className="mobile-tabbar"
        aria-label="Mobile admin navigation"
        data-phase61-mobile-nav="[ResponsiveAdaptation][phase61][SAFE_AREA_PASS]"
        data-phase74-mobile-nav="[FrontendAdmin][phase74][NO_TARIFFS_NAV]"
        data-phase75-mobile-nav="[MobileAdminConsole][phase75][SINGLE_USERS_NAV]"
      >
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
