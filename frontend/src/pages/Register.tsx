// FILE: frontend/src/pages/Register.tsx
// VERSION: 1.0.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: User registration page with email/password form, referral code support, and onboarding info panel
//   SCOPE: Form validation (password match), registration API call, token storage, navigation to dashboard
//   DEPENDS: M-009 (frontend-user), M-002 (auth API), M-005 (referrals)
//   LINKS: M-009 (frontend-user)
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   RegisterPage - Registration component with form, referral code handling, and marketing panel
//   BLOCK_REGISTER_PAGE - RegisterPage default export (157 lines)
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY
//
// START_BLOCK_REGISTER_PAGE
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Loader2, Lock, Mail, Shield, Sparkles } from 'lucide-react'
import toast from 'react-hot-toast'
import { authApi } from '../lib/api'
import { useAuthStore } from '../stores/auth'

export default function Register() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { fetchUser } = useAuthStore()
  const [searchParams] = useSearchParams()

  const referralCode = searchParams.get('ref')

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (password !== confirmPassword) {
      toast.error('Пароли не совпадают')
      return
    }

    setLoading(true)

    try {
      const { data } = await authApi.register(email, password, referralCode || undefined)

      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)

      await fetchUser()
      toast.success(t('registrationSuccess'))
      navigate('/')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || t('error'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen px-4 py-8">
      <div className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-6xl grid-cols-1 overflow-hidden rounded-[32px] border border-white/10 bg-slate-950/35 shadow-[0_36px_120px_rgba(2,10,14,0.55)] backdrop-blur-sm lg:grid-cols-[0.96fr_1.04fr]">
        <section className="flex items-center justify-center p-6 md:p-10">
          <div className="w-full max-w-md">
            <div className="mb-8 text-center lg:text-left">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[24px] bg-emerald-300/12 text-emerald-200 lg:mx-0">
                <Shield className="h-8 w-8" />
              </div>
              <h1 className="mt-5 text-3xl font-extrabold">{t('registerTitle')}</h1>
              <p className="mt-2 text-sm muted">Создайте аккаунт и получите тестовый доступ без сложной настройки.</p>
            </div>

            <form onSubmit={handleSubmit} className="glass space-y-4 p-6">
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
                    placeholder="Минимум 8 символов"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={8}
                  />
                </div>
              </label>

              <label className="block">
                <span className="mb-2 block text-sm muted">{t('confirmPassword')}</span>
                <div className="input-group">
                  <Lock className="icon h-5 w-5" />
                  <input
                    type="password"
                    className="input"
                    placeholder={t('confirmPassword')}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                  />
                </div>
              </label>

              {referralCode ? (
                <div className="panel-soft flex items-center gap-3 px-4 py-3 text-sm">
                  <Sparkles className="h-4 w-4 text-emerald-200" />
                  Реферальный код применён: <span className="font-bold text-cyan-100">{referralCode}</span>
                </div>
              ) : null}

              <button type="submit" className="btn-primary w-full py-3.5" disabled={loading}>
                {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : null}
                {loading ? 'Создаём аккаунт' : t('registerButton')}
              </button>
            </form>

            <div className="mt-6 text-center text-sm muted">
              {t('hasAccount')}{' '}
              <Link to="/login" className="font-semibold text-cyan-100 hover:text-emerald-100">
                {t('login')}
              </Link>
            </div>
          </div>
        </section>

        <section className="hidden border-l border-white/5 p-10 lg:flex lg:flex-col lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-3 rounded-full border border-cyan-200/12 bg-cyan-300/10 px-4 py-2 text-sm font-semibold text-cyan-100">
              <Sparkles className="h-4 w-4" />
              Trial onboarding
            </div>
            <h2 className="mt-8 max-w-xl text-5xl font-extrabold tracking-tight text-white">
              Начните с бесплатного периода и переходите на платный доступ только когда убедитесь в качестве
            </h2>
          </div>

          <div className="grid gap-4">
            {[
              ['3 дня trial', 'Первичное знакомство без привязки карты.'],
              ['Быстрая выдача конфигурации', 'После регистрации кабинет готов к работе.'],
              ['Реферальный бонус', 'Приглашения продлевают доступ бонусными днями.'],
            ].map(([title, description]) => (
              <div key={title} className="panel-soft p-5">
                <p className="text-lg font-bold">{title}</p>
                <p className="mt-2 text-sm muted">{description}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
// END_BLOCK_REGISTER_PAGE
