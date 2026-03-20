import { useQuery } from 'react-query'
import { useTranslation } from 'react-i18next'
import { Check, Zap, Crown, Rocket } from 'lucide-react'
import toast from 'react-hot-toast'
import { billingApi } from '../lib/api'
import Loading from '../components/Loading'

const planIcons = {
  basic: Zap,
  pro: Crown,
  premium: Rocket,
}

export default function Subscription() {
  const { t } = useTranslation()
  
  const { data: plansData, isLoading: plansLoading } = useQuery(
    'plans',
    () => billingApi.getPlans()
  )
  
  const { data: subData, isLoading: subLoading } = useQuery(
    'subscription',
    () => billingApi.getSubscription()
  )
  
  if (plansLoading || subLoading) {
    return <Loading text={t('loading')} />
  }
  
  const plans = plansData?.data || []
  const subscription = subData?.data
  
  const handleSubscribe = async (planId: number) => {
    try {
      const { data } = await billingApi.createPayment(planId)
      if (data.payment_url) {
        window.location.href = data.payment_url
      }
    } catch {
      toast.error(t('error'))
    }
  }
  
  return (
    <div className="space-y-8 animate-in">
      <div>
        <h1 className="text-3xl font-bold">{t('plans')}</h1>
        <p className="text-dark-400 mt-2">
          Выберите подходящий тарифный план
        </p>
      </div>
      
      {/* Current Subscription */}
      {subscription && (
        <div className="glass-card border-primary-500/50">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-dark-400">{t('currentPlan')}</p>
              <p className="text-xl font-bold">{subscription.plan_name}</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-dark-400">{t('daysLeft')}</p>
              <p className="text-2xl font-bold gradient-text">
                {subscription.days_left}
              </p>
            </div>
          </div>
        </div>
      )}
      
      {/* Plans Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {plans.map((plan, index) => {
          const Icon = planIcons[plan.name.toLowerCase() as keyof typeof planIcons] || Zap
          const isPopular = index === 1
          
          return (
            <div
              key={plan.id}
              className={`glass-card relative ${isPopular ? 'border-primary-500/50' : ''}`}
            >
              {isPopular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-primary-500 text-sm font-medium">
                  Популярный
                </div>
              )}
              
              <div className="text-center mb-6">
                <div className={`w-16 h-16 mx-auto rounded-2xl flex items-center justify-center mb-4 ${
                  isPopular ? 'gradient-bg' : 'bg-dark-700'
                }`}>
                  <Icon className="w-8 h-8" />
                </div>
                <h3 className="text-xl font-bold">{plan.name}</h3>
                <div className="mt-2">
                  <span className="text-3xl font-bold">{plan.price}₽</span>
                  <span className="text-dark-400">/{plan.duration_days} {t('days')}</span>
                </div>
              </div>
              
              <ul className="space-y-3 mb-6">
                {plan.features?.map((feature: string, i: number) => (
                  <li key={i} className="flex items-center gap-2 text-dark-300">
                    <Check className="w-5 h-5 text-green-400 flex-shrink-0" />
                    {feature}
                  </li>
                ))}
              </ul>
              
              <button
                onClick={() => handleSubscribe(plan.id)}
                className={isPopular ? 'btn-primary w-full' : 'btn-secondary w-full'}
              >
                {subscription ? t('extend') : t('buy')}
              </button>
            </div>
          )
        })}
      </div>
      
      {/* Trial Banner */}
      {!subscription && (
        <div className="glass-card gradient-bg text-center">
          <h3 className="text-xl font-bold mb-2">{t('trial')}</h3>
          <p className="text-white/80">
            {t('trialDays', { days: 3 })} — без привязки карты!
          </p>
        </div>
      )}
    </div>
  )
}
