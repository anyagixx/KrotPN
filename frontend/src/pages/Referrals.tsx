import { useQuery } from 'react-query'
import { useTranslation } from 'react-i18next'
import { Gift, Users, Copy, Check } from 'lucide-react'
import { useState } from 'react'
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
  
  const referralCode = data?.data?.code
  const referralLink = `${window.location.origin}/register?ref=${referralCode}`
  const stats = statsData?.data
  
  const handleCopy = async (text: string) => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    toast.success(t('copied'))
    setTimeout(() => setCopied(false), 2000)
  }
  
  return (
    <div className="space-y-8 animate-in max-w-2xl">
      <div>
        <h1 className="text-3xl font-bold">{t('referralProgram')}</h1>
        <p className="text-dark-400 mt-2">
          {t('referralInstructions')}
        </p>
      </div>
      
      {/* Stats */}
      <div className="grid grid-cols-2 gap-4">
        <div className="glass-card text-center">
          <Users className="w-8 h-8 mx-auto mb-2 text-primary-400" />
          <p className="text-3xl font-bold">{stats?.referrals_count || 0}</p>
          <p className="text-dark-400">{t('referralsCount')}</p>
        </div>
        <div className="glass-card text-center">
          <Gift className="w-8 h-8 mx-auto mb-2 text-green-400" />
          <p className="text-3xl font-bold">{stats?.bonus_days || 0}</p>
          <p className="text-dark-400">{t('bonusDays')}</p>
        </div>
      </div>
      
      {/* Referral Code */}
      <div className="glass-card">
        <h3 className="font-semibold mb-4">{t('referralCode')}</h3>
        <div className="flex gap-2">
          <input
            type="text"
            value={referralCode || ''}
            readOnly
            className="input font-mono"
          />
          <button
            onClick={() => handleCopy(referralCode || '')}
            className="btn-secondary"
          >
            {copied ? <Check className="w-5 h-5 text-green-400" /> : <Copy className="w-5 h-5" />}
          </button>
        </div>
      </div>
      
      {/* Referral Link */}
      <div className="glass-card">
        <h3 className="font-semibold mb-4">{t('referralLink')}</h3>
        <div className="flex gap-2">
          <input
            type="text"
            value={referralLink}
            readOnly
            className="input font-mono text-sm"
          />
          <button
            onClick={() => handleCopy(referralLink)}
            className="btn-primary"
          >
            <Copy className="w-5 h-5" />
            {t('copyConfig')}
          </button>
        </div>
      </div>
      
      {/* Bonus Info */}
      <div className="glass-card gradient-bg text-center">
        <Gift className="w-12 h-12 mx-auto mb-4" />
        <h3 className="text-xl font-bold mb-2">
          {t('referralBonus', { days: 7 })}
        </h3>
        <p className="text-white/80">
          За каждого приглашенного друга вы получите +7 дней подписки!
        </p>
      </div>
    </div>
  )
}
