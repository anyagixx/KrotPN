// FILE: frontend-admin/src/pages/Users.tsx
// VERSION: 1.3.0
// ROLE: UI_COMPONENT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Compact Matrix admin page for user management, search, pagination, role/status display, mobile account summary, and Phase-58 bounded inventory proof
//   SCOPE: Paginated user list with search, compact rows, role badges, active/blocked status, bounded scrolling, phone-safe metadata, and dense operator filters
//   DEPENDS: M-010 (frontend-admin), M-006 (admin API), M-037 (mobile-admin-console), M-038 (compact-ui-system), M-071 (matrix-style-system), M-076 (premium-admin-cockpit)
//   LINKS: M-010, M-037, M-038, M-071, M-076, Phase-54, Phase-58
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   UsersPage - Main compact admin users page component
//   formatDate - Helper: format date to ru-RU locale string
//   roleClass - Helper: choose role badge class
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v3.1.0 - Phase-58 added premium bounded inventory markers and denser user search frame.
//   LAST_CHANGE: v3.0.0 - Phase-54 added Matrix route markers and bounded compact inventory behavior for large user sets.
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
//   LAST_CHANGE: v2.9.0 - Phase-24 compact mobile user search rows without table-only dependency
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

// START_BLOCK: roleClass
// Returns compact badge class for admin role visibility
// DEPENDS: none (pure function)
function roleClass(role: string) {
  if (role === 'superadmin') return 'danger-pill'
  if (role === 'admin') return 'metric-pill'
  return 'neutral-pill'
}
// END_BLOCK: roleClass

// START_BLOCK: Users
// Main compact admin users page: paginated user list with search and role/status display
// DEPENDS: M-010 (frontend-admin), M-006 (admin API via adminApi)
//   - adminApi.getUsers (paginated with search)
export default function Users() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery<{ data: PaginatedResponse<AdminUser> }>(
    ['admin-users', page, search],
    () => adminApi.getUsers(page, search),
    { keepPreviousData: true }
  )

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
    <div
      className="page-shell"
      data-phase54-admin-route="users"
      data-phase58-route="users"
      data-log-marker="[MobileAdminConsole][Phase54][PRIMARY_ACTIONS_REACHABLE]"
    >
      <div className="page-header">
        <div>
          <h1 className="page-title">Пользователи</h1>
          <p className="page-subtitle">Найдено {total} аккаунтов. Поиск и статусы остаются читаемыми на телефоне.</p>
        </div>

        <div className="grid gap-2 sm:min-w-[420px]" data-log-marker="[MobileAdminConsole][Phase54][ROUTE_VIEWPORT_SAFE]">
          <div className="metric-strip phase58-signal-strip">
            <div className="metric-strip-item">
              <span className="metric-label">Активные</span>
              <span className="block text-base font-bold">{counters.active}</span>
            </div>
            <div className="metric-strip-item">
              <span className="metric-label">Админы</span>
              <span className="block text-base font-bold">{counters.admins}</span>
            </div>
            <div className="metric-strip-item">
              <span className="metric-label">Блок</span>
              <span className="block text-base font-bold">{counters.blocked}</span>
            </div>
          </div>

          <div className="relative">
            <Search className="input-icon-left" />
            <input
              type="text"
              className="input input-with-icon-left"
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

      {isLoading ? (
        <div className="empty-state">
          <UserRound className="h-9 w-9 text-cyan-200" />
          <div>
            <p className="text-base font-semibold">Загружаем список пользователей</p>
            <p className="mt-1 text-sm muted">Тянем страницу и статус аккаунтов из admin API.</p>
          </div>
        </div>
      ) : users.length === 0 ? (
        <div className="empty-state">
          <Search className="h-9 w-9 text-cyan-200" />
          <div>
            <p className="text-base font-semibold">Ничего не найдено</p>
            <p className="mt-1 text-sm muted">Измени поисковый запрос или сбрось фильтр.</p>
          </div>
        </div>
      ) : (
        <div
          className="compact-list bounded-scroll phase58-inventory-list phase58-scroll-rail"
          data-phase58-inventory="[PremiumAdminCockpit][phase58][INVENTORIES_BOUNDED]"
        >
          {users.map((user: AdminUser) => (
            <article key={user.id} className="list-row">
              <div className="row-main">
                <div className="flex min-w-0 items-start gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white/10 font-bold text-cyan-100">
                    {user.display_name?.[0] || user.email?.[0] || '?'}
                  </div>
                  <div className="min-w-0">
                    <h2 className="row-title">{user.display_name || 'Без имени'}</h2>
                    <p className="row-subtitle">{user.telegram_username ? `@${user.telegram_username}` : `ID #${user.id}`}</p>
                  </div>
                </div>

                <span className={user.is_active ? 'metric-pill shrink-0' : 'danger-pill shrink-0'}>
                  {user.is_active ? <UserCheck className="h-3.5 w-3.5" /> : <UserX className="h-3.5 w-3.5" />}
                  {user.is_active ? 'Активен' : 'Блок'}
                </span>
              </div>

              <div className="row-meta">
                <div className="meta-cell">
                  <span className="meta-label">Email</span>
                  <span className="meta-value">{user.email || '-'}</span>
                </div>
                <div className="meta-cell">
                  <span className="meta-label">Роль</span>
                  <span className={roleClass(user.role)}>
                    {user.role === 'superadmin' ? <Shield className="h-3.5 w-3.5" /> : null}
                    {user.role}
                  </span>
                </div>
                <div className="meta-cell">
                  <span className="meta-label">Последний вход</span>
                  <span className="meta-value">{formatDate(user.last_login_at)}</span>
                </div>
                <div className="meta-cell">
                  <span className="meta-label">Создан</span>
                  <span className="meta-value">{formatDate(user.created_at)}</span>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      {pages > 1 ? (
        <div className="flex items-center justify-between gap-3">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="btn-secondary"
          >
            Назад
          </button>
          <p className="text-sm muted">
            {page} / {pages}
          </p>
          <button
            onClick={() => setPage((p) => Math.min(pages, p + 1))}
            disabled={page === pages}
            className="btn-secondary"
          >
            Вперёд
          </button>
        </div>
      ) : null}
    </div>
  )
}
// END_BLOCK: Users
