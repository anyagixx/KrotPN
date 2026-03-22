import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import { Plus, Server, MapPin, Users, Edit, Trash2 } from 'lucide-react'
import { adminApi } from '../lib/api'

export default function Servers() {
  const [showModal, setShowModal] = useState(false)
  const [editingServer, setEditingServer] = useState<any>(null)
  const queryClient = useQueryClient()
  
  const { data: servers, isLoading } = useQuery('admin-servers', () => adminApi.getServers())
  
  const deleteMutation = useMutation(
    (id: number) => adminApi.deleteServer(id),
    { onSuccess: () => queryClient.invalidateQueries('admin-servers') }
  )
  const serverItems = servers?.data?.servers || []
  
  const handleDelete = async (id: number) => {
    if (confirm('Удалить сервер?')) {
      await deleteMutation.mutateAsync(id)
    }
  }
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">VPN Серверы</h1>
          <p className="text-gray-400 mt-1">Управление серверами AmneziaWG</p>
        </div>
        <button 
          onClick={() => { setEditingServer(null); setShowModal(true) }}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-5 h-5" />
          Добавить сервер
        </button>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {serverItems.map((server: any) => (
          <div key={server.id} className="stat-card">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className={`p-3 rounded-xl ${server.is_online ? 'bg-green-500/20' : 'bg-red-500/20'}`}>
                  <Server className={`w-6 h-6 ${server.is_online ? 'text-green-400' : 'text-red-400'}`} />
                </div>
                <div>
                  <h3 className="font-semibold">{server.name}</h3>
                  <p className="text-sm text-gray-400 flex items-center gap-1">
                    <MapPin className="w-4 h-4" />
                    {server.location}
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <button 
                  onClick={() => { setEditingServer(server); setShowModal(true) }}
                  className="p-2 hover:bg-dark-700 rounded-lg"
                >
                  <Edit className="w-4 h-4 text-gray-400" />
                </button>
                <button 
                  onClick={() => handleDelete(server.id)}
                  className="p-2 hover:bg-red-500/10 rounded-lg"
                >
                  <Trash2 className="w-4 h-4 text-red-400" />
                </button>
              </div>
            </div>
            
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-400">Клиентов</span>
                <span className="flex items-center gap-1">
                  <Users className="w-4 h-4" />
                  {server.current_clients} / {server.max_clients}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Нагрузка</span>
                <span>{server.load_percent?.toFixed(1)}%</span>
              </div>
            </div>
            
            <div className="mt-4 pt-4 border-t border-dark-700">
              <div className="h-2 bg-dark-700 rounded-full overflow-hidden">
                <div 
                  className={`h-full rounded-full ${
                    server.load_percent > 80 ? 'bg-red-500' :
                    server.load_percent > 50 ? 'bg-yellow-500' : 'bg-green-500'
                  }`}
                  style={{ width: `${Math.min(100, server.load_percent)}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
      
      {/* Modal placeholder */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="glass p-6 w-full max-w-md">
            <h2 className="text-xl font-bold mb-4">
              {editingServer ? 'Редактировать сервер' : 'Новый сервер'}
            </h2>
            <p className="text-gray-400">Форма редактирования...</p>
            <div className="flex gap-3 mt-6">
              <button onClick={() => setShowModal(false)} className="btn-secondary flex-1">
                Отмена
              </button>
              <button onClick={() => setShowModal(false)} className="btn-primary flex-1">
                Сохранить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
