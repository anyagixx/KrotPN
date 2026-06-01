// FILE: frontend/src/pages/ResetPassword.tsx
// VERSION: 1.0.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Password reset confirmation page for one-time recovery tokens
//   SCOPE: Token query parsing, strong-password validation, reset API call, and navigation back to login
//   DEPENDS: M-009 (frontend-user), M-002 (auth API), M-062 (auth email UX and password security)
//   LINKS: M-009, M-062, V-M-062
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ResetPasswordPage - Confirms a password reset token with a new strong password
//   BLOCK_RESET_PASSWORD_PAGE - ResetPassword default export
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.0.0 - Added Phase-44 password reset confirmation UX
// END_CHANGE_SUMMARY
//
// START_BLOCK_RESET_PASSWORD_PAGE
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, CheckCircle2, Loader2, Lock, ShieldCheck } from 'lucide-react'
import toast from 'react-hot-toast'
import { authApi } from '../lib/api'
import { passwordPolicyHint, passwordStrengthIssues } from '../lib/passwordPolicy'

function readApiError(error: unknown, fallback: string): string {
  const response = (error as { response?: { data?: { detail?: unknown } } }).response
  const detail = response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object' && 'message' in detail) {
    return String((detail as { message?: unknown }).message || fallback)
  }
  return fallback
}

export default function ResetPassword() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [done, setDone] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!token) {
      toast.error('Ссылка для сброса пароля недействительна')
      return
    }
    if (password !== confirmPassword) {
      toast.error('Пароли не совпадают')
      return
    }
    const issues = passwordStrengthIssues(password)
    if (issues.length > 0) {
      toast.error(`Пароль слишком простой: ${issues.join(', ')}`)
      return
    }

    setLoading(true)
    try {
      await authApi.confirmPasswordReset(token, password)
      setDone(true)
      toast.success('Пароль обновлён')
    } catch (error: unknown) {
      toast.error(readApiError(error, 'Не удалось обновить пароль'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen px-3 py-4 sm:px-4 sm:py-6">
      <div className="mx-auto flex min-h-[calc(100vh-2rem)] max-w-xl items-center justify-center">
        <section className="mx-auto w-full max-w-md">
          <div className="mb-6 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-lg bg-emerald-300/12 text-emerald-100">
              <ShieldCheck className="h-7 w-7" />
            </div>
            <h1 className="mt-4 text-2xl font-extrabold sm:text-3xl">Новый пароль</h1>
            <p className="mt-2 text-sm muted">Задайте устойчивый пароль для личного кабинета.</p>
          </div>

          {done ? (
            <div className="glass space-y-4 p-5 text-center sm:p-6">
              <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-200" />
              <div>
                <h2 className="text-xl font-extrabold text-white">Пароль обновлён</h2>
                <p className="mt-2 text-sm muted">Теперь можно войти в аккаунт с новым паролем.</p>
              </div>
              <button type="button" className="btn-primary w-full" onClick={() => navigate('/login')}>
                Перейти ко входу
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="glass space-y-4 p-5 sm:p-6">
              {!token ? (
                <div className="panel-soft px-4 py-3 text-sm text-slate-200">
                  В ссылке отсутствует одноразовый токен. Запросите новое письмо для сброса пароля.
                </div>
              ) : null}

              <label className="block">
                <span className="mb-2 block text-sm muted">Новый пароль</span>
                <div className="input-group">
                  <Lock className="icon h-5 w-5" />
                  <input
                    type="password"
                    className="input"
                    placeholder="Минимум 10 символов"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                    minLength={10}
                  />
                </div>
                <p className="mt-2 text-xs leading-5 muted">{passwordPolicyHint}</p>
              </label>

              <label className="block">
                <span className="mb-2 block text-sm muted">Повторите пароль</span>
                <div className="input-group">
                  <Lock className="icon h-5 w-5" />
                  <input
                    type="password"
                    className="input"
                    placeholder="Повторите пароль"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    required
                  />
                </div>
              </label>

              <button type="submit" className="btn-primary w-full py-3" disabled={loading || !token}>
                {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : null}
                {loading ? 'Обновляем' : 'Сохранить пароль'}
              </button>

              <Link to="/forgot-password" className="btn-secondary w-full">
                <ArrowLeft className="h-4 w-4" />
                Запросить новую ссылку
              </Link>
            </form>
          )}
        </section>
      </div>
    </div>
  )
}
// END_BLOCK_RESET_PASSWORD_PAGE
