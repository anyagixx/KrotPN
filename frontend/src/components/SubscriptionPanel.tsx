// FILE: frontend/src/components/SubscriptionPanel.tsx
// VERSION: 1.0.0
// ROLE: UI_COMPONENT
// MAP_MODE: EXPORTS
// START_MODULE_CONTRACT
//   PURPOSE: Shared compact subscription, tariff, checkout, and calendar surface for the user dashboard and compatibility subscription route
//   SCOPE: Server-derived subscription status, canonical tariff presentation aliases, plan_id-only checkout, compact cross-month calendar, and Phase-68 dashboard-owned subscription block
//   DEPENDS: M-009 (frontend-user), M-036 (mobile-user-cabinet), M-063 (trial countdown), M-068 (paid tariff catalog), M-071 (matrix-style-system), M-074 (responsive-device-adaptation), M-075 (premium-user-cabinet)
//   LINKS: M-009, M-036, M-063, M-068, M-071, M-074, M-075, Phase-62, Phase-68
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   SubscriptionPanel - Shared compact subscription block used by /dashboard and /dashboard/subscription
//   buildCalendarMonths - Builds one or two compact month grids for active subscription range clarity
//   getPlanPresentation - Maps canonical plan slugs to Phase-68 display names, descriptions, and icons without changing backend slugs
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.1.0 - Added Phase-69 referral-bonus pending access copy via access_label.
//   LAST_CHANGE: v1.0.0 - Added Phase-68 shared dashboard-owned subscription/tariff/calendar panel.
// END_CHANGE_SUMMARY
//
// START_BLOCK_SUBSCRIPTION_PANEL
import { useQuery } from 'react-query'
import { useTranslation } from 'react-i18next'
import {
  AlertTriangle,
  Briefcase,
  Calendar,
  CreditCard,
  Laptop,
  ShieldCheck,
  User,
  Users,
  Zap,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { billingApi, deviceApi, Plan, SubscriptionStatus } from '../lib/api'
import Loading from './Loading'

const weekdayLabels = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

const planPresentation = {
  'krotpn-1': {
    name: 'KrotPN Self',
    description: 'Персональный тариф',
    icon: User,
  },
  'krotpn-6': {
    name: 'KrotPN Family',
    description: 'Тариф для семьи',
    icon: Users,
  },
  'krotpn-9': {
    name: 'KrotPN Team',
    description: 'Тариф для команды',
    icon: Briefcase,
  },
}

type SubscriptionPanelProps = {
  compact?: boolean
}

type CalendarDay = {
  key: string
  label: string
  inMonth: boolean
  active: boolean
  today: boolean
  rangeStart: boolean
  rangeEnd: boolean
  dateLabel: string
}

type CalendarMonth = {
  key: string
  title: string
  days: CalendarDay[]
}

function getPlanPresentation(plan: Plan) {
  return planPresentation[(plan.slug || '') as keyof typeof planPresentation] || {
    name: plan.name,
    description: plan.description || 'Тариф KrotPN',
    icon: Zap,
  }
}

function formatRemaining(subscription?: SubscriptionStatus) {
  if (!subscription?.has_subscription) return 'Нет активного доступа'
  if (subscription.pending_activation && subscription.access_label === 'referral-bonus') return 'Бонус ожидает подключения'
  if (subscription.pending_activation && subscription.access_label === 'trial-referral-bonus') return 'Trial + бонус ожидают'
  if (subscription.pending_activation) return 'Ожидает подключения'
  if (!subscription.is_active) return 'Доступ закончился'
  return `${subscription.remaining_days}д ${subscription.remaining_hours}ч ${subscription.remaining_minutes}м`
}

function subscriptionDescription(subscription?: SubscriptionStatus) {
  if (!subscription?.has_subscription) return 'Выберите тариф, оплатите и сразу откройте конфиг.'
  if (subscription.pending_activation && subscription.access_label === 'referral-bonus') {
    const days = subscription.pending_duration_days || 7
    return `Бонусные ${days} дней уже доступны. Таймер стартует после первого подключения.`
  }
  if (subscription.pending_activation && subscription.access_label === 'trial-referral-bonus') {
    const days = subscription.pending_duration_days || 11
    return `Конфиг уже доступен. ${days} дней trial и бонуса стартуют после первого подключения.`
  }
  if (subscription.pending_activation) return 'Конфиг уже доступен. Таймер на 4 дня стартует после первого подключения.'
  if (subscription.is_active) return 'Оставшееся время рассчитано backend по серверному времени.'
  return 'Продлите подписку, чтобы снова открыть VPN доступ.'
}

function startOfDay(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate())
}

