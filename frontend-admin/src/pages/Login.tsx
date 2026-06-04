// FILE: frontend-admin/src/pages/Login.tsx
// VERSION: 3.1.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Minimal Matrix-style admin authentication page with visible KrotPN logo, credential form, role verification, and auth store integration
//   SCOPE: Large unframed brand mark, email/password login, role gate (admin/superadmin only), compact admin auth shell, redirect to dashboard on success
//   DEPENDS: M-010 (frontend-admin), M-006 (admin API), M-037 (mobile-admin-console), M-070 (matrix-visual-runtime), M-071 (matrix-style-system), M-080 (visible-brand-logo-integration), auth store
//   LINKS: M-010, M-037, M-070, M-071, M-080, Phase-54, Phase-63, Phase-67
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   LoginPage - Minimal admin login page component with auth flow, role gate, and large Phase-67-style BrandMark
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v3.1.0 - Reduced admin login to logo, credential inputs, and submit action with Phase-67-style unframed Matrix form controls.
//   LAST_CHANGE: v3.0.0 - Switched admin login mark to Phase-63 BrandMark without restoring preset credentials.
//   LAST_CHANGE: v2.9.0 - Phase-54 compact Matrix admin login without oversized split hero or preset credentials.
//   LAST_CHANGE: v2.8.2 - Removed login field placeholders and standardized icon input padding.
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.8.1 - Phase-25 stores admin refresh token so existing 401 refresh retry can operate
// END_CHANGE_SUMMARY

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, Lock, Mail } from 'lucide-react'
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
      className="admin-login-shell admin-auth-screen"
      data-phase54-admin-login="compact"
      data-log-marker="[FrontendAdmin][Phase54][ROUTE_MATRIX_READY]"
      data-admin-login-minimal="[FrontendAdmin][fix][MINIMAL_LOGIN_READY]"
    >
      <section className="admin-auth-panel animate-in">
        <div className="admin-auth-heading">
          <BrandMark
            size="lg"
            className="admin-login-mark phase67-auth-logo"
            marker="[VisibleBrandLogo][phase63][ADMIN_SHELL_LOGO_SAFE]"
            data-phase63-admin-shell-logo="login"
            data-phase67-large-logo="[VisibleBrandLogo][phase67][LOGO_NO_OVERLAP]"
          />
          <h1 className="sr-only">Вход в админку</h1>
        </div>

        <form onSubmit={handleSubmit} className="admin-auth-form">
          <label className="auth-input-group relative block">
            <span className="sr-only">Email</span>
            <Mail className="icon input-icon-left h-5 w-5" />
            <input
              type="email"
              className="input auth-input w-full"
              aria-label="Email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>

          <label className="auth-input-group relative block">
            <span className="sr-only">Пароль</span>
            <Lock className="icon input-icon-left h-5 w-5" />
            <input
              type="password"
              className="input auth-input w-full"
              aria-label="Пароль"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>

          {error ? <p className="admin-auth-error">{error}</p> : null}

          <button type="submit" className="auth-primary-action w-full" disabled={loading}>
            {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : null}
            {loading ? 'Проверяем' : 'Войти'}
          </button>
        </form>
      </section>
    </div>
  )
}
// END_BLOCK: Login
