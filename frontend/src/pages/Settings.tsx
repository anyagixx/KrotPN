import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation } from 'react-query'
import { Globe, Lock, Save, User } from 'lucide-react'
import toast from 'react-hot-toast'
import { userApi } from '../lib/api'
import { useAuthStore } from '../stores/auth'

export default function Settings() {
  const { t, i18n } = useTranslation()
  const { user, setUser } = useAuthStore()

  const [name, setName] = useState(user?.name || '')
  const [language, setLanguage] = useState(user?.language || 'ru')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')

  const updateProfile = useMutation((data: { name?: string; language?: string }) => userApi.updateProfile(data), {
    onSuccess: (response: any) => {
      setUser(response.data)
      i18n.changeLanguage(response.data.language)
      localStorage.setItem('language', response.data.language)
      toast.success(t('success'))
    },
    onError: () => {
      toast.error(t('error'))
    },
  })

  const changePassword = useMutation(() => userApi.changePassword(currentPassword, newPassword), {
    onSuccess: () => {
      setCurrentPassword('')
      setNewPassword('')
      toast.success(t('passwordChanged'))
    },
    onError: () => {
      toast.error(t('error'))
    },
  })

  const handleSaveProfile = () => {
    updateProfile.mutate({ name, language })
  }

  const handleChangePassword = (e: React.FormEvent) => {
    e.preventDefault()
    if (newPassword.length < 8) {
      toast.error('Пароль должен быть не короче 8 символов')
      return
    }
    changePassword.mutate()
  }

  return (
    <div className="content-section animate-in">
      <div className="section-header">
        <div>
          <h1 className="section-title">{t('settings')}</h1>
          <p className="section-subtitle">Управляйте профилем, языком интерфейса и безопасностью учётной записи.</p>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <section className="panel p-6">
          <div className="mb-6 flex items-center gap-3">
            <div className="rounded-2xl bg-white/8 p-3 text-cyan-100">
              <User className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold">{t('profile')}</h2>
              <p className="text-sm muted">Основные данные аккаунта.</p>
            </div>
          </div>

          <div className="space-y-4">
            <label className="block">
              <span className="mb-2 block text-sm muted">{t('email')}</span>
              <input type="email" value={user?.email || ''} disabled className="input opacity-60" />
            </label>

            <label className="block">
              <span className="mb-2 block text-sm muted">Имя</span>
              <input type="text" value={name} onChange={(e) => setName(e.target.value)} className="input" placeholder="Ваше имя" />
            </label>

            <button onClick={handleSaveProfile} disabled={updateProfile.isLoading} className="btn-primary">
              <Save className="h-5 w-5" />
              {t('save')}
            </button>
          </div>
        </section>

        <section className="panel p-6">
          <div className="mb-6 flex items-center gap-3">
            <div className="rounded-2xl bg-emerald-300/12 p-3 text-emerald-200">
              <Globe className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold">{t('language')}</h2>
              <p className="text-sm muted">Переключение языка интерфейса в один клик.</p>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <button
              onClick={() => {
                setLanguage('ru')
                updateProfile.mutate({ language: 'ru' })
              }}
              className={language === 'ru' ? 'btn-primary' : 'btn-secondary'}
            >
              🇷🇺 Русский
            </button>
            <button
              onClick={() => {
                setLanguage('en')
                updateProfile.mutate({ language: 'en' })
              }}
              className={language === 'en' ? 'btn-primary' : 'btn-secondary'}
            >
              🇬🇧 English
            </button>
          </div>
        </section>
      </div>

      <section className="panel max-w-3xl p-6">
        <div className="mb-6 flex items-center gap-3">
          <div className="rounded-2xl bg-red-300/10 p-3 text-red-100">
            <Lock className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold">{t('changePassword')}</h2>
            <p className="text-sm muted">Используйте длинный уникальный пароль для защиты аккаунта.</p>
          </div>
        </div>

        <form onSubmit={handleChangePassword} className="grid gap-4">
          <label className="block">
            <span className="mb-2 block text-sm muted">{t('currentPassword')}</span>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="input"
              required
            />
          </label>

          <label className="block">
            <span className="mb-2 block text-sm muted">{t('newPassword')}</span>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="input"
              required
              minLength={8}
            />
          </label>

          <div>
            <button type="submit" disabled={changePassword.isLoading} className="btn-secondary">
              <Lock className="h-5 w-5" />
              {t('changePassword')}
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}
