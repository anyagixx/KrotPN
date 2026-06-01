// FILE: frontend/src/pages/ForgotPassword.tsx
// VERSION: 1.0.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Password reset request page for email/password users
//   SCOPE: Email input, generic request response, spam-folder hint, and navigation back to login
//   DEPENDS: M-009 (frontend-user), M-002 (auth API), M-062 (auth email UX and password security)
//   LINKS: M-009, M-062, V-M-062
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ForgotPasswordPage - Requests a password reset email without account enumeration
//   BLOCK_FORGOT_PASSWORD_PAGE - ForgotPassword default export
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.0.0 - Added Phase-44 password reset request UX
// END_CHANGE_SUMMARY
//
// START_BLOCK_FORGOT_PASSWORD_PAGE
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Loader2, Mail, ShieldCheck } from 'lucide-react'
import toast from 'react-hot-toast'
import { authApi } from '../lib/api'

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
    <div className="min-h-screen px-3 py-4 sm:px-4 sm:py-6">
      <div className="mx-auto flex min-h-[calc(100vh-2rem)] max-w-xl items-center justify-center">
        <section className="mx-auto w-full max-w-md">
          <div className="mb-6 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-lg bg-cyan-300/12 text-cyan-100">
              <ShieldCheck className="h-7 w-7" />
            </div>
            <h1 className="mt-4 text-2xl font-extrabold sm:text-3xl">Восстановление пароля</h1>
            <p className="mt-2 text-sm muted">Укажите email аккаунта, и мы отправим ссылку для сброса.</p>
          </div>

          <form onSubmit={handleSubmit} className="glass space-y-4 p-5 sm:p-6">
            <label className="block">
              <span className="mb-2 block text-sm muted">Email</span>
              <div className="input-group">
                <Mail className="icon h-5 w-5" />
                <input
                  type="email"
                  className="input"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
              </div>
            </label>

            {sent ? (
              <div className="panel-soft px-4 py-3 text-sm leading-6 text-slate-200">
                Если такой аккаунт есть, письмо уже отправлено. Проверьте входящие, а также папку «Спам» или «Промоакции».
              </div>
            ) : null}

            <button type="submit" className="btn-primary w-full py-3" disabled={loading}>
              {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : null}
              {loading ? 'Отправляем' : 'Отправить ссылку'}
            </button>

            <Link to="/login" className="btn-secondary w-full">
              <ArrowLeft className="h-4 w-4" />
              Вернуться ко входу
            </Link>
          </form>
        </section>
      </div>
    </div>
  )
}
// END_BLOCK_FORGOT_PASSWORD_PAGE