function sameMonth(left: Date, right: Date) {
  return left.getFullYear() === right.getFullYear() && left.getMonth() === right.getMonth()
}

function buildMonthGrid(monthAnchor: Date, rangeStart: Date | null, rangeEnd: Date | null): CalendarMonth {
  const monthStart = new Date(monthAnchor.getFullYear(), monthAnchor.getMonth(), 1)
  const gridStart = new Date(monthStart)
  gridStart.setDate(monthStart.getDate() - ((monthStart.getDay() + 6) % 7))
  const today = startOfDay(new Date()).getTime()
  const formatter = new Intl.DateTimeFormat('ru-RU', { month: 'long', year: 'numeric' })

  const days = Array.from({ length: 42 }, (_, index) => {
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
      rangeStart: !!rangeStart && dayStart === rangeStart.getTime(),
      rangeEnd: !!rangeEnd && dayStart === rangeEnd.getTime(),
      dateLabel: date.toLocaleDateString('ru-RU'),
    }
  })

  return {
    key: `${monthStart.getFullYear()}-${monthStart.getMonth()}`,
    title: formatter.format(monthStart),
    days,
  }
}

function buildCalendarMonths(subscription?: SubscriptionStatus): CalendarMonth[] {
  const activeFrom = subscription?.active_from || subscription?.activated_at || subscription?.started_at
  const activeUntil = subscription?.active_until || subscription?.expires_at
  const rangeStart = activeFrom ? startOfDay(new Date(activeFrom)) : null
  const rangeEnd = activeUntil ? startOfDay(new Date(activeUntil)) : null
  const anchor = rangeStart || startOfDay(new Date())
  const months = [buildMonthGrid(anchor, rangeStart, rangeEnd)]

  if (rangeStart && rangeEnd && !sameMonth(rangeStart, rangeEnd)) {
    months.push(buildMonthGrid(rangeEnd, rangeStart, rangeEnd))
  }

  return months
}

