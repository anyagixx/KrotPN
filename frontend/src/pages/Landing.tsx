// FILE: frontend/src/pages/Landing.tsx
// VERSION: 1.0.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Premium public KrotPN entry route with compact Matrix CTA, offer proof, tariff preview, and verified-email safety copy
//   SCOPE: Public landing, login/register navigation, VPN and free MTProto value presentation, public tariff preview, no checkout or access side effects
//   DEPENDS: M-073 (premium-public-site), M-009 (frontend-user), M-068 (paid tariff catalog), M-069 (brand assets), M-070 (matrix runtime), M-071 (matrix styles), M-072 (premium art direction)
//   LINKS: M-073, V-M-073, docs/plans/Phase-56.xml
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   PUBLIC_TARIFF_PREVIEW - Static fallback copy mirrored from M-068 and verified by Phase-56 smoke
//   Landing - Public premium entry component with CTA and safe tariff preview
//   BLOCK_PUBLIC_TARIFF_PREVIEW - Canonical fallback tariff preview values
//   BLOCK_LANDING_PAGE - Public route rendering
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.0.0 - Added Phase-56 premium public entry route without changing backend billing or registration semantics
// END_CHANGE_SUMMARY
//
// START_BLOCK_PUBLIC_TARIFF_PREVIEW
import { Link } from 'react-router-dom'
import { useQuery } from 'react-query'
import { ArrowRight, Check, CreditCard, LockKeyhole, RadioTower, ShieldCheck, Smartphone, Sparkles, Zap } from 'lucide-react'
import { billingApi, Plan } from '../lib/api'

const PUBLIC_TARIFF_PREVIEW: Plan[] = [
  {
    id: 0,
    slug: 'krotpn-1',
    name: 'KrotPN 1',
    description: 'Персональный тариф для одного устройства.',
    price: 369,
    currency: 'RUB',
    duration_days: 30,
    device_limit: 1,
    features: ['1 устройство', 'AmneziaWG Full Tunnel', 'Персональный Telegram MTProto proxy'],
    is_active: true,
    is_canonical: true,
    is_popular: false,
    sort_order: 10,
  },
  {
    id: 0,
    slug: 'krotpn-6',
    name: 'KrotPN 6',
    description: 'Оптимальный тариф для нескольких устройств.',
    price: 693,
    currency: 'RUB',
    duration_days: 30,
    device_limit: 6,
    features: ['До 6 устройств', 'AmneziaWG Full Tunnel', 'Персональный Telegram MTProto proxy'],
    is_active: true,
    is_canonical: true,
    is_popular: true,
    sort_order: 20,
  },
  {
    id: 0,
    slug: 'krotpn-9',
    name: 'KrotPN 9',
    description: 'Максимальный стандартный тариф KrotPN.',
    price: 936,
    currency: 'RUB',
    duration_days: 30,
    device_limit: 9,
    features: ['До 9 устройств', 'AmneziaWG Full Tunnel', 'Персональный Telegram MTProto proxy'],
    is_active: true,
    is_canonical: true,
    is_popular: false,
    sort_order: 30,
  },
]

const tariffIcons = {
  'krotpn-1': Smartphone,
  'krotpn-6': Sparkles,
  'krotpn-9': Zap,
}
// END_BLOCK_PUBLIC_TARIFF_PREVIEW

