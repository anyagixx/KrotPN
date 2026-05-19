# 🐀 KrotPN

**Коммерческий VPN-сервис с AmneziaWG Full Tunnel и персональным MTProto proxy для Telegram**

![Version](https://img.shields.io/badge/version-2.19.1-blue)
![Python](https://img.shields.io/badge/python-3.11-green)
![React](https://img.shields.io/badge/react-18-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## 🌟 Особенности

- **AmneziaWG** - обфусцированный WireGuard протокол для обхода DPI
- **Full Tunnel** - весь клиентский трафик проходит через RU Entry Node к DE Exit Node
- **Персональный MTProto proxy** - каждый подтвержденный пользователь получает индивидуальный `u-*.krotpn.xyz` Telegram proxy
- **KPprotoN fake-TLS edge** - RU SNI router на публичном 443 маршрутизирует web и MTProto трафик без раскрытия пользовательских секретов
- **HTTPS production TLS** - операторский wildcard SSL сертификат используется для web, admin и MTProto edge
- **Email verification** - регистрация активируется только после подтверждения почты через Resend
- **Двухуровневая архитектура** - RU Entry Node + DE Exit Node
- **Коммерческая модель** - подписки, триалы, реферальная программа
- **Telegram Bot** - управление через Telegram
- **PWA** - установка как приложение на телефон
- **Интерактивная установка** - одна команда для полного деплоя

## 🏗️ Архитектура

```
┌──────────────────┐
│ Пользователь     │
│ - HTTPS cabinet  │
│ - AWG client     │
│ - Telegram proxy │
└────────┬─────────┘
         │
         │ HTTPS / AWG / MTProto over 443
         ▼
┌──────────────────────────────────────────┐
│ RU Entry Node                            │
│ - HAProxy SNI router :443                │
│ - nginx web/API fallback :9443           │
│ - public admin HTTPS :8443               │
│ - backend/frontend/admin/Postgres/Redis  │
│ - AWG entry                              │
└────────┬────────────────────────┬────────┘
         │                        │
         │ AWG full tunnel        │ u-*.krotpn.xyz SNI
         ▼                        ▼
┌──────────────────┐     ┌─────────────────────────┐
│ DE Exit Node     │     │ DE KPprotoN Runtime      │
│ - AWG exit       │     │ - fake-TLS MTProto :443  │
│ - Internet egress│     │ - private policy API     │
└──────────────────┘     └─────────────────────────┘
```

## 🤖 AI Development Handoff

Проект ведётся по `MyGRACE` для работы с несколькими ИИ-агентами через ленивую навигацию по индексам.

Перед любыми изменениями новый агент должен прочитать файлы в таком порядке:

1. `docs/current-status.xml`
2. `docs/graph-index.xml`
3. `docs/modules/M-XXX.xml` — только модуль, который меняется
4. `docs/plan-index.xml`
5. `docs/plans/Phase-N.xml` — только релевантная фаза
6. `docs/verification-index.xml`
7. `docs/verification/V-M-XXX.xml` — только релевантная проверка
8. `AGENTS.md`

Это обязательный входной слой проекта: он фиксирует текущую стадию разработки,
приоритеты, карту модулей и правила проверки изменений.
Монолитные GRACE-файлы не являются активным входом; они лежат в `docs/archive/classic-grace/` только для редкой исторической справки.

## ⚡ Быстрый старт

### Одна команда установки

```bash
curl -fsSL https://raw.githubusercontent.com/anyagixx/KrotPN/main/install.sh | bash
```

Или с wget:

```bash
wget -qO- https://raw.githubusercontent.com/anyagixx/KrotPN/main/install.sh | bash
```

Установщик проведёт вас через все шаги интерактивно.

### Требования

| Компонент | RU Сервер | DE Сервер |
|-----------|-----------|-----------|
| OS | Ubuntu 20.04/22.04 | Ubuntu 20.04/22.04 |
| CPU | 2+ ядер | 1+ ядро |
| RAM | 2+ GB | 1+ GB |
| Порты | 22, 80, 443, 8443, 51821/udp | 22, 443, 51821/udp |

Перед production-деплоем подготовьте:

- домен, например `krotpn.xyz`, с DNS на RU public IP;
- wildcard DNS для `*.krotpn.xyz`, чтобы персональные MTProto SNI имена резолвились на RU edge;
- wildcard TLS файлы `fullchain1.pem` и `privkey1.pem` на RU сервере;
- Resend API key и подтвержденный sender, например `noreply@krotpn.xyz`;
- чистые RU и DE VPS с root-доступом.

### После установки

| Сервис | URL |
|--------|-----|
| **Frontend** | `https://YOUR_DOMAIN` |
| **Admin Panel** | `https://YOUR_DOMAIN:8443/login` |
| **Backend API** | `https://YOUR_DOMAIN/api/v1/` |
| **User MTProto proxy** | В личном кабинете после подтверждения email |

HTTP автоматически перенаправляется на HTTPS. В production self-signed TLS не используется: установщик просит пути к подготовленным wildcard TLS файлам.

После регистрации пользователь получает письмо подтверждения. VPN trial и персональный MTProto proxy выдаются только после успешного `verify-email`.

### 🔐 Доступ к Admin Panel

После установки используйте учётные данные, которые вы задали в `ADMIN_EMAIL` и `ADMIN_PASSWORD` во время деплоя.

> ⚠️ Не оставляйте дефолтные или предсказуемые значения. Для production используйте уникальный длинный пароль.

### 🖥️ CLI инструменты

Управление администраторами через командную строку:

```bash
# Создать нового админа
docker exec -it krotpn-backend python -m app.cli create-admin -e admin2@example.com -p secret123

# Сбросить пароль
docker exec -it krotpn-backend python -m app.cli reset-password -e your-admin@example.com -p newsecret

# Список всех админов
docker exec -it krotpn-backend python -m app.cli list-admins

# Проверить конфигурацию
docker exec -it krotpn-backend python -m app.cli check-config
```

## 📱 Клиентские приложения

| Платформа | Скачать |
|-----------|---------|
| Android | [Google Play](https://play.google.com/store/apps/details?id=org.amnezia.awg) |
| iOS | [App Store](https://apps.apple.com/app/amneziawg/id6448364248) |
| Windows | [GitHub Releases](https://github.com/amnezia-vpn/amneziawg-windows-client/releases) |
| macOS | [GitHub Releases](https://github.com/amnezia-vpn/amneziawg-apple/releases) |

## 🔧 Управление

### Создание VPN клиента

```bash
ssh root@YOUR_RU_IP
/opt/KrotPN/deploy/create-client.sh username
```

### Проверка состояния

```bash
ssh root@YOUR_RU_IP "docker compose -f /opt/KrotPN/docker-compose.yml ps"
```

### Логи

```bash
ssh root@YOUR_RU_IP "docker compose -f /opt/KrotPN/docker-compose.yml logs -f backend"
```

### Перезапуск

```bash
ssh root@YOUR_RU_IP "cd /opt/KrotPN && docker compose restart"
```

## 📁 Структура проекта

```
KrotPN/
├── install.sh              # Интерактивный установщик
├── backend/                # FastAPI Backend
│   └── app/
│       ├── core/          # Config, Security, Database
│       ├── users/         # Auth & Users
│       ├── vpn/           # AmneziaWG Integration
│       ├── billing/       # YooKassa Payments
│       ├── mtproto/       # Personal Telegram MTProto proxy
│       ├── email/         # Verification email delivery
│       └── referrals/     # Referral System
│
├── frontend/              # React User Dashboard
├── frontend-admin/        # React Admin Panel
├── telegram-bot/          # Telegram Bot
├── mtproto-runtime/       # KPprotoN fake-TLS runtime
├── nginx/                 # HTTPS fallback proxy
│   ├── Dockerfile
│   ├── nginx.conf
│   └── generate-certs.sh
│
├── deploy/                # Deployment Scripts
│   ├── deploy-all.sh     # Автоматический деплой
│   ├── quick-start.sh    # Wrapper для deploy-all.sh
│   ├── mtproto-de-compose.yml
│   ├── haproxy-phase38.cfg
│   ├── create-client.sh
│   └── remove-client.sh
│
└── docker-compose.yml     # Core services + nginx + RU SNI router
```

## 🔐 Безопасность

- **Wildcard TLS** - операторский `fullchain1.pem`/`privkey1.pem` для production HTTPS и MTProto fake-TLS
- **HTTP -> HTTPS** - принудительный redirect на домене проекта
- **Email verification** - trial, VPN и MTProto proxy не выдаются до подтверждения почты
- **Resend provider** - API key вводится при установке и не печатается в логах
- **Private MTProto policy API** - SNI policy apply/revoke доступны только по приватному токену
- **Secret redaction** - raw proxy links, derived secrets, TLS private keys, runtime tokens and email tokens не должны попадать в логи
- **httpOnly cookies** - защита от XSS кражи токенов
- **JWT токены** - короткий срок жизни (15 мин)
- **Token blacklist** - отзыв токенов через Redis
- **Fernet шифрование** - VPN приватные ключи
- **DATA_ENCRYPTION_KEY** - отдельный ключ шифрования (не из JWT secret)
- **Rate limiting** - nginx: 5r/m login, 30r/m API
- **Security headers** - HSTS, CSP, X-Frame-Options
- **Admin audit log** - все действия админов логируются
- **CORS whitelist** - контроль доступа
- **UFW firewall** - на обоих серверах

## 💰 Монетизация

- **Триал**: 3 дня бесплатно
- **Подписки**: 1/3/6/12 месяцев
- **Реферальная программа**: +7 дней за приглашение
- **YooKassa**: приём платежей

## 🌐 API Endpoints

| Endpoint | Описание |
|----------|----------|
| `GET /health` | Health check |
| `POST /api/v1/auth/register` | Регистрация |
| `POST /api/v1/auth/verify-email` | Подтверждение email и активация доступа |
| `POST /api/v1/auth/login` | Авторизация |
| `GET /api/v1/vpn/config` | Получить конфиг VPN |
| `GET /api/v1/vpn/qr` | QR код для клиента |
| `GET /api/v1/mtproto/proxy` | Персональный MTProto proxy для Telegram |
| `GET /api/v1/subscription/status` | Статус подписки |
| `POST /api/v1/billing/create-payment` | Создать платёж |

Полная документация: `https://YOUR_DOMAIN/docs`

## 📞 Поддержка

- **GitHub**: https://github.com/anyagixx/KrotPN
- **Issues**: https://github.com/anyagixx/KrotPN/issues

## 📄 Лицензия

MIT License

---

**Сделано с ❤️ для свободного интернета**
