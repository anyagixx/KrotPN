// FILE: frontend-admin/src/pages/Login.tsx
// VERSION: 3.0.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact Matrix-style admin authentication page with visible Phase-63 KrotPN logo, login form, role verification, and auth store integration
//   SCOPE: Visible brand mark, email/password login, role gate (admin/superadmin only), route-safe compact console shell, redirect to dashboard on success
//   DEPENDS: M-010 (frontend-admin), M-006 (admin API), M-037 (mobile-admin-console), M-070 (matrix-visual-runtime), M-071 (matrix-style-system), M-080 (visible-brand-logo-integration), auth store
//   LINKS: M-010, M-037, M-070, M-071, M-080, Phase-54, Phase-63
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   LoginPage - Admin login page component with auth flow and Phase-63 BrandMark
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v3.0.0 - Switched admin login mark to Phase-63 BrandMark without restoring preset credentials.
//   LAST_CHANGE: v2.9.0 - Phase-54 compact Matrix admin login without oversized split hero or preset credentials.
//   LAST_CHANGE: v2.8.2 - Removed login field placeholders and standardized icon input padding.
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.8.1 - Phase-25 stores admin refresh token so existing 401 refresh retry can operate
// END_CHANGE_SUMMARY

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity, Loader2, Lock, Mail, Server, Users } from 'lucide-react'
import { adminApi } from '../lib/api'
import BrandMark from '../components/BrandMark'
import { useAuthStore } from '../stores/auth'

// START_BLOCK: Login
// Admin login page: email/password auth, role gate (admin/superadmin only), redirect to dashboard
// DEPENDS: M-010 (frontend-admin), M-006 (admin API via adminApi)
//   - adminApi.login, adminApi.getCurrentUser
//   - useAuthStore (Zustand auth store: setUser, setToken)
export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const { setUser, setToken } = useAuthStore()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const { data } = await adminApi.login(email, password)
      setToken(data.access_token)
      if (data.refresh_token) {
        localStorage.setItem('admin_refresh_token', data.refresh_token)
      } else {
        localStorage.removeItem('admin_refresh_token')
      }

      const userResponse = await adminApi.getCurrentUser()
      const user = userResponse.data

      if (user.role !== 'admin' && user.role !== 'superadmin') {
        setToken(null)
        setError('Доступ запрещён. Требуются права администратора.')
        return
      }

      setUser({
        id: user.id,
        email: user.email ?? '',
        role: user.role,
        is_superuser: user.role === 'superadmin',
      })
      navigate('/')
    } catch (err: unknown) {
      setToken(null)
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Ошибка авторизации')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="admin-login-shell"
      data-phase54-admin-login="compact"
      data-log-marker="[FrontendAdmin][Phase54][ROUTE_MATRIX_READY]"
    >
      <div className="admin-login-card">
        <section className="flex min-w-0 flex-col justify-between gap-4">
          <div className="flex items-start gap-3">
            <BrandMark
              size="lg"
              className="admin-login-mark"
              marker="[VisibleBrandLogo][phase63][ADMIN_SHELL_LOGO_SAFE]"
              data-phase63-admin-shell-logo="login"
            />
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase text-emerald-200">KrotPN Control Plane</p>
              <h1 className="mt-1 text-2xl font-extrabold text-white">Админ-консоль</h1>
              <p className="mt-2 max-w-xl text-sm leading-6 muted">
                Компактный вход для оператора: пользователи, серверы, MTProto, тарифы и аварийная сводка.
              </p>
            </div>
          </div>

          <div className="admin-hero-strip">
            {[
              [Users, 'Users', 'поиск и роли'],
              [Server, 'Nodes', 'маршруты и health'],
              [Activity, 'MTProto', 'proxy ops'],
            ].map(([Icon, title, description]) => {
              const ItemIcon = Icon as typeof Users
              return (
                <div key={String(title)} className="admin-route-card">
                  <ItemIcon className="mb-2 h-4 w-4 text-cyan-200" />
                  <p className="text-sm font-semibold text-white">{String(title)}</p>
                  <p className="mt-1 text-xs muted">{String(description)}</p>
                </div>
              )
            })}
          </div>
        </section>

        <section className="flex items-center justify-center">
          <div className="w-full">
            <div className="mb-4">
              <h2 className="text-xl font-extrabold text-white">Вход в админку</h2>
              <p className="mt-1 text-sm muted">Поля пустые, без подсказок и заранее подставленных credentials.</p>
            </div>

            <form onSubmit={handleSubmit} className="glass space-y-4 p-4 sm:p-5">
              <label className="block">
                <span className="mb-2 block text-sm muted">Email</span>
                <div className="relative">
                  <Mail className="input-icon-left h-5 w-5" />
                  <input
                    type="email"
                    className="input input-with-icon-left"
                    aria-label="Email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
              </label>

              <label className="block">
                <span className="mb-2 block text-sm muted">Пароль</span>
                <div className="relative">
                  <Lock className="input-icon-left h-5 w-5" />
                  <input
                    type="password"
                    className="input input-with-icon-left"
                    aria-label="Пароль"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
              </label>

              {error ? <p className="rounded-lg bg-red-400/10 px-4 py-3 text-sm text-red-100">{error}</p> : null}

              <button type="submit" className="btn-primary w-full py-3.5" disabled={loading}>
                {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : null}
                {loading ? 'Проверяем доступ' : 'Войти в консоль'}
              </button>
            </form>

            <p className="mt-4 text-sm muted">
              Для операционной работы используй только административную учётную запись.
            </p>
          </div>
        </section>
      </div>
    </div>
  )
}
// END_BLOCK: Login