// START_BLOCK_LANDING_PAGE
export default function Landing() {
  const { data: plansData } = useQuery('public-tariff-preview', () => billingApi.getPlans(), {
    retry: false,
  })

  const plans = [...(plansData?.data?.length ? plansData.data : PUBLIC_TARIFF_PREVIEW)]
    .filter((plan) => plan.is_canonical !== false)
    .sort((a, b) => a.sort_order - b.sort_order)

  return (
    <main className="matrix-public-page animate-in" data-phase56-public-route="landing">
      <header className="matrix-public-nav">
        <Link to="/" className="matrix-public-brand" aria-label="KrotPN">
          <img src="/brand/email-logo.png" alt="" className="matrix-brand-logo" data-phase56-logo="true" />
          <span>KrotPN</span>
        </Link>
        <nav className="flex items-center gap-2">
          <Link to="/login" className="btn-secondary min-h-10 px-3 py-2 text-sm">
            Войти
          </Link>
          <Link to="/register" className="btn-primary min-h-10 px-3 py-2 text-sm" data-phase56-primary-cta="register">
            Старт
          </Link>
        </nav>
      </header>

      <section className="matrix-public-hero">
        <div className="matrix-public-hero-copy">
          <p className="matrix-kicker">VPN + Telegram MTProto proxy</p>
          <h1>KrotPN</h1>
          <p className="matrix-public-lead">
            Премиальный защищенный доступ: Full Tunnel VPN, личный кабинет и бесплатный индивидуальный
            MTProto proxy после подтверждения email.
          </p>
          <div className="matrix-public-actions">
            <Link to="/register" className="btn-primary" data-phase56-public-cta="register">
              Создать аккаунт
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link to="/login" className="btn-secondary">
              Войти в кабинет
            </Link>
          </div>
          <p className="matrix-public-proof" data-phase56-email-proof-copy="true">
            VPN, trial, кабинет и proxy активируются только после подтверждения email через письмо.
          </p>
        </div>

        <div className="matrix-public-signal" aria-label="KrotPN runtime signal">
          <div className="matrix-public-signal-row">
            <ShieldCheck className="h-5 w-5 text-emerald-100" />
            <span>verified email gate</span>
          </div>
          <div className="matrix-public-signal-row">
            <RadioTower className="h-5 w-5 text-cyan-100" />
            <span>individual MTProto SNI</span>
          </div>
          <div className="matrix-public-signal-row">
            <LockKeyhole className="h-5 w-5 text-amber-100" />
            <span>AmneziaWG Full Tunnel</span>
          </div>
        </div>
      </section>

      <section className="matrix-public-band" aria-label="KrotPN value">
        <article className="matrix-public-feature">
          <ShieldCheck className="h-5 w-5 text-emerald-100" />
          <div>
            <h2>VPN без лишнего шума</h2>
            <p>Компактный кабинет, конфиги, QR и device-bound доступ для оплаченного тарифа.</p>
          </div>
        </article>
        <article className="matrix-public-feature">
          <RadioTower className="h-5 w-5 text-cyan-100" />
          <div>
            <h2>Proxy бесплатно</h2>
            <p>После регистрации и подтверждения email выдается личный бессрочный Telegram MTProto proxy.</p>
          </div>
        </article>
        <article className="matrix-public-feature">
          <CreditCard className="h-5 w-5 text-amber-100" />
          <div>
            <h2>Тарифы честно</h2>
            <p>Оплата создается backend по plan_id; публичная страница показывает только preview.</p>
          </div>
        </article>
      </section>

      <section className="matrix-public-tariffs" data-phase56-tariff-preview="canonical-three-plans">
        <div className="matrix-page-header">
          <div className="min-w-0">
            <p className="matrix-kicker">30 days access</p>
            <h2 className="section-title">Тарифы KrotPN</h2>
            <p className="section-subtitle mt-1 text-sm">Выбор и оплата выполняются в личном кабинете после регистрации.</p>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          {plans.map((plan) => {
            const Icon = tariffIcons[(plan.slug || '') as keyof typeof tariffIcons] || Zap
            return (
              <article key={plan.slug || plan.name} className="matrix-public-tariff" data-phase56-tariff-slug={plan.slug || ''}>
                <div className="flex items-start justify-between gap-3">
                  <div className="matrix-icon-tile">
                    <Icon className="h-5 w-5" />
                  </div>
                  {plan.is_popular ? <span className="status-badge-success">Популярный</span> : null}
                </div>
                <h3>{plan.name}</h3>
                <p className="min-h-10 text-sm muted">{plan.description}</p>
                <div className="matrix-public-price">
                  <span>{plan.price} ₽</span>
                  <small>/ {plan.duration_days} дней</small>
                </div>
                <div className="metric-pill w-fit">{plan.device_limit} устройств</div>
                <ul>
                  {plan.features.slice(0, 3).map((feature) => (
                    <li key={feature}>
                      <Check className="h-4 w-4 text-emerald-100" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
              </article>
            )
          })}
        </div>
      </section>
    </main>
  )
}
// END_BLOCK_LANDING_PAGE
