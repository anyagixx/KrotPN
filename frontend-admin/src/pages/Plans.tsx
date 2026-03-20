import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import { Plus, Edit, Trash2, Check, Star } from 'lucide-react'
import { adminApi } from '../lib/api'

export default function Plans() {
  const [showModal, setShowModal] = useState(false)
  const queryClient = useQueryClient()
  
  const { data: plans, isLoading } = useQuery('admin-plans', () => adminApi.getPlans())
  
  const deleteMutation = useMutation(
    (id: number) => adminApi.deletePlan(id),
    { onSuccess: () => queryClient.invalidateQueries('admin-plans') }
  )
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Тарифные планы</h1>
          <p className="text-gray-400 mt-1">Управление подписками</p>
        </div>
        <button 
          onClick={() => setShowModal(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-5 h-5" />
          Создать план
        </button>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {plans?.data?.map((plan: any) => (
          <div 
            key={plan.id} 
            className={`stat-card relative ${!plan.is_active ? 'opacity-50' : ''}`}
          >
            {plan.is_popular && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-yellow-500 text-black text-xs font-bold rounded-full">
                Популярный
              </div>
            )}
            
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-bold">{plan.name}</h3>
              <div className="flex gap-2">
                <button className="p-2 hover:bg-dark-700 rounded-lg">
                  <Edit className="w-4 h-4 text-gray-400" />
                </button>
                <button 
                  onClick={() => deleteMutation.mutate(plan.id)}
                  className="p-2 hover:bg-red-500/10 rounded-lg"
                >
                  <Trash2 className="w-4 h-4 text-red-400" />
                </button>
              </div>
            </div>
            
            <div className="mb-4">
              <span className="text-3xl font-bold">{plan.price}</span>
              <span className="text-gray-400 ml-1">₽</span>
              <span className="text-gray-400 ml-2">/ {plan.duration_days} дней</span>
            </div>
            
            {plan.features && (
              <ul className="space-y-2 mb-4">
                {JSON.parse(plan.features || '[]').map((feature: string, i: number) => (
                  <li key={i} className="flex items-center gap-2 text-sm text-gray-300">
                    <Check className="w-4 h-4 text-green-400" />
                    {feature}
                  </li>
                ))}
              </ul>
            )}
            
            <div className="flex items-center justify-between pt-4 border-t border-dark-700">
              <span className={`text-sm ${plan.is_active ? 'text-green-400' : 'text-red-400'}`}>
                {plan.is_active ? 'Активен' : 'Неактивен'}
              </span>
              <span className="text-sm text-gray-400">
                {plan.currency}
              </span>
            </div>
          </div>
        ))}
      </div>
      
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="glass p-6 w-full max-w-md">
            <h2 className="text-xl font-bold mb-4">Новый тарифный план</h2>
            <p className="text-gray-400">Форма создания...</p>
            <div className="flex gap-3 mt-6">
              <button onClick={() => setShowModal(false)} className="btn-secondary flex-1">
                Отмена
              </button>
              <button onClick={() => setShowModal(false)} className="btn-primary flex-1">
                Создать
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