export default function SubscriptionPanel({ compact = false }: SubscriptionPanelProps) {
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
  const calendarMonths = buildCalendarMonths(subscription)
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
    <section
      id="dashboard-subscription"
      className={compact ? 'phase68-subscription-panel grid gap-3' : 'phase68-subscription-panel grid gap-3'}
      data-phase68-dashboard-subscription="merged"
      data-phase57-subscription-countdown="server-derived"
      data-phase62-keep="[CompactDeletionAudit][phase62][PRIMARY_WORKFLOWS_PRESERVED]"
    >
      <article className="phase57-card-compact" data-phase68-subscription-status="server-derived">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase text-cyan-100/70">Подписка</p>
            <h2 className="mt-1 truncate text-xl font-extrabold">
              {subscription?.has_subscription ? subscription.plan_name || 'Доступ KrotPN' : 'Нет активного доступа'}
            </h2>
            <p className="mt-2 text-sm muted">
              {subscriptionDescription(subscription)}
            </p>
            {subscription?.active_until ? (
              <p className="mt-2 text-xs muted">
                до {new Date(subscription.active_until).toLocaleString('ru-RU')}
              </p>
            ) : null}
          </div>
          <span
            className={
              subscription?.is_active
                ? 'status-badge-success motion-status w-fit shrink-0'
                : 'status-badge-warning motion-status w-fit shrink-0'
            }
          >
            {formatRemaining(subscription)}
          </span>
        </div>
      </article>

      <section className="grid gap-3" data-phase53-tariff-catalog="canonical-three-plans" data-phase57-tariff-catalog="canonical-three-plans">
        <div className="matrix-page-header">
          <div className="min-w-0">
            <h2 className="text-xl font-extrabold">Тарифные планы</h2>
          </div>
        </div>

        <div className="phase68-plan-grid">
          {plans.map((plan) => {
            const presentation = getPlanPresentation(plan)
            const Icon = presentation.icon
            const isPopular = Boolean(plan.is_popular)
            const blockedByDevices = consumedSlots > plan.device_limit
            const usageText = `${Math.min(consumedSlots, plan.device_limit)} из ${plan.device_limit}`

            return (
              <article
                key={plan.id}
                className={`phase57-card-compact ${isPopular ? 'ring-1 ring-emerald-200/16' : ''}`}
                data-phase53-tariff-row={plan.slug}
                data-phase57-tariff-row={plan.slug}
                data-phase68-tariff-card={plan.slug || 'custom'}
              >
                <div className="flex h-full flex-col gap-4">
                  <div className="flex min-w-0 items-start gap-3">
                    <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-lg ${isPopular ? 'gradient-bg text-slate-950' : 'bg-white/8 text-cyan-100'}`}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="truncate text-lg font-extrabold">{presentation.name}</h3>
                        {isPopular ? <span className="status-badge-success">Популярный</span> : null}
                      </div>
                      <p className="mt-1 text-sm muted">{presentation.description}</p>
                      <div className="mt-2 flex flex-wrap items-end gap-x-2 gap-y-1">
                        <span className="text-2xl font-extrabold">{plan.price}₽</span>
                        <span className="text-sm muted">
                          / {plan.duration_days} {t('days')}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="mt-auto grid gap-2">
                    <div className="flex flex-wrap gap-2 text-xs">
                      <span className="metric-pill">
                        <Laptop className="h-3.5 w-3.5" />
                        {plan.device_limit} устройств
                      </span>
                      <span className={blockedByDevices ? 'danger-pill' : 'metric-pill'}>
                        Занято {usageText}
                      </span>
                    </div>
                    {blockedByDevices ? (
                      <p className="text-sm text-amber-100">
                        Для этого тарифа занято слишком много устройств. Сначала отзовите лишние в разделе конфигураций.
                      </p>
                    ) : null}
                    <button
                      disabled={blockedByDevices}
                      onClick={() => handleSubscribe(plan.id)}
                      className={`motion-interactive min-h-11 w-full rounded-lg px-3 py-2.5 disabled:cursor-not-allowed disabled:opacity-55 ${isPopular ? 'btn-primary' : 'btn-secondary'}`}
                      data-phase57-renewal-cta="plan-id-only"
                    >
                      <CreditCard className="h-5 w-5" />
                      {blockedByDevices ? 'Недоступно' : subscription?.has_subscription ? t('extend') : t('buy')}
                    </button>
                  </div>
                </div>
              </article>
            )
          })}
        </div>
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

      <section
        className="phase57-card-compact"
        data-phase45-subscription-calendar="true"
        data-phase57-subscription-calendar="active-range"
        data-phase68-subscription-calendar="compact-cross-month"
      >
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase text-cyan-100/70">Календарь подписки</p>
            <p className="mt-1 text-sm muted">
              {subscription?.pending_activation
                ? 'Даты подсветятся после первого подключения.'
                : subscription?.active_from && subscription?.active_until
                  ? `${new Date(subscription.active_from).toLocaleDateString('ru-RU')} - ${new Date(subscription.active_until).toLocaleDateString('ru-RU')}`
                  : 'Нет активного диапазона подписки.'}
            </p>
          </div>
          <Calendar className="h-5 w-5 shrink-0 text-cyan-100" />
        </div>

        <div className="phase68-calendar-months mt-3">
          {calendarMonths.map((month) => (
            <div key={month.key} className="phase68-calendar-month">
              <p className="mb-2 truncate text-center text-xs font-bold uppercase text-cyan-100/70">{month.title}</p>
              <div className="grid grid-cols-7 gap-1 text-center text-[10px]">
                {weekdayLabels.map((day) => (
                  <span key={day} className="py-0.5 font-bold text-cyan-100/70">{day}</span>
                ))}
                {month.days.map((day) => (
                  <span
                    key={day.key}
                    aria-label={day.dateLabel}
                    className={[
                      'phase68-calendar-day',
                      day.active ? 'phase68-calendar-day-active' : 'phase68-calendar-day-idle',
                      day.inMonth ? '' : 'opacity-30',
                      day.today ? 'ring-1 ring-cyan-100/50' : '',
                      day.rangeStart ? 'phase68-calendar-day-start' : '',
                      day.rangeEnd ? 'phase68-calendar-day-end' : '',
                    ].join(' ')}
                  >
                    {day.label}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>
    </section>
  )
}
// END_BLOCK_SUBSCRIPTION_PANEL
