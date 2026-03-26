import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import { Ban, RotateCw, Search, ShieldAlert, ShieldCheck, Trash2 } from 'lucide-react'
import { adminApi } from '../lib/api'

function formatDate(value?: string | null) {
  if (!value) return 'Нет данных'
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function Devices() {
  const [search, setSearch] = useState('')
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery(['admin-devices', search], () => adminApi.getDevices(search))

  const mutateAndRefresh = (message: string) => ({
    onSuccess: () => {
      void queryClient.invalidateQueries('admin-devices')
      setFeedback({ tone: 'success', text: message })
    },
    onError: (error: any) => {
      setFeedback({
        tone: 'error',
        text: error?.response?.data?.detail || 'Операция не выполнена',
      })
    },
  })

  const blockMutation = useMutation((id: number) => adminApi.blockDevice(id), mutateAndRefresh('Устройство заблокировано'))
  const unblockMutation = useMutation((id: number) => adminApi.unblockDevice(id), mutateAndRefresh('Блокировка снята'))
  const rotateMutation = useMutation((id: number) => adminApi.rotateDevice(id), mutateAndRefresh('Конфиг перевыпущен'))
  const revokeMutation = useMutation((id: number) => adminApi.revokeDevice(id), mutateAndRefresh('Устройство отозвано'))

  const items = data?.data?.items || []

  const counters = useMemo(() => {
    return items.reduce(
      (acc: { active: number; blocked: number; suspicious: number }, item: any) => {
        if (item.status === 'blocked') acc.blocked += 1
        if (item.status === 'active') acc.active += 1
        if ((item.recent_event_types || []).some((event: string) => event.includes('suspicious') || event.includes('concurrent'))) {
          acc.suspicious += 1
        }
        return acc
      },
      { active: 0, blocked: 0, suspicious: 0 }
    )
  }, [items])

  return (
    <div className="page-shell">
      <div className="page-header">
        <div>
          <h1 className="page-title">Устройства</h1>
          <p className="page-subtitle">Device-bound peer inventory, свежие сигналы anti-sharing и быстрые санкции на уровне одного устройства.</p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="panel-soft grid grid-cols-3 gap-3 px-4 py-3 text-sm">
            <div>
              <p className="muted">Активные</p>
              <p className="mt-1 font-bold">{counters.active}</p>
            </div>
            <div>
              <p className="muted">Блок</p>
              <p className="mt-1 font-bold">{counters.blocked}</p>
            </div>
            <div>
              <p className="muted">Сигналы</p>
              <p className="mt-1 font-bold">{counters.suspicious}</p>
            </div>
          </div>

          <div className="relative w-full sm:w-80">
            <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              className="input pl-12"
              placeholder="Поиск по email, имени, платформе"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
        </div>
      </div>

      {feedback ? (
        <div className={feedback.tone === 'success' ? 'panel-soft mb-4 px-4 py-3 text-sm text-emerald-100' : 'panel-soft mb-4 px-4 py-3 text-sm text-amber-100'}>
          {feedback.text}
        </div>
      ) : null}

      <div className="panel overflow-hidden">
        {isLoading ? (
          <div className="empty-state m-6">
            <ShieldAlert className="h-10 w-10 text-cyan-200" />
            <div>
              <p className="text-lg font-semibold">Загружаем устройство и сигналы</p>
              <p className="mt-1 text-sm muted">Тянем device registry и свежие security events из admin API.</p>
            </div>
          </div>
        ) : items.length === 0 ? (
          <div className="empty-state m-6">
            <Search className="h-10 w-10 text-cyan-200" />
            <div>
              <p className="text-lg font-semibold">Устройства не найдены</p>
              <p className="mt-1 text-sm muted">Измени запрос или дождись первой device-bound выдачи.</p>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Пользователь</th>
                  <th>Устройство</th>
                  <th>Статус</th>
                  <th>Endpoint / Handshake</th>
                  <th>Сигналы</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item: any) => (
                  <tr key={item.id}>
                    <td>
                      <div>
                        <p className="font-semibold">{item.user_display_name || item.user_email || `User #${item.user_id}`}</p>
                        <p className="text-xs muted">{item.user_email || `ID #${item.user_id}`}</p>
                      </div>
                    </td>
                    <td>
                      <div>
                        <p className="font-semibold">{item.name}</p>
                        <p className="text-xs muted">{item.platform || 'platform not set'} · v{item.config_version}</p>
                      </div>
                    </td>
                    <td>
                      <span className={item.status === 'blocked' ? 'danger-pill' : 'metric-pill'}>
                        {item.status === 'blocked' ? <Ban className="h-3.5 w-3.5" /> : <ShieldCheck className="h-3.5 w-3.5" />}
                        {item.status}
                      </span>
                      {item.block_reason ? (
                        <p className="mt-2 text-xs muted">reason: {item.block_reason}</p>
                      ) : null}
                    </td>
                    <td>
                      <p className="text-sm">{item.last_endpoint || 'Нет endpoint'}</p>
                      <p className="mt-1 text-xs muted">{formatDate(item.last_handshake_at)}</p>
                    </td>
                    <td>
                      <div className="flex flex-wrap gap-2">
                        {(item.recent_event_types || []).length ? (
                          item.recent_event_types.map((event: string) => (
                            <span key={`${item.id}-${event}`} className="inline-flex rounded-full bg-white/5 px-3 py-1 text-xs font-semibold text-slate-300">
                              {event}
                            </span>
                          ))
                        ) : (
                          <span className="text-xs muted">Нет сигналов</span>
                        )}
                      </div>
                    </td>
                    <td>
                      <div className="flex flex-wrap gap-2">
                        {item.status === 'blocked' ? (
                          <button onClick={() => unblockMutation.mutate(item.id)} className="btn-secondary">
                            <ShieldCheck className="h-4 w-4" />
                            Unblock
                          </button>
                        ) : (
                          <button onClick={() => blockMutation.mutate(item.id)} className="btn-secondary">
                            <Ban className="h-4 w-4" />
                            Block
                          </button>
                        )}
                        <button onClick={() => rotateMutation.mutate(item.id)} className="btn-secondary">
                          <RotateCw className="h-4 w-4" />
                          Rotate
                        </button>
                        <button onClick={() => revokeMutation.mutate(item.id)} className="btn-secondary">
                          <Trash2 className="h-4 w-4" />
                          Revoke
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
