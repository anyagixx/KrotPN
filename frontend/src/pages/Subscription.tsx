// FILE: frontend/src/pages/Subscription.tsx
// VERSION: 1.2.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact Matrix subscription page with current status, readable plan rows, and payment initiation
//   SCOPE: Subscription status summary, compact plan list, payment creation and redirect to payment URL
//   DEPENDS: M-009 (frontend-user), M-004 (billing API), M-036 (mobile-user-cabinet), M-038 (compact-ui-system), M-071 (matrix-style-system)
//   LINKS: M-009 (frontend-user), M-036 (mobile-user-cabinet), M-038 (compact-ui-system), M-071
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
//   LAST_CHANGE: v2.12.0 - Applied Phase-53 compact Matrix tariff/status/calendar surfaces without changing checkout shape.
//   LAST_CHANGE: v2.11.0 - Added Phase-50 three paid tariffs with device-limit usage and downgrade guard UX.
//   LAST_CHANGE: v2.10.0 - Added Phase-45 pending trial countdown and compact active-date calendar.
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.9.0 - Reworked billing surface into compact mobile-first plan rows for Phase-23
// END_CHANGE_SUMMARY
//
// START_BLOCK_SUBSCRIPTION_PAGE
import { useQuery } from 'react-query'
import { useTranslation } from 'react-i18next'
import { AlertTriangle, Calendar, Check, CreditCard, Crown, Laptop, Rocket, ShieldCheck, Smartphone, Zap } from 'lucide-react'
import toast from 'react-hot-toast'
import { billingApi, deviceApi, SubscriptionStatus } from '../lib/api'
import Loading from '../components/Loading'

const planIcons = {
  'krotpn-1': Smartphone,
  'krotpn-6': Crown,
  'krotpn-9': Rocket,
}

const weekdayLabels = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

function formatRemaining(subscription?: SubscriptionStatus) {
  if (!subscription?.has_subscription) return 'Нет активного доступа'
  if (subscription.pending_activation) return 'Trial начнется после первого VPN подключения'
  if (!subscription.is_active) return 'Доступ закончился'
  return `${subscription.remaining_days}д ${subscription.remaining_hours}ч ${subscription.remaining_minutes}м`
}

function subscriptionDescription(subscription?: SubscriptionStatus) {
  if (!subscription?.has_subscription) return 'Выберите тариф, оплатите и сразу откройте конфиг.'
  if (subscription.pending_activation) return 'Конфиг уже доступен. Таймер на 4 дня стартует после первого успешного VPN handshake.'
  if (subscription.is_active) return 'Оставшееся время рассчитано backend по серверному времени.'
  return 'Продлите подписку, чтобы снова открыть VPN доступ.'
}

function startOfDay(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate())
}

function buildCalendarDays(subscription?: SubscriptionStatus) {
  const activeFrom = subscription?.active_from || subscription?.activated_at || subscription?.started_at
  const activeUntil = subscription?.active_until || subscription?.expires_at
  const rangeStart = activeFrom ? startOfDay(new Date(activeFrom)) : null
  const rangeEnd = activeUntil ? startOfDay(new Date(activeUntil)) : null
  const anchor = rangeStart || startOfDay(new Date())
  const monthStart = new Date(anchor.getFullYear(), anchor.getMonth(), 1)
  const gridStart = new Date(monthStart)
  gridStart.setDate(monthStart.getDate() - ((monthStart.getDay() + 6) % 7))
  const today = startOfDay(new Date()).getTime()

  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(gridStart)
    date.setDate(gridStart.getDate() + index)
    const dayStart = startOfDay(date).getTime()
    const active = !!rangeStart && !!rangeEnd && dayStart >= rangeStart.getTime() && dayStart <= rangeEnd.getTime()

    return {
      key: date.toISOString(),
      label: String(date.getDate()),
      inMonth: date.getMonth() === monthStart.getMonth(),
      active,
      today: dayStart === today,
    }
  })
}

