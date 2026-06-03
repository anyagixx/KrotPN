// FILE: frontend/src/pages/Settings.tsx
// VERSION: 1.2.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Premium compact Matrix user settings page for profile update, language switch, and password change
//   SCOPE: Profile form, language toggle (ru/en), password change form with strong-password validation
//   DEPENDS: M-009 (frontend-user), M-002 (auth API), M-003 (user profile API), M-071 (matrix-style-system), M-075 (premium-user-cabinet)
//   LINKS: M-009 (frontend-user), M-071, M-075
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   SettingsPage - Premium compact settings component with profile, language, and password sections
//   BLOCK_SETTINGS_PAGE - SettingsPage default export with Phase-57 secondary surface markers
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v3.1.0 - Added Phase-57 compact secondary settings surface markers while preserving strong-password policy.
//   LAST_CHANGE: v3.0.0 - Applied Phase-53 compact Matrix settings surfaces.
//   LAST_CHANGE: 2026-06-01 - Reused Phase-44 strong-password policy for password changes
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY
//
// START_BLOCK_SETTINGS_PAGE
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation } from 'react-query'
import { Globe, Lock, Save, User } from 'lucide-react'
import toast from 'react-hot-toast'
import { userApi } from '../lib/api'
import { passwordPolicyHint, passwordStrengthIssues } from '../lib/passwordPolicy'
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
    const issues = passwordStrengthIssues(newPassword)
    if (issues.length > 0) {
      toast.error(`Пароль слишком простой: ${issues.join(', ')}`)
      return
    }
    changePassword.mutate()
  }

  return (
    <div className="content-section matrix-page animate-in" data-phase53-route="settings" data-phase57-route="settings">
      <div className="section-header matrix-page-header">
        <div className="min-w-0">
          <h1 className="section-title">{t('settings')}</h1>
          <p className="section-subtitle">Управляйте профилем, языком интерфейса и безопасностью учётной записи.</p>
        </div>
      </div>

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]" data-phase57-referrals-settings-compact="settings">
        <section className="phase57-card-compact">
          <div className="mb-6 flex items-center gap-3">
            <div className="matrix-icon-tile">
              <User className="h-5 w-5" />
            </div>
            <div className="min-w-0">
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

        <section className="phase57-card-compact">
          <div className="mb-6 flex items-center gap-3">
            <div className="matrix-icon-tile">
              <Globe className="h-5 w-5" />
            </div>
            <div className="min-w-0">
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

      <section className="phase57-card-compact max-w-3xl" data-phase57-settings-password-policy="strong-password">
        <div className="mb-6 flex items-center gap-3">
          <div className="matrix-icon-tile">
            <Lock className="h-5 w-5" />
          </div>
          <div className="min-w-0">
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
              minLength={10}
            />
            <p className="mt-2 text-xs leading-5 muted">{passwordPolicyHint}</p>
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
// END_BLOCK_SETTINGS_PAGE
