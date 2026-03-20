import { Outlet, NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { 
  LayoutDashboard, 
  FileCode, 
  CreditCard, 
  Users, 
  Settings, 
  LogOut,
  Shield
} from 'lucide-react'
import { useAuthStore } from '../stores/auth'

const navItems = [
  { to: '/', icon: LayoutDashboard, labelKey: 'dashboard' },
  { to: '/config', icon: FileCode, labelKey: 'config' },
  { to: '/subscription', icon: CreditCard, labelKey: 'subscription' },
  { to: '/referrals', icon: Users, labelKey: 'referrals' },
  { to: '/settings', icon: Settings, labelKey: 'settings' },
]

export default function Layout() {
  const { t } = useTranslation()
  const { user, logout } = useAuthStore()
  
  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-64 glass border-r border-dark-700 flex flex-col">
        {/* Logo */}
        <div className="p-6 border-b border-dark-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl gradient-bg flex items-center justify-center">
              <Shield className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-lg">{t('appName')}</h1>
              <p className="text-xs text-dark-400">VPN Service</p>
            </div>
          </div>
        </div>
        
        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                  isActive
                    ? 'bg-primary-500/10 text-primary-400'
                    : 'text-dark-300 hover:bg-dark-700/50 hover:text-white'
                }`
              }
            >
              <item.icon className="w-5 h-5" />
              <span>{t(item.labelKey)}</span>
            </NavLink>
          ))}
        </nav>
        
        {/* User */}
        <div className="p-4 border-t border-dark-700">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-full bg-dark-700 flex items-center justify-center text-lg font-medium">
              {user?.display_name?.[0]?.toUpperCase() || '?'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-medium truncate">{user?.display_name || 'User'}</p>
              <p className="text-xs text-dark-400 truncate">{user?.email || ''}</p>
            </div>
          </div>
          <button
            onClick={logout}
            className="w-full flex items-center gap-3 px-4 py-2 rounded-xl text-dark-400 hover:text-red-400 hover:bg-red-500/10 transition-all"
          >
            <LogOut className="w-5 h-5" />
            <span>{t('logout')}</span>
          </button>
        </div>
      </aside>
      
      {/* Main content */}
      <main className="flex-1 p-8 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