export default function Subscription() {
  const { t } = useTranslation()

  const { data: plansData, isLoading: plansLoading, isError: plansError } = useQuery('plans', () => billingApi.getPlans())
  const { data: subData, isLoading: subLoading, isError: subError } = useQuery('subscription', () => billingApi.getSubscription(), {
    refetchInterval: 30000,
  })
  const { data: deviceData } = useQuery('devices-for-tariffs', () => deviceApi.list(), {
    retry: false,
    refetchInterval: 30000,
  })

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

  const plans = [...(plansData?.data || [])].sort((a, b) => a.sort_order - b.sort_order)
  const subscription = subData?.data
  const calendarDays = buildCalendarDays(subscription)
  const consumedSlots = deviceData?.data.consumed_slots ?? 0

  const handleSubscribe = async (planId: number) => {
    try {
      const { data } = await billingApi.createPayment(planId)
      if (data.payment_url) {
        window.location.href = data.payment_url
      }
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || t('error'))
    }
  }

  return (
    <div className="content-section matrix-page animate-in" data-phase53-route="subscription">
      <section className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(260px,0.75fr)]">
        <article className="panel p-4 sm:p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-bold uppercase text-cyan-100/70">Текущая подписка</p>
              <h1 className="mt-1 truncate text-2xl font-extrabold">
                {subscription?.has_subscription ? subscription.plan_name || 'Trial' : 'Нет активного доступа'}
              </h1>
              <p className="mt-2 text-sm muted">
                {subscriptionDescription(subscription)}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className={subscription?.is_active ? 'status-badge-success w-fit' : 'status-badge-warning w-fit'}>
                  {formatRemaining(subscription)}
                </span>
                {subscription?.active_until ? (
                  <span className="text-xs muted">
                    до {new Date(subscription.active_until).toLocaleString('ru-RU')}
                  </span>
                ) : null}
              </div>
            </div>
            <span
              className={
                subscription?.pending_activation
                  ? 'status-badge-warning shrink-0'
                  : subscription?.is_active
                    ? 'status-badge-success shrink-0'
                    : 'status-badge-warning shrink-0'
              }
            >
              {subscription?.pending_activation ? 'pending' : subscription?.is_active ? 'active' : 'inactive'}
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

      <section className="panel p-4 sm:p-5" data-phase45-subscription-calendar="true">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase text-cyan-100/70">Календарь доступа</p>
            <h2 className="mt-1 text-xl font-extrabold">Активные даты</h2>
            <p className="mt-1 text-sm muted">
              {subscription?.pending_activation
                ? 'Даты подсветятся после первого VPN подключения.'
                : subscription?.active_from && subscription?.active_until
                  ? `${new Date(subscription.active_from).toLocaleDateString('ru-RU')} - ${new Date(subscription.active_until).toLocaleDateString('ru-RU')}`
                  : 'Нет активного диапазона подписки.'}
            </p>
          </div>
          <Calendar className="h-5 w-5 shrink-0 text-cyan-100" />
        </div>

        <div className="mt-4 grid grid-cols-7 gap-1 text-center text-xs">
          {weekdayLabels.map((day) => (
            <span key={day} className="py-1 font-bold text-cyan-100/70">{day}</span>
          ))}
          {calendarDays.map((day) => (
            <span
              key={day.key}
              className={[
                'flex aspect-square min-h-9 items-center justify-center rounded-md border text-sm font-semibold',
                day.active ? 'border-emerald-200/50 bg-emerald-300/18 text-emerald-50' : 'border-white/8 bg-white/[0.03] text-slate-100',
                day.inMonth ? '' : 'opacity-35',
                day.today ? 'ring-1 ring-cyan-100/50' : '',
              ].join(' ')}
            >
              {day.label}
            </span>
          ))}
        </div>
      </section>

      <section className="grid gap-3" data-phase53-tariff-catalog="canonical-three-plans">
        <div className="matrix-page-header">
          <div className="min-w-0">
            <h2 className="text-xl font-extrabold">{t('plans')}</h2>
            <p className="mt-1 text-sm muted">Три тарифа KrotPN на 30 дней. Оплата создается backend по выбранному plan_id.</p>
          </div>
        </div>

        {plans.map((plan) => {
          const Icon = planIcons[(plan.slug || '') as keyof typeof planIcons] || Zap
          const isPopular = Boolean(plan.is_popular)
          const blockedByDevices = consumedSlots > plan.device_limit
          const usageText = `${Math.min(consumedSlots, plan.device_limit)} из ${plan.device_limit}`

          return (
            <article
              key={plan.id}
              className={`panel p-4 sm:p-5 ${isPopular ? 'ring-1 ring-emerald-200/16' : ''}`}
              data-phase53-tariff-row={plan.slug}
            >
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div className="flex min-w-0 items-start gap-3">
                  <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-lg ${isPopular ? 'gradient-bg text-slate-950' : 'bg-white/8 text-cyan-100'}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="truncate text-xl font-extrabold">{plan.name}</h3>
                      {isPopular ? <span className="status-badge-success">Популярный</span> : null}
                    </div>
                    <p className="mt-1 text-sm muted">{plan.description}</p>
                    <div className="mt-1 flex flex-wrap items-end gap-x-2 gap-y-1">
                      <span className="text-2xl font-extrabold">{plan.price}₽</span>
                      <span className="text-sm muted">
                        / {plan.duration_days} {t('days')}
                      </span>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs">
                      <span className="metric-pill">
                        <Laptop className="h-3.5 w-3.5" />
                        {plan.device_limit} устройств
                      </span>
                      <span className={blockedByDevices ? 'danger-pill' : 'metric-pill'}>
                        Занято {usageText}
                      </span>
                    </div>
                    {blockedByDevices ? (
                      <p className="mt-2 text-sm text-amber-100">
                        Для этого тарифа занято слишком много устройств. Сначала отзовите лишние в разделе конфигураций.
                      </p>
                    ) : null}
                  </div>
                </div>

                <button
                  disabled={blockedByDevices}
                  onClick={() => handleSubscribe(plan.id)}
                  className={`min-h-11 w-full rounded-lg px-3 py-2.5 disabled:cursor-not-allowed disabled:opacity-55 md:w-auto ${isPopular ? 'btn-primary' : 'btn-secondary'}`}
                >
                  <CreditCard className="h-5 w-5" />
                  {blockedByDevices ? 'Недоступно' : subscription?.has_subscription ? t('extend') : t('buy')}
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
              <p className="mt-1 text-sm muted">Бесплатный trial на 4 дня начнется после первого VPN подключения.</p>
            </div>
          </div>
        </section>
      ) : null}
    </div>
  )
}
// END_BLOCK_SUBSCRIPTION_PAGE
