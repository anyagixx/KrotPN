// FILE: frontend/src/pages/Subscription.tsx
// VERSION: 1.1.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact subscription page with current status, readable plan rows, and payment initiation
//   SCOPE: Subscription status summary, compact plan list, payment creation and redirect to payment URL
//   DEPENDS: M-009 (frontend-user), M-004 (billing API), M-036 (mobile-user-cabinet), M-038 (compact-ui-system)
//   LINKS: M-009 (frontend-user), M-036 (mobile-user-cabinet), M-038 (compact-ui-system)
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   SubscriptionPage - Compact plans listing and subscription status component
//   planIcons - Icon mapping for plan rows
//   BLOCK_SUBSCRIPTION_PAGE - SubscriptionPage default export with compact billing workflow
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.9.0 - Reworked billing surface into compact mobile-first plan rows for Phase-23
// END_CHANGE_SUMMARY
//
// START_BLOCK_SUBSCRIPTION_PAGE
import { useQuery } from 'react-query'
import { useTranslation } from 'react-i18next'
import { AlertTriangle, Calendar, Check, CreditCard, Crown, Rocket, ShieldCheck, Zap } from 'lucide-react'
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

  const { data: plansData, isLoading: plansLoading, isError: plansError } = useQuery('plans', () => billingApi.getPlans())
  const { data: subData, isLoading: subLoading, isError: subError } = useQuery('subscription', () => billingApi.getSubscription())

  if (plansLoading || subLoading) {
    return <Loading text={t('loading')} />
  }

  if (plansError || subError) {
    return (
      <div className="empty-state">
        <AlertTriangle className="h-10 w-10 text-red-200" />
        <div>
          <p className="text-lg font-semibold">Не удалось загрузить тарифы</p>
          <p className="mt-1 text-sm muted">Сервис оплаты или backend сейчас недоступен. Попробуй позже.</p>
        </div>
      </div>
    )
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
    <div className="content-section animate-in">
      <section className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(260px,0.75fr)]">
        <article className="panel p-4 sm:p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-bold uppercase text-cyan-100/70">Текущая подписка</p>
              <h1 className="mt-1 truncate text-2xl font-extrabold">
                {subscription?.has_subscription ? subscription.plan_name || 'Активная подписка' : 'Нет активного доступа'}
              </h1>
              <p className="mt-2 text-sm muted">
                {subscription?.has_subscription
                  ? `До окончания осталось ${subscription.days_left} дней.`
                  : 'Выберите тариф, оплатите и сразу откройте конфиг.'}
              </p>
            </div>
            <span className={subscription?.has_subscription ? 'status-badge-success shrink-0' : 'status-badge-warning shrink-0'}>
              {subscription?.has_subscription ? 'active' : 'inactive'}
            </span>
          </div>
        </article>

        <article className="panel p-4 sm:p-5">
          <div className="flex items-start gap-3">
            <ShieldCheck className="mt-1 h-5 w-5 shrink-0 text-emerald-200" />
            <div className="min-w-0">
              <h2 className="text-lg font-bold">Что включено</h2>
              <p className="mt-1 text-sm muted">VPN-туннель, личный кабинет, QR, `.conf` и device-bound конфиги.</p>
            </div>
          </div>
        </article>
      </section>

      <section className="grid gap-3">
        <div className="flex items-end justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-xl font-extrabold">{t('plans')}</h2>
            <p className="mt-1 text-sm muted">Компактный список тарифов для оплаты или продления.</p>
          </div>
        </div>

        {plans.map((plan, index) => {
          const Icon = planIcons[plan.name.toLowerCase() as keyof typeof planIcons] || Zap
          const isPopular = index === 1

          return (
            <article key={plan.id} className={`panel p-4 sm:p-5 ${isPopular ? 'ring-1 ring-emerald-200/16' : ''}`}>
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div className="flex min-w-0 items-start gap-3">
                  <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${isPopular ? 'gradient-bg text-slate-950' : 'bg-white/8 text-cyan-100'}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="truncate text-xl font-extrabold">{plan.name}</h3>
                      {isPopular ? <span className="status-badge-success">Популярный</span> : null}
                    </div>
                    <div className="mt-1 flex flex-wrap items-end gap-x-2 gap-y-1">
                      <span className="text-2xl font-extrabold">{plan.price}₽</span>
                      <span className="text-sm muted">
                        / {plan.duration_days} {t('days')}
                      </span>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => handleSubscribe(plan.id)}
                  className={`min-h-11 w-full rounded-xl px-3 py-2.5 md:w-auto ${isPopular ? 'btn-primary' : 'btn-secondary'}`}
                >
                  <CreditCard className="h-5 w-5" />
                  {subscription?.has_subscription ? t('extend') : t('buy')}
                </button>
              </div>

              {plan.features?.length ? (
                <ul className="mt-4 grid gap-2 sm:grid-cols-2">
                  {plan.features.map((feature: string, i: number) => (
                    <li key={i} className="flex min-w-0 items-start gap-2 text-sm text-slate-100">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-200" />
                      <span className="min-w-0 break-words">{feature}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </article>
          )
        })}
      </section>

      {plans.length === 0 ? (
        <div className="empty-state">
          <ShieldCheck className="h-10 w-10 text-cyan-100" />
          <div>
            <p className="text-lg font-semibold">Активные планы пока не опубликованы</p>
            <p className="mt-1 text-sm muted">Когда администратор добавит тарифы, они появятся здесь автоматически.</p>
          </div>
        </div>
      ) : null}

      {!subscription?.has_subscription ? (
        <section className="panel p-4 sm:p-5">
          <div className="flex items-start gap-3">
            <Calendar className="mt-1 h-5 w-5 shrink-0 text-cyan-100" />
            <div className="min-w-0">
              <h3 className="text-lg font-bold">{t('trial')}</h3>
              <p className="mt-1 text-sm muted">{t('trialDays', { days: 3 })} и быстрый вход в личный кабинет.</p>
            </div>
          </div>
        </section>
      ) : null}
    </div>
  )
}
// END_BLOCK_SUBSCRIPTION_PAGE
