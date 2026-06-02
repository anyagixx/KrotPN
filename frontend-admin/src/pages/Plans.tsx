// FILE: frontend-admin/src/pages/Plans.tsx
// VERSION: 1.0.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Admin page for viewing the protected canonical paid tariff matrix
//   SCOPE: Display Phase-50 canonical tariff matrix with price, device limit, active/popular state, and no accidental CRUD controls
//   DEPENDS: M-010 (frontend-admin), M-006 (admin API)
//   LINKS: M-010
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   PlansPage - Main admin plans page component
//   getFeatures - Helper: parse plan features from array or JSON string
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.1.0 - Reworked admin plans into Phase-50 compact canonical matrix without create/edit/delete affordances.
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY

import { useQuery } from 'react-query'
import { Check, CreditCard, ShieldCheck, Star } from 'lucide-react'
import { adminApi } from '../lib/api'
import type { AdminPlan } from '../types'

// START_BLOCK: getFeatures
// Parses plan features from array or JSON string into string[]
// DEPENDS: none (pure function)
function getFeatures(plan: AdminPlan): string[] {
  if (Array.isArray(plan.features)) return plan.features
  if (typeof plan.features === 'string') {
    try {
      return JSON.parse(plan.features)
    } catch {
      return []
    }
  }
  return []
}
// END_BLOCK: getFeatures

// START_BLOCK: Plans
// Admin plans page: protected Phase-50 tariff matrix
// DEPENDS: M-010 (frontend-admin), M-006 (admin API via adminApi)
//   - adminApi.getPlans
export default function Plans() {
  const { data: plans, isLoading } = useQuery('admin-plans', () => adminApi.getPlans())
  const items = [...(plans?.data || [])].sort((a: AdminPlan, b: AdminPlan) => (a.sort_order || 0) - (b.sort_order || 0))
  const activeCount = items.filter((plan: AdminPlan) => plan.is_active).length
  const totalDevices = items.reduce((sum: number, plan: AdminPlan) => sum + plan.device_limit, 0)

  return (
    <div className="page-shell">
      <div className="page-header">
        <div>
          <h1 className="page-title">Тарифы KrotPN</h1>
          <p className="page-subtitle">Защищенная матрица Phase-50: 1, 6 и 9 устройств на 30 дней.</p>
        </div>

        <div className="grid grid-cols-2 gap-2 sm:flex sm:items-center">
          <div className="panel-soft px-4 py-3 text-sm">
            <p className="muted">Активных планов</p>
            <p className="mt-1 font-bold">{activeCount} / 3</p>
          </div>
          <div className="panel-soft px-4 py-3 text-sm">
            <p className="muted">Сумма лимитов</p>
            <p className="mt-1 font-bold">{totalDevices}</p>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="empty-state">
          <CreditCard className="h-10 w-10 text-cyan-200" />
          <div>
            <p className="text-lg font-semibold">Загружаем тарифы</p>
            <p className="mt-1 text-sm muted">Получаем список планов из billing admin API.</p>
          </div>
        </div>
      ) : items.length === 0 ? (
        <div className="empty-state">
          <CreditCard className="h-10 w-10 text-cyan-200" />
          <div>
            <p className="text-lg font-semibold">Канонические тарифы не найдены</p>
            <p className="mt-1 text-sm muted">Backend должен создать их через Phase-50 catalog convergence.</p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-3">
          {items.map((plan: AdminPlan) => (
            <div key={plan.id} className={`panel p-4 ${!plan.is_active ? 'opacity-65' : ''}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="truncate text-xl font-extrabold">{plan.name}</h3>
                    {plan.is_popular ? (
                      <span className="metric-pill">
                        <Star className="h-3.5 w-3.5" />
                        Популярный
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-xs font-semibold uppercase text-cyan-100/70">{plan.slug}</p>
                </div>
                <span className={plan.is_active ? 'metric-pill shrink-0' : 'danger-pill shrink-0'}>
                  {plan.is_active ? 'Активен' : 'Отключен'}
                </span>
              </div>

              <div className="mt-4">
                <p className="mt-2 text-sm muted">{plan.description || 'Описание тарифа пока не заполнено.'}</p>
              </div>

              <div className="mt-4 grid grid-cols-3 gap-2">
                <div className="panel-soft p-3">
                  <p className="text-xs muted">Цена</p>
                  <p className="mt-1 text-lg font-extrabold">{plan.price}₽</p>
                </div>
                <div className="panel-soft p-3">
                  <p className="text-xs muted">Период</p>
                  <p className="mt-1 text-lg font-extrabold">{plan.duration_days}д</p>
                </div>
                <div className="panel-soft p-3">
                  <p className="text-xs muted">Лимит</p>
                  <p className="mt-1 text-lg font-extrabold">{plan.device_limit}</p>
                </div>
              </div>

              <div className="mt-4 rounded-lg bg-white/5 p-3">
                <p className="text-xs uppercase tracking-[0.12em] muted">Состав</p>
                <ul className="mt-3 space-y-2">
                  {getFeatures(plan).length > 0 ? (
                    getFeatures(plan).map((feature: string, index: number) => (
                      <li key={index} className="flex items-start gap-2 text-sm text-slate-100">
                        <div className="mt-0.5 rounded-full bg-emerald-300/12 p-1 text-emerald-200">
                          <Check className="h-3.5 w-3.5" />
                        </div>
                        <span>{feature}</span>
                      </li>
                    ))
                  ) : (
                    <li className="text-sm muted">Список преимуществ для этого тарифа пока не задан.</li>
                  )}
                </ul>
              </div>

              <div className="mt-4 flex items-center justify-between gap-3 border-t border-white/5 pt-4 text-sm">
                <span className="muted">sort {plan.sort_order}</span>
                <span className="metric-pill">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  canonical
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
// END_BLOCK: Plans
