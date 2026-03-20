import { useState } from 'react'
import { Save, RefreshCw } from 'lucide-react'

export default function Settings() {
  const [saved, setSaved] = useState(false)
  
  const handleSave = () => {
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }
  
  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-3xl font-bold">Настройки</h1>
        <p className="text-gray-400 mt-1">Конфигурация системы</p>
      </div>
      
      <div className="stat-card">
        <h3 className="font-semibold mb-4">Общие настройки</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Название сервиса</label>
            <input type="text" className="input" defaultValue="KrotVPN" />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-2">Email поддержки</label>
            <input type="email" className="input" defaultValue="support@krotvpn.com" />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-2">Пробный период (дней)</label>
            <input type="number" className="input" defaultValue="3" />
          </div>
        </div>
      </div>
      
      <div className="stat-card">
        <h3 className="font-semibold mb-4">Реферальная программа</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Бонус за реферала (дней)</label>
            <input type="number" className="input" defaultValue="7" />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-2">Минимальный платёж для бонуса (₽)</label>
            <input type="number" className="input" defaultValue="100" />
          </div>
        </div>
      </div>
      
      <div className="stat-card">
        <h3 className="font-semibold mb-4">AmneziaWG параметры</h3>
        <p className="text-sm text-yellow-400 mb-4">
          ⚠️ Изменение этих параметров потребует обновления конфигов у всех клиентов!
        </p>
        <div className="grid grid-cols-3 gap-4">
          {['Jc', 'Jmin', 'Jmax', 'S1', 'S2', 'H1', 'H2', 'H3', 'H4'].map((param) => (
            <div key={param}>
              <label className="block text-sm text-gray-400 mb-2">{param}</label>
              <input 
                type="number" 
                className="input" 
                defaultValue={param === 'Jc' ? 120 : param === 'Jmin' ? 50 : param === 'Jmax' ? 1000 : 0}
              />
            </div>
          ))}
        </div>
      </div>
      
      <div className="flex gap-3">
        <button onClick={handleSave} className="btn-primary flex items-center gap-2">
          <Save className="w-5 h-5" />
          {saved ? 'Сохранено!' : 'Сохранить'}
        </button>
        <button className="btn-secondary flex items-center gap-2">
          <RefreshCw className="w-5 h-5" />
          Сбросить
        </button>
      </div>
    </div>
  )
}
