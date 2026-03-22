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
  { to: '/', icon: LayoutDashboard, labelKey: 'dashboard', caption: 'Состояние подключения' },
  { to: '/config', icon: FileCode, labelKey: 'config', caption: 'Файл, QR и инструкции' },
  { to: '/subscription', icon: CreditCard, labelKey: 'subscription', caption: 'Тариф и продление' },
  { to: '/referrals', icon: Gift, labelKey: 'referrals', caption: 'Бонусы и приглашения' },
  { to: '/settings', icon: Settings, labelKey: 'settings', caption: 'Профиль и безопасность' },
]

export default function Layout() {
  const { t } = useTranslation()
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="app-shell">
      <div className="mx-auto grid min-h-[calc(100vh-2rem)] max-w-[1560px] grid-cols-1 gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="glass overflow-hidden">
          <div className="border-b border-white/5 px-6 py-6">
            <div className="flex items-center gap-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-300/12 text-emerald-200 ring-1 ring-emerald-200/12">
                <Shield className="h-7 w-7" />
              </div>
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.22em] text-cyan-100/70">Secure Access</p>
                <h1 className="mt-1 text-2xl font-extrabold">{t('appName')}</h1>
                <p className="mt-1 text-sm muted">Личный кабинет VPN-сервиса</p>
              </div>
            </div>
          </div>

          <div className="px-4 py-4">
            <div className="panel-soft px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] muted">Ваш статус</p>
              <p className="mt-2 text-lg font-bold text-white">{user?.display_name || user?.email || 'Пользователь'}</p>
              <p className="mt-1 text-sm muted">Управляйте доступом, тарифом и конфигурацией из одного места.</p>
            </div>
          </div>

          <nav className="grid gap-2 px-4 pb-4">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  [
                    'group flex items-center gap-3 rounded-2xl px-4 py-3 transition',
                    isActive
                      ? 'bg-emerald-300/12 text-emerald-100 ring-1 ring-emerald-200/12'
                      : 'text-slate-300 hover:bg-white/5 hover:text-white',
                  ].join(' ')
                }
              >
                <div className="rounded-xl bg-white/5 p-2 transition group-hover:bg-white/10">
                  <item.icon className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <p className="font-semibold">{t(item.labelKey)}</p>
                  <p className="truncate text-xs muted">{item.caption}</p>
                </div>
              </NavLink>
            ))}
          </nav>

          <div className="border-t border-white/5 px-4 py-4">
            <div className="panel-soft mb-3 flex items-center gap-3 px-4 py-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/10 text-lg font-bold">
                {user?.display_name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || '?'}
              </div>
              <div className="min-w-0">
                <p className="truncate font-semibold">{user?.display_name || 'Без имени'}</p>
                <p className="truncate text-xs muted">{user?.email || 'Аккаунт без email'}</p>
              </div>
            </div>

            <button onClick={handleLogout} className="btn-secondary w-full justify-start">
              <LogOut className="h-5 w-5" />
              {t('logout')}
            </button>
          </div>
        </aside>

        <main className="panel overflow-hidden">
          <header className="border-b border-white/5 px-6 py-6 md:px-8">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-cyan-100/70">Private Area</p>
                <h2 className="mt-2 text-3xl font-extrabold tracking-tight">Управление вашим VPN без лишнего шума</h2>
                <p className="mt-2 max-w-2xl text-sm muted">
                  Конфигурация, подписка, трафик и безопасность собраны в одном аккуратном интерфейсе.
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                <div className="panel-soft px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.18em] muted">Защита</p>
                  <p className="mt-2 font-semibold text-emerald-200">AmneziaWG enabled</p>
                </div>
                <div className="panel-soft px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.18em] muted">Аккаунт</p>
                  <p className="mt-2 font-semibold">{user?.email || 'Private account'}</p>
                </div>
                <div className="panel-soft px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.18em] muted">Доступ</p>
                  <p className="mt-2 font-semibold">{user?.is_active ? 'Активен' : 'Ограничен'}</p>
                </div>
              </div>
            </div>
          </header>

          <div className="p-6 md:p-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
