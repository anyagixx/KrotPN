// FILE: frontend/src/pages/Login.tsx
// VERSION: 1.2.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact Matrix login page with email/password authentication and visible Phase-63 KrotPN logo
//   SCOPE: Visible brand mark, login form, token storage, recovery link, navigation to dashboard after successful auth
//   DEPENDS: M-009 (frontend-user), M-002 (auth API), M-071 (matrix-style-system), M-080 (visible-brand-logo-integration)
//   LINKS: M-009 (frontend-user), M-071, M-080, Phase-63
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   LoginPage - Login component with compact Matrix auth form and Phase-63 BrandMark
//   BLOCK_LOGIN_PAGE - LoginPage default export
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.3.0 - Switched auth logo to Phase-63 BrandMark while preserving Phase-56 regression markers.
//   LAST_CHANGE: v1.2.0 - Added Phase-56 visible brand logo and dashboard navigation target for public landing split
//   LAST_CHANGE: v3.0.0 - Removed heavy marketing panel and applied Phase-53 compact Matrix auth surface
//   LAST_CHANGE: 2026-06-01 - Added Phase-44 password recovery entry point
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY
//
// START_BLOCK_LOGIN_PAGE
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Loader2, Lock, Mail } from 'lucide-react'
import toast from 'react-hot-toast'
import { authApi } from '../lib/api'
import { useAuthStore } from '../stores/auth'
import BrandMark from '../components/BrandMark'

export default function Login() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { fetchUser } = useAuthStore()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      const { data } = await authApi.login(email, password)

      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)

      await fetchUser()
      toast.success(t('success'))
      navigate('/dashboard')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || t('invalidCredentials'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="matrix-auth-screen" data-phase53-auth-route="login">
      <section className="matrix-auth-card animate-in">
        <div className="matrix-auth-heading">
          <BrandMark
            size="lg"
            className="matrix-auth-brand-lockup"
            marker="[VisibleBrandLogo][phase63][PUBLIC_AUTH_LOGO_VISIBLE]"
            data-phase56-logo="true"
            data-phase56-legacy-src="/brand/email-logo.png"
            data-phase63-public-auth-logo="login"
          />
          <p className="matrix-kicker mt-4">KrotPN Secure Access</p>
          <h1 className="mt-2 text-2xl font-extrabold text-white">{t('loginTitle')}</h1>
          <p className="mt-2 text-sm muted">Войдите, чтобы управлять подключением и подпиской.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block">
            <span className="mb-2 block text-sm muted">{t('email')}</span>
            <div className="input-group">
              <Mail className="icon h-5 w-5" />
              <input
                type="email"
                className="input"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
          </label>

          <label className="block">
            <span className="mb-2 block text-sm muted">{t('password')}</span>
            <div className="input-group">
              <Lock className="icon h-5 w-5" />
              <input
                type="password"
                className="input"
                placeholder={t('password')}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </label>

          <button type="submit" className="btn-primary w-full py-3.5" disabled={loading}>
            {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : null}
            {loading ? 'Проверяем доступ' : t('loginButton')}
          </button>

          <div className="text-right text-sm">
            <Link to="/forgot-password" className="font-semibold text-cyan-100 hover:text-emerald-100">
              Забыли пароль?
            </Link>
          </div>
        </form>

        <div className="mt-5 text-center text-sm muted">
          {t('noAccount')}{' '}
          <Link to="/register" className="font-semibold text-cyan-100 hover:text-emerald-100">
            {t('register')}
          </Link>
        </div>
      </section>
    </div>
  )
}
// END_BLOCK_LOGIN_PAGE
