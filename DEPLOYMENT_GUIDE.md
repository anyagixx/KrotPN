# 🚀 Руководство по запуску KrotPN

## 📋 Содержание

1. [Требования](#требования)
2. [Быстрый старт](#быстрый-старт)
3. [Подробная установка](#подробная-установка)
4. [Конфигурация](#конфигурация)
5. [Запуск](#запуск)
6. [Проверка](#проверка)
7. [Устранение неполадок](#устранение-неполадок)

---

## Требования

### Сервер (минимум)

| Компонент | Версия |
|-----------|--------|
| OS | Ubuntu 20.04/22.04 LTS |
| CPU | 2 ядра |
| RAM | 2 GB |
| Disk | 20 GB SSD |
| Network | 100 Mbps+ |

### Программное обеспечение

| Компонент | Версия |
|-----------|--------|
| Docker | 24.0+ |
| Docker Compose | 2.20+ |
| Python | 3.11+ |
| Node.js | 20+ |
| PostgreSQL | 15+ |
| Redis | 7+ |

---

## Быстрый старт

### Вариант 1: Docker (рекомендуется)

```bash
# 1. Клонируем репозиторий
git clone https://github.com/anyagixx/KrotPN.git
cd KrotPN

# 2. Создаём .env файл
cp .env.example .env
nano .env  # Заполните все переменные!

# 3. Запускаем
docker-compose up -d

# 4. Проверяем
curl http://localhost:8000/health
```

### Вариант 2: Ручная установка

```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend (другой терминал)
cd frontend
npm install
npm run build
npm run preview

# Admin (другой терминал)
cd frontend-admin
npm install
npm run build
npm run preview
```

---

## Подробная установка

### Шаг 1: Подготовка сервера

```bash
# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Устанавливаем Docker Compose
sudo apt install docker-compose-plugin

# Перезаходим в систему
exit
# ssh снова
```

### Шаг 2: Установка AmneziaWG

```bash
# Добавляем репозиторий
sudo add-apt-repository ppa:amnezia/ppa -y
sudo apt update

# Устанавливаем AmneziaWG
sudo apt install amneziawg amneziawg-tools -y

# Включаем форвардинг
echo "net.ipv4.ip_forward=1" | sudo tee /etc/sysctl.d/99-krotpn.conf
sudo sysctl -p /etc/sysctl.d/99-krotpn.conf
```

### Шаг 3: Клонирование проекта

```bash
git clone https://github.com/anyagixx/KrotPN.git
cd KrotPN
```

### Шаг 4: Генерация ключей

```bash
# Генерируем SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32)"
# Сохраните вывод!

# Генерируем DATA_ENCRYPTION_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Сохраните вывод!

# Генерируем ключи AmneziaWG (на сервере)
awg genkey | tee privatekey | awg pubkey > publickey
cat privatekey  # Сохраните!
cat publickey   # Сохраните!
```

### Шаг 5: Конфигурация .env

```bash
cp .env.example .env
nano .env
```

Заполните следующие **обязательные** переменные:

```env
# === ОБЯЗАТЕЛЬНЫЕ ===
SECRET_KEY=ваш_32_символьный_ключ
DATA_ENCRYPTION_KEY=ваш_fernet_ключ
DATABASE_URL=postgresql+asyncpg://krotpn:password@db:5432/krotpn

# === YOOKASSA ===
YOOKASSA_SHOP_ID=ваш_shop_id
YOOKASSA_SECRET_KEY=ваш_secret_key

# === TELEGRAM ===
TELEGRAM_BOT_TOKEN=ваш_токен_бота

# === VPN ===
VPN_SERVER_PUBLIC_KEY=публичный_ключ_сервера
VPN_SERVER_ENDPOINT=ip_сервера
```

---

## Конфигурация

### Переменные окружения

| Переменная | Обязательно | Описание |
|------------|-------------|----------|
| `SECRET_KEY` | ✅ | JWT secret (32+ символа) |
| `DATA_ENCRYPTION_KEY` | ✅ | Fernet ключ для шифрования |
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `REDIS_URL` | ❌ | Redis URL (default: redis://redis:6379/0) |
| `YOOKASSA_SHOP_ID` | ✅ | YooKassa shop ID |
| `YOOKASSA_SECRET_KEY` | ✅ | YooKassa secret key |
| `TELEGRAM_BOT_TOKEN` | ✅ | Telegram bot token |
| `VPN_SERVER_PUBLIC_KEY` | ✅ | AmneziaWG public key |
| `VPN_SERVER_ENDPOINT` | ✅ | VPN server IP |
| `ADMIN_EMAIL` | ❌ | Admin email |
| `ADMIN_PASSWORD` | ❌ | Admin password (change on first run!) |
| `TRIAL_DAYS` | ❌ | Trial period (default: 3) |
| `REFERRAL_BONUS_DAYS` | ❌ | Referral bonus (default: 7) |

### Полный пример .env

```env
# Application
APP_NAME=KrotPN
APP_VERSION=1.0.0
DEBUG=false
ENVIRONMENT=production

# Server
HOST=0.0.0.0
PORT=8000

# Database
DATABASE_URL=postgresql+asyncpg://krotpn:SecurePassword123@db:5432/krotpn

# Redis
REDIS_URL=redis://redis:6379/0

# Security
SECRET_KEY=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Data Encryption
DATA_ENCRYPTION_KEY=Z7Y8x9w0v1u2t3s4r5q6p7o8n9m0l1k2j3i4h5g6f7e8=

# CORS
CORS_ORIGINS=["https://krotpn.com","https://admin.krotpn.com"]

# Admin
ADMIN_EMAIL=admin@krotpn.com
ADMIN_PASSWORD=ChangeMeImmediately123!

# VPN Configuration
VPN_SUBNET=10.10.0.0/24
VPN_PORT=51821
VPN_DNS=8.8.8.8, 1.1.1.1
VPN_MTU=1360

# AmneziaWG Obfuscation
AWG_JC=120
AWG_JMIN=50
AWG_JMAX=1000
AWG_S1=111
AWG_S2=222
AWG_H1=1
AWG_H2=2
AWG_H3=3
AWG_H4=4

# Trial
TRIAL_DAYS=3

# YooKassa
YOOKASSA_SHOP_ID=123456
YOOKASSA_SECRET_KEY=test_XXXXXXXXXXXXXXXXXXXXXXXX

# Telegram
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=noreply@krotpn.com

# Referral
REFERRAL_BONUS_DAYS=7
REFERRAL_MIN_PAYMENT=100.0
```

---

## Запуск

### Development режим

```bash
# Terminal 1: Backend
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Frontend User
cd frontend
npm run dev

# Terminal 3: Frontend Admin
cd frontend-admin
npm run dev

# Terminal 4: Telegram Bot
cd telegram-bot
source venv/bin/activate
TELEGRAM_BOT_TOKEN=xxx python bot.py
```

### Production режим (Docker)

```bash
# Сборка и запуск
docker-compose up -d --build

# Просмотр логов
docker-compose logs -f

# Перезапуск
docker-compose restart

# Остановка
docker-compose down
```

### Production режим (Systemd)

```bash
# Создаём сервис для backend
sudo tee /etc/systemd/system/krotpn-backend.service << 'SERVICE'
[Unit]
Description=KrotPN Backend API
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=krotpn
WorkingDirectory=/opt/krotpn/backend
Environment="PATH=/opt/krotpn/backend/venv/bin"
ExecStart=/opt/krotpn/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable krotpn-backend
sudo systemctl start krotpn-backend
```

---

## Проверка

### Backend

```bash
# Health check
curl http://localhost:8000/health

# Ожидаемый ответ:
# {"status": "healthy", "version": "1.0.0", "environment": "production"}

# API документация (только в debug режиме)
open http://localhost:8000/docs
```

### Frontend

```bash
# User dashboard
open http://localhost:5173

# Admin panel
open http://localhost:5174
```

### Database

```bash
# Подключение к PostgreSQL
docker exec -it krotpn-db psql -U krotpn -d krotpn

# Проверка таблиц
\dt

# Выход
\q
```

### VPN

```bash
# Проверка интерфейса
awg show

# Проверка порта
sudo ss -ulpn | grep 51821
```

---

## Устранение неполадок

### Проблема: Backend не запускается

```bash
# Проверяем логи
docker-compose logs backend

# Частые причины:
# 1. Не заполнен .env
# 2. Неверный DATABASE_URL
# 3. Не установлен PostgreSQL

# Проверяем подключение к БД
docker exec -it krotpn-db pg_isready -U krotpn
```

### Проблема: Frontend не подключается к API

```bash
# Проверяем CORS в .env
CORS_ORIGINS=["http://localhost:5173","http://localhost:5174"]

# Проверяем что backend запущен
curl http://localhost:8000/health
```

### Проблема: YooKassa webhook не работает

```bash
# Проверяем что webhook URL доступен из интернета
curl https://your-domain.com/api/billing/webhooks/yookassa

# Проверяем логи
docker-compose logs backend | grep YOOKASSA
```

### Проблема: Telegram бот не отвечает

```bash
# Проверяем токен
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe

# Проверяем логи бота
docker-compose logs telegram-bot
```

### Проблема: VPN не подключается

```bash
# Проверяем интерфейс
awg show

# Проверяем порт
sudo ss -ulpn | grep 51821

# Проверяем firewall
sudo ufw status
sudo ufw allow 51821/udp
```

---

## Мониторинг

### Логи

```bash
# Все сервисы
docker-compose logs -f

# Конкретный сервис
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f telegram-bot
```

### Метрики

```bash
# System health
curl http://localhost:8000/api/admin/system/health

# Stats
curl http://localhost:8000/api/admin/stats
```

---

## Обновление

```bash
# Останавливаем
docker-compose down

# Забираем изменения
git pull origin main

# Пересобираем и запускаем
docker-compose up -d --build

# Применяем миграции (если есть)
docker-compose exec backend alembic upgrade head
```

---

## Backup

```bash
# Backup базы данных
docker exec krotpn-db pg_dump -U krotpn krotpn > backup_$(date +%Y%m%d).sql

# Restore
cat backup_20260321.sql | docker exec -i krotpn-db psql -U krotpn krotpn
```

---

## Контакты поддержки

- **Telegram:** @krotpn_support
- **Email:** support@krotpn.com
- **GitHub Issues:** https://github.com/anyagixx/KrotPN/issues

---

*Документация обновлена: 21.03.2026*
