// FILE: frontend-admin/src/pages/Users.tsx
// VERSION: 1.0.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Admin page for user management (list, search, pagination, role/status display)
//   SCOPE: Paginated user list with search, role badges, active/blocked status
//   DEPENDS: M-010 (frontend-admin), M-006 (admin API)
//   LINKS: M-010
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   UsersPage - Main admin users page component
//   formatDate - Helper: format date to ru-RU locale string
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY

import { useMemo, useState } from 'react'
import { useQuery } from 'react-query'
import { Search, Shield, UserCheck, UserRound, UserX } from 'lucide-react'
import { adminApi } from '../lib/api'
import type { AdminUser, PaginatedResponse } from '../types'

// START_BLOCK: formatDate
// Formats ISO date string to ru-RU locale or returns 'Никогда'
// DEPENDS: none (pure function)
function formatDate(value?: string | null) {
  if (!value) return 'Никогда'
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
// END_BLOCK: formatDate

// START_BLOCK: Users
// Main admin users page: paginated user list with search and role/status display
// DEPENDS: M-010 (frontend-admin), M-006 (admin API via adminApi)
//   - adminApi.getUsers (paginated with search)
export default function Users() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery<{ data: PaginatedResponse<AdminUser> }>(['admin-users', page, search], () => adminApi.getUsers(page, search), {
    keepPreviousData: true,
  })

  const users = data?.data?.items || []
  const total = data?.data?.total || 0
  const pages = data?.data?.pages || 1

  const counters = useMemo(() => {
    return users.reduce(
      (acc: { active: number; admins: number; blocked: number }, user: AdminUser) => {
        if (user.is_active) acc.active += 1
        else acc.blocked += 1
        if (user.role === 'admin' || user.role === 'superadmin') acc.admins += 1
        return acc
      },
      { active: 0, admins: 0, blocked: 0 }
    )
  }, [users])

  return (
    <div className="page-shell">
      <div className="page-header">
        <div>
          <h1 className="page-title">Пользователи</h1>
          <p className="page-subtitle">Найдено {total} аккаунтов. Поиск работает по текущей серверной выборке.</p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="panel-soft grid grid-cols-3 gap-3 px-4 py-3 text-sm">
            <div>
              <p className="muted">Активные</p>
              <p className="mt-1 font-bold">{counters.active}</p>
            </div>
            <div>
              <p className="muted">Админы</p>
              <p className="mt-1 font-bold">{counters.admins}</p>
            </div>
            <div>
              <p className="muted">Блок</p>
              <p className="mt-1 font-bold">{counters.blocked}</p>
            </div>
          </div>

          <div className="relative w-full sm:w-80">
            <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              className="input pl-12"
              placeholder="Поиск по email или имени"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(1)
              }}
            />
          </div>
        </div>
      </div>

      <div className="panel overflow-hidden">
        {isLoading ? (
          <div className="empty-state m-6">
            <UserRound className="h-10 w-10 text-cyan-200" />
            <div>
              <p className="text-lg font-semibold">Загружаем список пользователей</p>
              <p className="mt-1 text-sm muted">Тянем страницу и статус аккаунтов из admin API.</p>
            </div>
          </div>
        ) : users.length === 0 ? (
          <div className="empty-state m-6">
            <Search className="h-10 w-10 text-cyan-200" />
            <div>
              <p className="text-lg font-semibold">Ничего не найдено</p>
              <p className="mt-1 text-sm muted">Измени поисковый запрос или сбрось фильтр.</p>
            </div>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Профиль</th>
                    <th>Email</th>
                    <th>Роль</th>
                    <th>Статус</th>
                    <th>Последний вход</th>
                    <th>Создан</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user: AdminUser) => (
                    <tr key={user.id}>
                      <td>
                        <div className="flex items-center gap-3">
                          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/10 font-bold text-cyan-100">
                            {user.display_name?.[0] || user.email?.[0] || '?'}
                          </div>
                          <div>
                            <p className="font-semibold">{user.display_name || 'Без имени'}</p>
                            <p className="text-xs muted">
                              {user.telegram_username ? `@${user.telegram_username}` : `ID #${user.id}`}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td>{user.email || '-'}</td>
                      <td>
                        <span
                          className={
                            user.role === 'superadmin'
                              ? 'danger-pill'
                              : user.role === 'admin'
                                ? 'metric-pill'
                                : 'inline-flex items-center rounded-full bg-white/5 px-3 py-1 text-xs font-semibold text-slate-300'
                          }
                        >
                          {user.role === 'superadmin' && <Shield className="h-3.5 w-3.5" />}
                          {user.role}
                        </span>
                      </td>
                      <td>
                        <span className={user.is_active ? 'metric-pill' : 'danger-pill'}>
                          {user.is_active ? <UserCheck className="h-3.5 w-3.5" /> : <UserX className="h-3.5 w-3.5" />}
                          {user.is_active ? 'Активен' : 'Заблокирован'}
                        </span>
                      </td>
                      <td className="muted">{formatDate(user.last_login_at)}</td>
                      <td className="muted">{formatDate(user.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {pages > 1 ? (
              <div className="flex flex-col items-center justify-between gap-3 border-t border-white/5 px-5 py-4 sm:flex-row">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="btn-secondary disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Назад
                </button>
                <p className="text-sm muted">
                  Страница {page} из {pages}
                </p>
                <button
                  onClick={() => setPage((p) => Math.min(pages, p + 1))}
                  disabled={page === pages}
                  className="btn-secondary disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Вперёд
                </button>
              </div>
            ) : null}
          </>
        )}
      </div>
    </div>
  )
}
// END_BLOCK: Users
