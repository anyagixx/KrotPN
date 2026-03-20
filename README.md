# 🛡️ KrotVPN - Commercial VPN Service

**KrotVPN** — коммерческий VPN-сервис на базе протокола AmneziaWG для обхода блокировок Роскомнадзора.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![License](https://img.shields.io/badge/license-MIT-blue)

## 🚀 Возможности

- **AmneziaWG протокол** — обфусцированный WireGuard, не детектируемый DPI
- **Split-tunneling** — российский трафик идет напрямую
- **Web-панель** — удобное управление подписками
- **Telegram бот** — уведомления и авторизация
- **Реферальная система** — бонусы за приглашения
- **Мультиязычность** — русский и английский интерфейс
- **PWA** — установка как приложение на мобильные

## 📋 Архитектура

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Клиент    │────▶│  RU-сервер  │────▶│  DE-сервер  │────▶  Интернет
│  (AmneziaWG)│     │ (Entry Node)│     │ (Exit Node) │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │   Web UI    │
                    │  (FastAPI)  │
                    └─────────────┘
```

## 🛠 Технологии

### Backend
- **Python 3.11+** — основной язык
- **FastAPI** — REST API фреймворк
- **SQLModel** — ORM с Pydantic
- **PostgreSQL** — основная БД
- **Redis** — кэширование и сессии

### Frontend
- **React 18** — UI фреймворк
- **Vite** — сборщик
- **TailwindCSS** — стили
- **Zustand** — state management
- **PWA** — оффлайн поддержка

### Infrastructure
- **Docker** — контейнеризация
- **Nginx** — reverse proxy
- **AmneziaWG** — VPN протокол

## 📁 Структура проекта

```
krotvpn/
├── docs/                    # GRACE документация
│   ├── requirements.xml     # Требования
│   ├── technology.xml       # Технологии
│   ├── development-plan.xml # План разработки
│   ├── verification-plan.xml# План тестирования
│   └── knowledge-graph.xml  # Граф зависимостей
├── backend/
│   ├── app/
│   │   ├── core/           # Ядро (config, security, db)
│   │   ├── users/          # Пользователи и авторизация
│   │   ├── vpn/            # VPN управление (AmneziaWG)
│   │   ├── billing/        # Подписки и платежи
│   │   ├── referrals/      # Реферальная программа
│   │   ├── routing/        # Split-tunneling
│   │   └── main.py         # Точка входа
│   ├── tests/
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/     # React компоненты
│   │   ├── pages/          # Страницы
│   │   ├── stores/         # Zustand stores
│   │   ├── lib/            # API клиент
│   │   └── i18n/           # Переводы
│   └── Dockerfile
├── telegram-bot/           # Telegram бот
├── scripts/                # Скрипты установки
└── docker-compose.yml
```

## 🚀 Быстрый старт

### Разработка

```bash
# Клонировать репозиторий
git clone https://github.com/your-repo/krotvpn.git
cd krotvpn

# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Отредактировать .env
uvicorn app.main:app --reload

# Frontend
cd ../frontend
npm install
npm run dev
```

### Docker

```bash
# Создать .env файл
cp .env.example .env
# Отредактировать .env

# Запустить
docker-compose up -d

# Проверить
curl http://localhost:8000/health
```

## ⚙️ Конфигурация

### Обязательные переменные

```env
SECRET_KEY=your-secret-key-at-least-32-characters
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/krotvpn
```

### Платежные системы

```env
YOOKASSA_SHOP_ID=your-shop-id
YOOKASSA_SECRET_KEY=your-secret-key
```

### Telegram

```env
TELEGRAM_BOT_TOKEN=your-bot-token
```

## 📱 Клиенты

- **Android**: [AmneziaWG](https://play.google.com/store/apps/details?id=org.amnezia.awg)
- **iOS**: [AmneziaWG](https://apps.apple.com/app/amneziawg/id6448364661)
- **Desktop**: [AmneziaVPN](https://amnezia.org/)

## 🔐 Безопасность

- JWT токены с refresh
- bcrypt хэширование паролей
- Fernet шифрование приватных ключей
- Rate limiting API
- CORS защита

## 📊 API Endpoints

### Auth
- `POST /api/auth/register` — регистрация
- `POST /api/auth/login` — вход
- `POST /api/auth/refresh` — обновление токена
- `POST /api/auth/telegram` — Telegram авторизация

### VPN
- `GET /api/vpn/config` — получить конфиг
- `GET /api/vpn/config/download` — скачать .conf
- `GET /api/vpn/config/qr` — QR-код
- `GET /api/vpn/stats` — статистика

### Billing
- `GET /api/billing/plans` — тарифы
- `POST /api/billing/subscribe` — подписка
- `GET /api/billing/subscription` — текущая подписка

## 🧪 Тестирование

```bash
# Backend
cd backend
pytest --cov=app

# Frontend
cd frontend
npm run test
```

## 📈 Мониторинг

- Health check: `GET /health`
- API Docs: `GET /docs` (только в debug режиме)
- Prometheus metrics: `GET /metrics` (опционально)

## 🤝 Разработка по методике GRACE

Проект разработан по методике **GRACE** (Graph-RAG Anchored Code Engineering):

1. `requirements.xml` — требования продукта
2. `technology.xml` — стек технологий
3. `development-plan.xml` — модули и фазы
4. `verification-plan.xml` — тесты
5. `knowledge-graph.xml` — зависимости

## 📄 Лицензия

MIT License

## 👤 Автор

KrotVPN Team

---

**⚠️ Важно**: AmneziaWG параметры обфускации (Jc, Jmin, Jmax, S1, S2, H1-H4) должны совпадать на сервере и клиенте!
