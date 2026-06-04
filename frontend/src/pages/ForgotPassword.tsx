// FILE: frontend/src/pages/ForgotPassword.tsx
// VERSION: 1.4.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Phase-67 frameless password reset request page for email/password users with a large unframed KrotPN logo
//   SCOPE: Large visible brand mark, polished auth-only email input, generic request response, spam-folder hint, and navigation back to login
//   DEPENDS: M-009 (frontend-user), M-002 (auth API), M-062 (auth email UX and password security), M-071 (matrix-style-system), M-080 (visible-brand-logo-integration)
//   LINKS: M-009, M-062, M-071, M-080, V-M-062, Phase-63, Phase-67
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ForgotPasswordPage - Requests a password reset email without account enumeration and renders Phase-67 frameless BrandMark
//   BLOCK_FORGOT_PASSWORD_PAGE - ForgotPassword default export
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.4.0 - Applied Phase-67 frameless recovery copy, red-focus auth field, and polished actions.
//   LAST_CHANGE: v1.3.0 - Switched recovery logo to Phase-63 BrandMark while preserving Phase-56 regression markers.
//   LAST_CHANGE: v1.2.0 - Added Phase-56 visible brand logo for premium public/auth consistency
//   LAST_CHANGE: v1.1.0 - Applied Phase-53 compact Matrix recovery surface
//   LAST_CHANGE: v1.0.0 - Added Phase-44 password reset request UX
// END_CHANGE_SUMMARY
//
// START_BLOCK_FORGOT_PASSWORD_PAGE
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Loader2, Mail } from 'lucide-react'
import toast from 'react-hot-toast'
import { authApi } from '../lib/api'
import BrandMark from '../components/BrandMark'

function readApiError(error: unknown, fallback: string): string {
  const response = (error as { response?: { data?: { detail?: unknown } } }).response
  const detail = response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object' && 'message' in detail) {
    return String((detail as { message?: unknown }).message || fallback)
  }
  return fallback
}

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setLoading(true)
    try {
      await authApi.requestPasswordReset(email)
      setSent(true)
      toast.success('Если аккаунт существует, письмо отправлено')
    } catch (error: unknown) {
      toast.error(readApiError(error, 'Не удалось отправить письмо'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="matrix-auth-screen phase67-auth-screen" data-phase53-auth-route="forgot-password" data-phase67-auth-route="forgot-password">
      <section className="matrix-auth-panel animate-in">
        <div className="matrix-auth-heading">
          <BrandMark
            size="lg"
            className="matrix-auth-brand-lockup phase67-auth-logo"
            marker="[VisibleBrandLogo][phase67][LARGE_UNFRAMED_AUTH_LOGO]"
            data-phase56-logo="true"
            data-phase56-legacy-src="/brand/email-logo.png"
            data-phase63-public-auth-logo="forgot-password"
            data-phase67-large-logo="[VisibleBrandLogo][phase67][LOGO_NO_OVERLAP]"
          />
          <p className="matrix-kicker mt-4">Кибернетический Протокол Навигации</p>
          <h1 className="mt-2 text-2xl font-extrabold text-white">Восстановление пароля</h1>
        </div>

        <form onSubmit={handleSubmit} className="phase67-auth-form">
            <label className="block">
              <span className="sr-only">Email</span>
              <div className="input-group auth-input-group">
                <Mail className="icon h-5 w-5" />
                <input
                  type="email"
                  className="input auth-input"
                  placeholder="Почта"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  aria-label="Email"
                  autoComplete="email"
                  required
                />
              </div>
            </label>

            {sent ? (
              <div className="panel-soft px-4 py-3 text-sm leading-6 text-slate-200">
                Если такой аккаунт есть, письмо уже отправлено. Проверьте входящие, а также папку «Спам» или «Промоакции».
              </div>
            ) : null}

            <button type="submit" className="btn-primary auth-primary-action w-full" disabled={loading}>
              {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : null}
              {loading ? 'Отправляем' : 'Отправить ссылку'}
            </button>

            <Link to="/login" className="auth-secondary-action w-full">
              <ArrowLeft className="h-4 w-4" />
              Вернуться ко входу
            </Link>
        </form>
      </section>
    </div>
  )
}
// END_BLOCK_FORGOT_PASSWORD_PAGE
