// FILE: frontend/src/pages/VerifyEmail.tsx
// VERSION: 1.2.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Email verification landing page with visible Phase-63 KrotPN logo that consumes one-time registration tokens and enters the authenticated onboarding path
//   SCOPE: Visible brand mark, token query parsing, verify-email API call, token storage after success, expired/replayed/error states
//   DEPENDS: M-009 (frontend-user), M-002 (auth API), M-071 (matrix-style-system), M-080 (visible-brand-logo-integration)
//   LINKS: M-009 (frontend-user), M-071, M-080, V-M-009, Phase-63
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   VerifyEmailPage - Verification component with Phase-63 BrandMark plus checking, success, expired/replay, and error states
//   BLOCK_VERIFY_EMAIL_PAGE - VerifyEmailPage default export
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
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
        localStorage.setItem('access_token', data.access_token)
        localStorage.setItem('refresh_token', data.refresh_token)
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
    <div className="matrix-auth-screen" data-phase53-auth-route="verify-email">
      <section className="matrix-auth-card animate-in space-y-5">
          <div className="flex items-start gap-3">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-emerald-300/12 text-emerald-100">
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
            <div>
              <div className="mb-2 flex items-center gap-2">
                <BrandMark
                  size="sm"
                  marker="[VisibleBrandLogo][phase63][PUBLIC_AUTH_LOGO_VISIBLE]"
                  data-phase56-logo="true"
                  data-phase56-legacy-src="/brand/email-logo.png"
                  data-phase63-public-auth-logo="verify-email"
                />
                <p className="text-sm font-semibold text-cyan-100">KrotPN</p>
              </div>
              <h1 className="mt-1 text-2xl font-extrabold text-white">
                {isChecking ? 'Подтверждаем email' : isSuccess ? 'Email подтверждён' : 'Ссылка недоступна'}
              </h1>
              <p className="mt-2 text-sm leading-6 muted">{message}</p>
            </div>
          </div>

          {isSuccess ? (
            <button type="button" className="btn-primary w-full py-3" onClick={() => navigate('/dashboard')}>
              <Shield className="h-4 w-4" />
              Открыть кабинет
            </button>
          ) : null}

          {isExpired ? (
            <Link to="/register" className="btn-secondary w-full py-3">
              {/* REGISTER_RESEND_AVAILABLE */}
              <RefreshCw className="h-4 w-4" />
              Отправить новую ссылку
            </Link>
          ) : null}

          {state === 'error' ? (
            <Link to="/register" className="btn-secondary w-full py-3">
              Вернуться к регистрации
            </Link>
          ) : null}
      </section>
    </div>
  )
}
// END_BLOCK_VERIFY_EMAIL_PAGE
