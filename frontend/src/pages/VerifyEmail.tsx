// FILE: frontend/src/pages/VerifyEmail.tsx
// VERSION: 1.4.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Frameless Matrix email verification landing page with visible KrotPN logo, one-time token consumption, and authenticated onboarding entry
//   SCOPE: Large unframed brand mark, token query parsing, verify-email API call, 60-day session token persistence after success, expired/replayed/error states, dashboard navigation
//   DEPENDS: M-009 (frontend-user), M-002 (auth API), M-039 (session-security-hardening), M-071 (matrix-style-system), M-080 (visible-brand-logo-integration)
//   LINKS: M-009 (frontend-user), M-039, M-071, M-080, V-M-009, V-M-039, Phase-67
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   VerifyEmailPage - Phase-67 verification component with large BrandMark plus checking, success, expired/replay, and error states
//   BLOCK_VERIFY_EMAIL_PAGE - VerifyEmailPage default export
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.4.0 - Applied Phase-67 frameless Matrix auth style and 60-day session helper persistence on verified-email success.
//   LAST_CHANGE: v1.3.0 - Switched verify-email inline logo to Phase-63 BrandMark while preserving Phase-56 regression markers.
//   LAST_CHANGE: v1.2.0 - Added Phase-56 visible brand logo and dashboard navigation target after verified email proof
//   LAST_CHANGE: v1.1.0 - Applied Phase-53 compact Matrix verification surface
//   LAST_CHANGE: 2026-05-13 - Added Phase-28 verify-email frontend route
// END_CHANGE_SUMMARY
//
// START_BLOCK_VERIFY_EMAIL_PAGE
import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, Loader2, RefreshCw, Shield } from 'lucide-react'
import toast from 'react-hot-toast'
import { authApi } from '../lib/api'
import { persistUserSessionTokens } from '../lib/session'
import { useAuthStore } from '../stores/auth'
import BrandMark from '../components/BrandMark'

type VerifyState = 'checking' | 'success' | 'expired' | 'error'

function readVerifyError(error: unknown): { code: string | null; message: string } {
  const response = (error as { response?: { data?: { detail?: unknown } } }).response
  const detail = response?.data?.detail
  if (detail && typeof detail === 'object' && 'code' in detail) {
    const typed = detail as { code?: unknown; message?: unknown }
    return {
      code: typeof typed.code === 'string' ? typed.code : null,
      message: typeof typed.message === 'string' ? typed.message : 'Ссылка не сработала',
    }
  }
  return { code: null, message: typeof detail === 'string' ? detail : 'Ссылка не сработала' }
}

export default function VerifyEmail() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { fetchUser } = useAuthStore()
  const token = searchParams.get('token') || ''

  const [state, setState] = useState<VerifyState>('checking')
  const [message, setMessage] = useState('Проверяем ссылку подтверждения.')

  useEffect(() => {
    let cancelled = false

    const verify = async () => {
      if (!token) {
        setState('error')
        setMessage('В ссылке нет токена подтверждения.')
        return
      }

      try {
        const { data } = await authApi.verifyEmail(token)
        if (cancelled) {
          return
        }
        persistUserSessionTokens(data.access_token, data.refresh_token)
        await fetchUser()
        if (cancelled) {
          return
        }
        setState('success')
        setMessage('Email подтверждён. Кабинет готов к работе.')
        toast.success('Email подтверждён')
      } catch (error: unknown) {
        if (cancelled) {
          return
        }
        const parsed = readVerifyError(error)
        if (parsed.code === 'token_expired' || parsed.code === 'token_replayed') {
          setState('expired')
          setMessage('Ссылка уже использована или срок действия истёк.')
        } else {
          setState('error')
          setMessage(parsed.message)
        }
      }
    }

    void verify()
    return () => {
      cancelled = true
    }
  }, [fetchUser, token])

  const isChecking = state === 'checking'
  const isSuccess = state === 'success'
  const isExpired = state === 'expired'

  return (
    <div className="matrix-auth-screen phase67-auth-screen" data-phase53-auth-route="verify-email" data-phase67-auth-route="verify-email">
      <section className="matrix-auth-panel animate-in space-y-5">
        <div className="matrix-auth-heading">
          <BrandMark
            size="lg"
            className="matrix-auth-brand-lockup phase67-auth-logo"
            marker="[VisibleBrandLogo][phase67][LARGE_UNFRAMED_AUTH_LOGO]"
            data-phase56-logo="true"
            data-phase56-legacy-src="/brand/email-logo.png"
            data-phase63-public-auth-logo="verify-email"
            data-phase67-large-logo="[VisibleBrandLogo][phase67][LOGO_NO_OVERLAP]"
          />
          <p className="matrix-kicker mt-4">Кибернетический Протокол Навигации</p>
          <h1 className="mt-3 text-2xl font-extrabold text-white">
            {isChecking ? 'Подтверждение почты' : isSuccess ? 'Email подтверждён' : 'Ссылка недоступна'}
          </h1>
        </div>

        <div className="matrix-auth-state flex items-center gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-emerald-300/12 text-emerald-100">
            {isChecking ? (
              <Loader2 className="h-6 w-6 animate-spin" />
            ) : isSuccess ? (
              // REGISTER_VERIFIED_SUCCESS
              <CheckCircle2 className="h-6 w-6" />
            ) : (
              // REGISTER_EXPIRED_LINK
              <AlertTriangle className="h-6 w-6" />
            )}
          </div>
          <p className="text-sm leading-6 muted">{message}</p>
        </div>

        {isSuccess ? (
          <button type="button" className="auth-primary-action btn w-full" onClick={() => navigate('/dashboard')}>
            <Shield className="h-4 w-4" />
            Открыть кабинет
          </button>
        ) : null}

        {isExpired ? (
          <Link to="/register" className="auth-secondary-action w-full">
            {/* REGISTER_RESEND_AVAILABLE */}
            <RefreshCw className="h-4 w-4" />
            Отправить новую ссылку
          </Link>
        ) : null}

        {state === 'error' ? (
          <Link to="/register" className="auth-secondary-action w-full">
            Вернуться к регистрации
          </Link>
        ) : null}
      </section>
    </div>
  )
}
// END_BLOCK_VERIFY_EMAIL_PAGE
