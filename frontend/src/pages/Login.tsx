// FILE: frontend/src/pages/Login.tsx
// VERSION: 1.5.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Phase-67 frameless Matrix login page with email/password authentication and a large unframed KrotPN logo
//   SCOPE: Large visible brand mark, polished auth-only email/password form, token storage, stored-session redirect, side-by-side register/recovery links, navigation to dashboard after successful auth
//   DEPENDS: M-009 (frontend-user), M-002 (auth API), M-039 (session-security-hardening), M-071 (matrix-style-system), M-080 (visible-brand-logo-integration)
//   LINKS: M-009 (frontend-user), M-039, M-071, M-080, Phase-63, Phase-67
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   LoginPage - Login component with Phase-67 frameless Matrix auth form, large BrandMark, and stored-session redirect
//   BLOCK_LOGIN_PAGE - LoginPage default export
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.5.0 - Added existing-session redirect and 60-day inactivity-aware token persistence.
//   LAST_CHANGE: v1.4.0 - Applied Phase-67 frameless login copy, red-focus auth fields, and side-by-side secondary actions.
//   LAST_CHANGE: v1.3.0 - Switched auth logo to Phase-63 BrandMark while preserving Phase-56 regression markers.
//   LAST_CHANGE: v1.2.0 - Added Phase-56 visible brand logo and dashboard navigation target for public landing split
//   LAST_CHANGE: v3.0.0 - Removed heavy marketing panel and applied Phase-53 compact Matrix auth surface
//   LAST_CHANGE: 2026-06-01 - Added Phase-44 password recovery entry point
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY
//
// START_BLOCK_LOGIN_PAGE
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Loader2, Lock, Mail } from 'lucide-react'
import toast from 'react-hot-toast'
import { authApi } from '../lib/api'
import { useAuthStore } from '../stores/auth'
import BrandMark from '../components/BrandMark'
import { enforceUserSessionTtl, persistUserSessionTokens } from '../lib/session'

export default function Login() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { fetchUser, isAuthenticated } = useAuthStore()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let cancelled = false

    const resumeExistingSession = async () => {
      if (!isAuthenticated && !enforceUserSessionTtl()) {
        return
      }

      await fetchUser()
      if (!cancelled && useAuthStore.getState().isAuthenticated) {
        navigate('/dashboard', { replace: true })
      }
    }

    void resumeExistingSession()
    return () => {
      cancelled = true
    }
  }, [fetchUser, isAuthenticated, navigate])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      const { data } = await authApi.login(email, password)

      persistUserSessionTokens(data.access_token, data.refresh_token)

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
    <div className="matrix-auth-screen phase67-auth-screen" data-phase53-auth-route="login" data-phase67-auth-route="login">
      <section className="matrix-auth-panel animate-in">
        <div className="matrix-auth-heading">
          <BrandMark
            size="lg"
            className="matrix-auth-brand-lockup phase67-auth-logo"
            marker="[VisibleBrandLogo][phase67][LARGE_UNFRAMED_AUTH_LOGO]"
            data-phase56-logo="true"
            data-phase56-legacy-src="/brand/email-logo.png"
            data-phase63-public-auth-logo="login"
            data-phase67-large-logo="[VisibleBrandLogo][phase67][LOGO_NO_OVERLAP]"
          />
          <p className="matrix-kicker mt-4">Кибернетический Протокол Навигации</p>
          <h1 className="mt-2 text-2xl font-extrabold text-white">Вход в KrotPN</h1>
        </div>

        <form onSubmit={handleSubmit} className="phase67-auth-form">
          <label className="block">
            <span className="sr-only">{t('email')}</span>
            <div className="input-group auth-input-group">
              <Mail className="icon h-5 w-5" />
              <input
                type="email"
                className="input auth-input"
                placeholder="Почта"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                aria-label={t('email')}
                autoComplete="email"
                required
              />
            </div>
          </label>

          <label className="block">
            <span className="sr-only">{t('password')}</span>
            <div className="input-group auth-input-group">
              <Lock className="icon h-5 w-5" />
              <input
                type="password"
                className="input auth-input"
                placeholder={t('password')}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-label={t('password')}
                autoComplete="current-password"
                required
              />
            </div>
          </label>

          <button type="submit" className="btn-primary auth-primary-action w-full" disabled={loading}>
            {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : null}
            {loading ? 'Проверяем доступ' : t('loginButton')}
          </button>

          <div className="phase67-auth-secondary-grid">
            <Link to="/register" className="auth-secondary-action">
              {t('register')}
            </Link>
            <Link to="/forgot-password" className="auth-secondary-action">
              Забыли пароль?
            </Link>
          </div>
        </form>
      </section>
    </div>
  )
}
// END_BLOCK_LOGIN_PAGE
