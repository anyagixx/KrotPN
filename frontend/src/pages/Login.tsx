// FILE: frontend/src/pages/Login.tsx
// VERSION: 1.1.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact Matrix login page with email/password authentication
//   SCOPE: Login form, token storage, recovery link, navigation to dashboard after successful auth
//   DEPENDS: M-009 (frontend-user), M-002 (auth API), M-071 (matrix-style-system)
//   LINKS: M-009 (frontend-user), M-071
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   LoginPage - Login component with compact Matrix auth form
//   BLOCK_LOGIN_PAGE - LoginPage default export
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v3.0.0 - Removed heavy marketing panel and applied Phase-53 compact Matrix auth surface
//   LAST_CHANGE: 2026-06-01 - Added Phase-44 password recovery entry point
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY
//
// START_BLOCK_LOGIN_PAGE
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Loader2, Lock, Mail, Shield } from 'lucide-react'
import toast from 'react-hot-toast'
import { authApi } from '../lib/api'
import { useAuthStore } from '../stores/auth'

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
      navigate('/')
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
          <div className="matrix-brand-mark mx-auto h-12 w-12">
            <Shield className="h-6 w-6" />
          </div>
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
