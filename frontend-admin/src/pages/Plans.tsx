// FILE: frontend-admin/src/pages/Plans.tsx
// VERSION: 1.0.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Admin page for billing plan management (list, display features, delete)
//   SCOPE: Display tariff plans grid with features, active status, delete; modal placeholder for create
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
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import { Check, CreditCard, Edit, Plus, Star, Trash2 } from 'lucide-react'
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
// Admin plans page: tariff plan grid with features, status, delete; create modal placeholder
// DEPENDS: M-010 (frontend-admin), M-006 (admin API via adminApi)
//   - adminApi.getPlans, adminApi.deletePlan
export default function Plans() {
  const [showModal, setShowModal] = useState(false)
  const queryClient = useQueryClient()

  const { data: plans, isLoading } = useQuery('admin-plans', () => adminApi.getPlans())

  const deleteMutation = useMutation((id: number) => adminApi.deletePlan(id), {
    onSuccess: () => queryClient.invalidateQueries('admin-plans'),
  })

  const items = plans?.data || []

  return (
    <div className="page-shell">
      <div className="page-header">
        <div>
          <h1 className="page-title">Тарифные планы</h1>
          <p className="page-subtitle">Текущая продуктовая матрица и статус публикации тарифов.</p>
        </div>

        <div className="flex items-center gap-3">
          <div className="panel-soft px-4 py-3 text-sm">
            <p className="muted">Активных планов</p>
            <p className="mt-1 font-bold">{items.filter((plan: AdminPlan) => plan.is_active).length}</p>
          </div>
          <button onClick={() => setShowModal(true)} className="btn-primary">
            <Plus className="h-5 w-5" />
            Создать план
          </button>
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
            <p className="text-lg font-semibold">Планы не найдены</p>
            <p className="mt-1 text-sm muted">После создания тарифов они появятся в этой сетке.</p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          {items.map((plan: AdminPlan) => (
            <div key={plan.id} className={`panel relative p-6 ${!plan.is_active ? 'opacity-65' : ''}`}>
              {plan.is_popular ? (
                <div className="absolute right-5 top-5 metric-pill">
                  <Star className="h-3.5 w-3.5" />
                  Популярный
                </div>
              ) : null}

              <div className="pr-24">
                <p className="text-xs uppercase tracking-[0.2em] muted">{plan.currency}</p>
                <h3 className="mt-3 text-2xl font-extrabold">{plan.name}</h3>
                <p className="mt-2 text-sm muted">{plan.description || 'Описание тарифа пока не заполнено.'}</p>
              </div>

              <div className="mt-6 flex items-end gap-2">
                <span className="text-4xl font-extrabold">{plan.price}</span>
                <span className="pb-1 text-sm muted">₽ / {plan.duration_days} дней</span>
              </div>

              <div className="mt-6 rounded-2xl bg-white/5 p-4">
                <p className="text-xs uppercase tracking-[0.18em] muted">Что входит</p>
                <ul className="mt-4 space-y-3">
                  {getFeatures(plan).length > 0 ? (
                    getFeatures(plan).map((feature: string, index: number) => (
                      <li key={index} className="flex items-start gap-3 text-sm text-slate-100">
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

              <div className="mt-6 flex items-center justify-between border-t border-white/5 pt-5">
                <span className={plan.is_active ? 'metric-pill' : 'danger-pill'}>
                  {plan.is_active ? 'Активен' : 'Неактивен'}
                </span>
                <div className="flex gap-2">
                  <button className="btn-secondary px-3 py-2">
                    <Edit className="h-4 w-4" />
                  </button>
                  <button onClick={() => deleteMutation.mutate(plan.id)} className="btn-danger px-3 py-2">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm">
          <div className="glass w-full max-w-lg p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-2xl font-bold">Создание тарифа</h2>
                <p className="mt-2 text-sm muted">
                  CRUD-форма backend поддерживает, но UI-редактор ещё не реализован. Сейчас экран честно показывает это.
                </p>
              </div>
              <button onClick={() => setShowModal(false)} className="btn-secondary px-3 py-2">
                Закрыть
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
// END_BLOCK: Plans
