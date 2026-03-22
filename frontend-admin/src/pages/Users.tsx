import { useState } from 'react'
import { useQuery } from 'react-query'
import { Search, MoreVertical, UserCheck, UserX } from 'lucide-react'
import { adminApi } from '../lib/api'

export default function Users() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  
  const { data, isLoading } = useQuery(
    ['admin-users', page, search],
    () => adminApi.getUsers(page, search),
    { keepPreviousData: true }
  )
  
  const users = data?.data?.items || []
  const total = data?.data?.total || 0
  const pages = data?.data?.pages || 1
  
  const formatDate = (date: string) => new Date(date).toLocaleDateString('ru-RU')
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Пользователи</h1>
          <p className="text-gray-400 mt-1">Всего: {total}</p>
        </div>
        
        <div className="relative w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            className="input pl-10"
            placeholder="Поиск..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1) }}
          />
        </div>
      </div>
      
      <div className="glass overflow-hidden">
        <table className="w-full">
          <thead className="bg-dark-800">
            <tr>
              <th className="text-left p-4 text-gray-400 font-medium">Пользователь</th>
              <th className="text-left p-4 text-gray-400 font-medium">Email</th>
              <th className="text-left p-4 text-gray-400 font-medium">Роль</th>
              <th className="text-left p-4 text-gray-400 font-medium">Статус</th>
              <th className="text-left p-4 text-gray-400 font-medium">Последний вход</th>
              <th className="text-left p-4 text-gray-400 font-medium">Создан</th>
              <th className="p-4"></th>
            </tr>
          </thead>
          <tbody>
            {users.map((user: any) => (
              <tr key={user.id} className="border-t border-dark-700 hover:bg-dark-800/50">
                <td className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-primary-500/20 flex items-center justify-center">
                      {user.display_name?.[0] || user.email?.[0] || '?'}
                    </div>
                    <div>
                      <p className="font-medium">{user.display_name || 'Без имени'}</p>
                      {user.telegram_username && (
                        <p className="text-sm text-gray-400">@{user.telegram_username}</p>
                      )}
                    </div>
                  </div>
                </td>
                <td className="p-4">{user.email || '-'}</td>
                <td className="p-4">
                  <span className={`px-2 py-1 rounded text-xs ${
                    user.role === 'superadmin' ? 'bg-red-500/20 text-red-400' :
                    user.role === 'admin' ? 'bg-yellow-500/20 text-yellow-400' :
                    'bg-gray-500/20 text-gray-400'
                  }`}>
                    {user.role}
                  </span>
                </td>
                <td className="p-4">
                  <span className={`flex items-center gap-2 ${
                    user.is_active ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {user.is_active ? <UserCheck className="w-4 h-4" /> : <UserX className="w-4 h-4" />}
                    {user.is_active ? 'Активен' : 'Заблокирован'}
                  </span>
                </td>
                <td className="p-4 text-gray-400">
                  {user.last_login_at ? formatDate(user.last_login_at) : 'Никогда'}
                </td>
                <td className="p-4 text-gray-400">{formatDate(user.created_at)}</td>
                <td className="p-4">
                  <button className="p-2 hover:bg-dark-700 rounded-lg">
                    <MoreVertical className="w-5 h-5 text-gray-400" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        
        {pages > 1 && (
          <div className="flex items-center justify-between p-4 border-t border-dark-700">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="btn-secondary disabled:opacity-50"
            >
              Назад
            </button>
            <span className="text-gray-400">
              Страница {page} из {pages}
            </span>
            <button
              onClick={() => setPage(p => Math.min(pages, p + 1))}
              disabled={page === pages}
              className="btn-secondary disabled:opacity-50"
            >
              Вперёд
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
