// FILE: frontend/src/pages/Register.tsx
// VERSION: 1.6.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Phase-67 frameless registration page with a large unframed KrotPN logo, verified-email pending state, referral code support, and compact onboarding context
//   SCOPE: Large visible brand mark, polished auth-only form validation, pending registration API call, check-email/resend state, no token storage before email verification
//   DEPENDS: M-009 (frontend-user), M-002 (auth API), M-005 (referrals), M-071 (matrix-style-system), M-080 (visible-brand-logo-integration)
//   LINKS: M-009 (frontend-user), V-M-009, M-071, M-080, Phase-63, Phase-67
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   RegisterPage - Registration component with Phase-67 frameless BrandMark, form, safe password example, pending check-email state, resend handling, and referral display
//   BLOCK_REGISTER_PAGE - RegisterPage default export
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.6.0 - Applied Phase-67 frameless registration copy, red-focus auth fields, and compact login action.
//   LAST_CHANGE: v1.5.0 - Switched registration logo to Phase-63 BrandMark while preserving Phase-56 regression markers.
//   LAST_CHANGE: v1.4.0 - Added Phase-56 visible brand logo while preserving verified-email pending state
//   LAST_CHANGE: v3.0.0 - Applied Phase-53 compact Matrix auth surface while preserving verified-email cutover
//   LAST_CHANGE: 2026-06-01 - Added Phase-46 password format example tied to the active password policy
//   LAST_CHANGE: 2026-06-01 - Added Phase-44 compact check-email UX, spam hint, strong-password hints, and duplicate-email recovery CTA
//   LAST_CHANGE: 2026-05-13 - Switched registration UX to pending email verification without token storage
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY
//
// START_BLOCK_REGISTER_PAGE
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AlertCircle, ArrowLeft, Loader2, Lock, Mail, MailCheck, RefreshCw, Sparkles } from 'lucide-react'
import toast from 'react-hot-toast'
import { authApi } from '../lib/api'
import { passwordPolicyExample, passwordPolicyHint, passwordStrengthIssues } from '../lib/passwordPolicy'
import BrandMark from '../components/BrandMark'

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
    <div className="matrix-auth-screen phase67-auth-screen" data-phase53-auth-route="register" data-phase67-auth-route="register">
      <section className="matrix-auth-panel animate-in">
        <div className="matrix-auth-heading">
          <BrandMark
            size="lg"
            className="matrix-auth-brand-lockup phase67-auth-logo"
            marker="[VisibleBrandLogo][phase67][LARGE_UNFRAMED_AUTH_LOGO]"
            data-phase56-logo="true"
            data-phase56-legacy-src="/brand/email-logo.png"
            data-phase63-public-auth-logo="register"
            data-phase67-large-logo="[VisibleBrandLogo][phase67][LOGO_NO_OVERLAP]"
          />
          <p className="matrix-kicker mt-4">Кибернетический Протокол Навигации</p>
          <h1 className="mt-2 text-2xl font-extrabold text-white">Присоединиться к KrotPN</h1>
        </div>

            {phase === 'pending' ? (
              <div className="matrix-auth-state space-y-4">
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
                    className="btn-secondary auth-secondary-action w-full"
                    disabled={loading}
                    onClick={() => void submitRegistration(true)}
                  >
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                    Отправить ещё раз
                  </button>
                  <button
                    type="button"
                    className="btn-secondary auth-secondary-action w-full"
                    onClick={() => setPhase('form')}
                  >
                    <ArrowLeft className="h-4 w-4" />
                    Изменить email
                  </button>
                </div>
              </div>
            ) : (
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
                      placeholder="Минимум 10 символов"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      aria-label={t('password')}
                      autoComplete="new-password"
                      required
                      minLength={10}
                    />
                  </div>
                  <p className="mt-2 text-xs leading-5 muted">{passwordPolicyHint}</p>
                  <p className="mt-1 text-xs leading-5 text-slate-300" data-phase46-password-example="true">
                    Пример формата: <span className="font-mono font-semibold text-cyan-100">{passwordPolicyExample}</span>.
                    Не используйте этот пример дословно.
                  </p>
                </label>

                <label className="block">
                  <span className="sr-only">{t('confirmPassword')}</span>
                  <div className="input-group auth-input-group">
                    <Lock className="icon h-5 w-5" />
                    <input
                      type="password"
                      className="input auth-input"
                      placeholder="Повтор пароля"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      aria-label={t('confirmPassword')}
                      autoComplete="new-password"
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

                <button type="submit" className="btn-primary auth-primary-action w-full" disabled={loading}>
                  {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : null}
                  {loading ? 'Отправляем письмо' : t('registerButton')}
                </button>

                <Link to="/login" className="auth-secondary-action w-full">
                  {t('login')}
                </Link>
              </form>
            )}
      </section>
    </div>
  )
}
// END_BLOCK_REGISTER_PAGE
