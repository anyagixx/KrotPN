// FILE: frontend/src/pages/Register.tsx
// VERSION: 1.1.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: User registration page with verified-email pending state, referral code support, and compact onboarding context
//   SCOPE: Form validation, pending registration API call, check-email/resend state, no token storage before email verification
//   DEPENDS: M-009 (frontend-user), M-002 (auth API), M-005 (referrals)
//   LINKS: M-009 (frontend-user), V-M-009
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   RegisterPage - Registration component with form, pending check-email state, resend handling, and referral display
//   BLOCK_REGISTER_PAGE - RegisterPage default export
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: 2026-06-01 - Added Phase-44 compact check-email UX, spam hint, strong-password hints, and duplicate-email recovery CTA
//   LAST_CHANGE: 2026-05-13 - Switched registration UX to pending email verification without token storage
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY
//
// START_BLOCK_REGISTER_PAGE
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AlertCircle, ArrowLeft, Loader2, Lock, Mail, MailCheck, RefreshCw, Shield, Sparkles } from 'lucide-react'
import toast from 'react-hot-toast'
import { authApi } from '../lib/api'
import { passwordPolicyHint, passwordStrengthIssues } from '../lib/passwordPolicy'

type RegistrationPhase = 'form' | 'pending'

function readApiError(error: unknown, fallback: string): { code: string | null; message: string } {
  const response = (error as { response?: { data?: { detail?: unknown } } }).response
  const detail = response?.data?.detail
  if (typeof detail === 'string') {
    return { code: null, message: detail }
  }
  if (detail && typeof detail === 'object' && 'message' in detail) {
    const detailObject = detail as { code?: unknown; message?: unknown }
    return {
      code: typeof detailObject.code === 'string' ? detailObject.code : null,
      message: String(detailObject.message || fallback),
    }
  }
  return { code: null, message: fallback }
}

export default function Register() {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()

  const referralCode = searchParams.get('ref')

  const [email, setEmail] = useState('')
  const [pendingEmail, setPendingEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [expiresAt, setExpiresAt] = useState<string | null>(null)
  const [phase, setPhase] = useState<RegistrationPhase>('form')
  const [loading, setLoading] = useState(false)
  const [registrationError, setRegistrationError] = useState<{ code: string | null; message: string } | null>(null)

  const submitRegistration = async (isResend = false) => {
    if (password !== confirmPassword) {
      toast.error('Пароли не совпадают')
      return
    }
    const passwordIssues = passwordStrengthIssues(password)
    if (passwordIssues.length > 0) {
      toast.error(`Пароль слишком простой: ${passwordIssues.join(', ')}`)
      return
    }

    setLoading(true)
    setRegistrationError(null)

    try {
      const { data } = await authApi.register(email, password, referralCode || undefined)
      setPendingEmail(data.email)
      setExpiresAt(data.expires_at)
      setPhase('pending')
      toast.success(isResend ? 'Письмо отправлено повторно' : 'Письмо для подтверждения отправлено')
    } catch (error: unknown) {
      const apiError = readApiError(error, t('error'))
      setRegistrationError(apiError)
      toast.error(apiError.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void submitRegistration(false)
  }

  const formattedExpiry = expiresAt
    ? new Date(expiresAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
    : null

  return (
    <div className="min-h-screen px-3 py-4 sm:px-4 sm:py-6">
      <div className="mx-auto flex min-h-[calc(100vh-2rem)] max-w-xl items-center justify-center">
        <section className="w-full p-2 sm:p-4">
          <div className="mx-auto w-full max-w-md">
            <div className="mb-6 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-lg bg-emerald-300/12 text-emerald-200">
                <Shield className="h-7 w-7" />
              </div>
              <h1 className="mt-4 text-2xl font-extrabold sm:text-3xl">{t('registerTitle')}</h1>
              <p className="mt-2 text-sm muted">Подтвердите email, чтобы активировать личный кабинет.</p>
            </div>

            {phase === 'pending' ? (
              <div className="glass space-y-4 p-5 sm:p-6">
                {/* REGISTER_PENDING_STATE */}
                <div className="flex items-start gap-3">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-emerald-300/12 text-emerald-100">
                    <MailCheck className="h-6 w-6" />
                  </div>
                  <div>
                    <h2 className="text-xl font-extrabold text-white">Проверьте почту</h2>
                    <p className="mt-1 text-sm leading-6 muted">
                      Мы отправили ссылку на <span className="font-semibold text-cyan-100">{pendingEmail}</span>.
                      Если письмо не пришло в течение минуты, проверьте папку «Спам» или «Промоакции».
                    </p>
                  </div>
                </div>

                {formattedExpiry ? (
                  <div className="panel-soft px-4 py-3 text-sm text-slate-200">
                    Ссылка активна до <span className="font-semibold text-white">{formattedExpiry}</span>.
                  </div>
                ) : null}

                <div className="grid gap-2 sm:grid-cols-2">
                  {/* REGISTER_RESEND_AVAILABLE */}
                  <button
                    type="button"
                    className="btn-secondary w-full"
                    disabled={loading}
                    onClick={() => void submitRegistration(true)}
                  >
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                    Отправить ещё раз
                  </button>
                  <button
                    type="button"
                    className="btn-secondary w-full"
                    onClick={() => setPhase('form')}
                  >
                    <ArrowLeft className="h-4 w-4" />
                    Изменить email
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="glass space-y-4 p-5 sm:p-6">
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
                      placeholder="Минимум 10 символов"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      minLength={10}
                    />
                  </div>
                  <p className="mt-2 text-xs leading-5 muted">{passwordPolicyHint}</p>
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

                {registrationError?.code === 'email_unavailable' ? (
                  <div className="panel-soft flex items-start gap-3 px-4 py-3 text-sm text-slate-200">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-cyan-100" />
                    <div>
                      <p>{registrationError.message}</p>
                      <Link to="/forgot-password" className="mt-1 inline-block font-semibold text-cyan-100 hover:text-emerald-100">
                        Восстановить доступ
                      </Link>
                    </div>
                  </div>
                ) : null}

                <button type="submit" className="btn-primary w-full py-3" disabled={loading}>
                  {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : null}
                  {loading ? 'Отправляем письмо' : t('registerButton')}
                </button>
              </form>
            )}

            <div className="mt-5 text-center text-sm muted">
              {t('hasAccount')}{' '}
              <Link to="/login" className="font-semibold text-cyan-100 hover:text-emerald-100">
                {t('login')}
              </Link>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
// END_BLOCK_REGISTER_PAGE
