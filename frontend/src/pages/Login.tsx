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
    <div className="min-h-screen px-4 py-8">
      <div className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-6xl grid-cols-1 overflow-hidden rounded-[32px] border border-white/10 bg-slate-950/35 shadow-[0_36px_120px_rgba(2,10,14,0.55)] backdrop-blur-sm lg:grid-cols-[1.08fr_0.92fr]">
        <section className="hidden border-r border-white/5 p-10 lg:flex lg:flex-col lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-3 rounded-full border border-emerald-200/12 bg-emerald-300/10 px-4 py-2 text-sm font-semibold text-emerald-100">
              <Shield className="h-4 w-4" />
              KrotVPN Secure Access
            </div>
            <h1 className="mt-8 max-w-xl text-5xl font-extrabold tracking-tight text-white">
              Премиальный VPN-кабинет для приватного доступа без лишней сложности
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-slate-300">
              Контролируйте подписку, конфигурацию, QR-код и защиту устройства из одного чистого интерфейса.
            </p>
          </div>

          <div className="grid gap-4">
            {[
              ['AmneziaWG', 'Обфускация и стабильный доступ даже в сложных сетях.'],
              ['Config + QR', 'Скачивание конфига и быстрый импорт на телефон за пару кликов.'],
              ['Referral бонусы', 'Приглашайте друзей и продлевайте доступ бонусными днями.'],
            ].map(([title, description]) => (
              <div key={title} className="panel-soft p-5">
                <p className="text-lg font-bold">{title}</p>
                <p className="mt-2 text-sm muted">{description}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="flex items-center justify-center p-6 md:p-10">
          <div className="w-full max-w-md">
            <div className="mb-8 text-center lg:text-left">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[24px] bg-emerald-300/12 text-emerald-200 lg:mx-0">
                <Shield className="h-8 w-8" />
              </div>
              <h2 className="mt-5 text-3xl font-extrabold">{t('loginTitle')}</h2>
              <p className="mt-2 text-sm muted">Войдите, чтобы управлять подключением и подпиской.</p>
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
            </form>

            <div className="mt-6 text-center text-sm muted">
              {t('noAccount')}{' '}
              <Link to="/register" className="font-semibold text-cyan-100 hover:text-emerald-100">
                {t('register')}
              </Link>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
