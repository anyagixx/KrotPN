import { RefreshCw, Save, ShieldAlert } from 'lucide-react'

function field(label: string, value: string | number, type: string = 'text') {
  return (
    <label className="block">
      <span className="mb-2 block text-sm muted">{label}</span>
      <input type={type} className="input" defaultValue={value} />
    </label>
  )
}

export default function Settings() {
  return (
    <div className="page-shell">
      <div className="page-header">
        <div>
          <h1 className="page-title">Настройки</h1>
          <p className="page-subtitle">
            Это обзор конфигурации. Полное сохранение параметров ещё не заведено на backend отдельным endpoint.
          </p>
        </div>
      </div>

      <div className="glass p-6">
        <div className="flex items-start gap-4">
          <div className="rounded-2xl bg-yellow-300/12 p-3 text-yellow-100">
            <ShieldAlert className="h-6 w-6" />
          </div>
          <div>
            <h3 className="text-lg font-semibold">Честный статус раздела</h3>
            <p className="mt-2 text-sm muted">
              Раньше этот экран выглядел как рабочая форма, хотя сохранение никуда не уходило. Теперь он прямо показывает,
              что это пока конфигурационный обзор перед полноценным CRUD.
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <section className="panel p-6">
          <h3 className="text-lg font-semibold">Общие параметры</h3>
          <div className="mt-5 space-y-4">
            {field('Название сервиса', 'KrotVPN')}
            {field('Email поддержки', 'support@krotvpn.com', 'email')}
            {field('Пробный период, дней', 3, 'number')}
          </div>
        </section>

        <section className="panel p-6">
          <h3 className="text-lg font-semibold">Реферальная программа</h3>
          <div className="mt-5 space-y-4">
            {field('Бонус за реферала, дней', 7, 'number')}
            {field('Минимальный платёж для бонуса, ₽', 100, 'number')}
          </div>
        </section>
      </div>

      <section className="panel p-6">
        <h3 className="text-lg font-semibold">AmneziaWG параметры</h3>
        <p className="mt-2 text-sm muted">
          Изменение этих параметров потребует регенерации конфигов. Оставил их в виде обзорной сетки, пока backend не
          примет запись.
        </p>

        <div className="mt-5 grid gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {[
            ['Jc', 120],
            ['Jmin', 50],
            ['Jmax', 1000],
            ['S1', 111],
            ['S2', 222],
            ['H1', 1],
            ['H2', 2],
            ['H3', 3],
            ['H4', 4],
          ].map(([label, value]) => (
            <div key={label} className="panel-soft p-4">
              <p className="text-xs uppercase tracking-[0.18em] muted">{label}</p>
              <p className="mt-3 text-2xl font-bold">{value}</p>
            </div>
          ))}
        </div>
      </section>

      <div className="flex flex-col gap-3 sm:flex-row">
        <button className="btn-primary">
          <Save className="h-5 w-5" />
          Сохранение появится с backend API
        </button>
        <button className="btn-secondary">
          <RefreshCw className="h-5 w-5" />
          Обновить экран
        </button>
      </div>
    </div>
  )
}
