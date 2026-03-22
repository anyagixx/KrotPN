import { useState } from 'react'
import { useQuery } from 'react-query'
import { useTranslation } from 'react-i18next'
import { Check, Copy, Gift, Link2, Users } from 'lucide-react'
import toast from 'react-hot-toast'
import { referralApi } from '../lib/api'
import Loading from '../components/Loading'

export default function Referrals() {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)

  const { data, isLoading } = useQuery('referrals', () => referralApi.getCode())
  const { data: statsData } = useQuery('referral-stats', () => referralApi.getStats())

  if (isLoading) {
    return <Loading text={t('loading')} />
  }

  const referralCode = data?.data?.code || ''
  const referralLink = `${window.location.origin}/register?ref=${referralCode}`
  const stats = statsData?.data

  const handleCopy = async (text: string) => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    toast.success(t('copied'))
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="content-section animate-in">
      <div className="section-header">
        <div>
          <h1 className="section-title">{t('referralProgram')}</h1>
          <p className="section-subtitle">Делитесь ссылкой, приглашайте друзей и получайте продление доступа бонусными днями.</p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="metric-card text-center">
          <Users className="mx-auto h-8 w-8 text-cyan-100" />
          <p className="metric-value">{stats?.total_referrals || 0}</p>
          <p className="mt-2 text-sm muted">{t('referralsCount')}</p>
        </div>
        <div className="metric-card text-center">
          <Gift className="mx-auto h-8 w-8 text-emerald-200" />
          <p className="metric-value">{stats?.bonus_days_earned || 0}</p>
          <p className="mt-2 text-sm muted">{t('bonusDays')}</p>
        </div>
      </div>

      <div className="panel p-6">
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-white/8 p-3 text-cyan-100">
            <Gift className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold">{t('referralCode')}</h2>
            <p className="text-sm muted">Используйте код в ручных приглашениях или чатах.</p>
          </div>
        </div>
        <div className="mt-5 flex flex-col gap-3 sm:flex-row">
          <input type="text" value={referralCode} readOnly className="input font-mono" />
          <button onClick={() => handleCopy(referralCode)} className="btn-secondary sm:min-w-[150px]">
            {copied ? <Check className="h-5 w-5 text-emerald-200" /> : <Copy className="h-5 w-5" />}
            Копировать
          </button>
        </div>
      </div>

      <div className="panel p-6">
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-emerald-300/12 p-3 text-emerald-200">
            <Link2 className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold">{t('referralLink')}</h2>
            <p className="text-sm muted">Полная ссылка на регистрацию с уже подставленным кодом.</p>
          </div>
        </div>
        <div className="mt-5 flex flex-col gap-3 sm:flex-row">
          <input type="text" value={referralLink} readOnly className="input font-mono text-sm" />
          <button onClick={() => handleCopy(referralLink)} className="btn-primary sm:min-w-[170px]">
            <Copy className="h-5 w-5" />
            Копировать ссылку
          </button>
        </div>
      </div>

      <div className="glass p-6 text-center">
        <Gift className="mx-auto h-12 w-12 text-emerald-100" />
        <h3 className="mt-4 text-2xl font-extrabold">{t('referralBonus', { days: 7 })}</h3>
        <p className="mt-2 text-sm text-slate-100">Каждый оплаченный реферал приносит тебе дополнительные 7 дней доступа.</p>
      </div>
    </div>
  )
}
