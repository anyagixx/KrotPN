# 🐀 KrotPN

**Коммерческий VPN-сервис с AmneziaWG Full Tunnel и персональным MTProto proxy для Telegram**

![Version](https://img.shields.io/badge/version-2.21.3-blue)
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

### Тарифы KrotPN

KrotPN публикует три канонических paid-тарифа на 30 дней. Они создаются и обновляются backend автоматически при старте, поэтому clean deploy и существующая база сходятся к одной матрице без ручного редактирования:

| Slug | Цена | Устройств | Назначение |
|------|------|-----------|------------|
| `krotpn-1` | 369 ₽ | 1 | персональный доступ |
| `krotpn-6` | 693 ₽ | 6 | основной семейный/мультидевайс тариф |
| `krotpn-9` | 936 ₽ | 9 | максимальный стандартный тариф |

Frontend отправляет на оплату только `plan_id`. Цена, валюта, длительность, лимит устройств и YooKassa metadata вычисляются на backend из канонического каталога. Если у пользователя уже занято больше устройств, чем допускает выбранный тариф, checkout блокируется до создания платежа.

Успешный paid webhook отменяет pending trial, активирует или продлевает платную подписку и передает выбранный `device_limit` в политику выдачи VPN-конфигов. Персональный MTProto proxy остается бесплатным verified-email entitlement и не переносится за платный тариф в Phase-50.

### Email Sender Avatar (BIMI)

KrotPN публикует BIMI SVG для sender branding по адресу:

```text
https://krotpn.xyz/.well-known/bimi/krotpn.svg
```

После деплоя и проверки URL добавьте DNS запись:

```text
Host/Name: default._bimi
Type: TXT
Value: v=BIMI1; l=https://krotpn.xyz/.well-known/bimi/krotpn.svg;
```

Если DNS-панель требует полный host, используйте `default._bimi.krotpn.xyz`.
Do not add `a=` until VMC/CMC PEM certificate material exists.

BIMI работает только если почтовый провайдер успешно проверяет SPF/DKIM/DMARC. Для Gmail и Apple аватар может не отображаться без VMC/CMC даже при корректной DNS записи. Resend отправляет письма от `noreply@krotpn.xyz`, но сам не управляет аватаркой отправителя в почтовых клиентах.

### Favicon and Email Logo

KrotPN ships browser favicon assets for the user cabinet and admin panel:

- `frontend/public/favicon.ico`
- `frontend/public/favicon-16x16.png`
- `frontend/public/favicon-32x32.png`
- `frontend/public/apple-touch-icon.png`
- `frontend/public/pwa-192x192.png`
- `frontend/public/pwa-512x512.png`
- `frontend-admin/public/favicon.ico`

HTML-письма подтверждения email и сброса пароля, которые отправляются через Resend, показывают логотип из публичного frontend URL:

```text
https://krotpn.xyz/brand/email-logo.png
```

Это именно логотип внутри письма. Он не заменяет BIMI и не заставляет почтовые клиенты показывать аватарку отправителя рядом с `noreply@krotpn.xyz`.

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

### MTProto Promotion Tag

KrotPN использует персональные fake-TLS MTProto proxy: у каждого пользователя свой `server=u-*.krotpn.xyz` и длинный `secret=ee...`.
`@MTProxybot` при регистрации просит не полный `ee...` secret, а внутренние 32 hex символа.

Чтобы получить и применить promotion tag:

1. Возьмите любой рабочий MTProto proxy из личного кабинета тестового или служебного пользователя.
2. Разберите secret:

```text
secret=ee<32_hex_secret><hex_encoded_sni>
```

Например, из `ee00112233445566778899aabbccddeeff...` для бота нужно взять только:

```text
00112233445566778899aabbccddeeff
```

3. В `@MTProxybot` выполните `/newproxy`, укажите `YOUR_DOMAIN:443`, затем передайте эти 32 hex символа.
4. Бот выдаст promotion tag формата `32 hex`, например `0123456789abcdef0123456789abcdef`.
5. В Admin Panel откройте `MTProto -> Settings -> Promotion tag`, вставьте tag и нажмите `Save tag`.

Если статус стал `pending_restart`, tag уже сохранён в KrotPN, но backend и DE MTProto runtime ещё не перечитали `MTPROTO_AD_TAG` из `.env`.
Примените tag на обоих серверах:

```bash
# RU server
TAG='YOUR_32_HEX_PROMOTION_TAG'
cd /opt/KrotPN
sed -i -E "s/^MTPROTO_AD_TAG=.*/MTPROTO_AD_TAG=${TAG}/" .env
docker compose up -d --force-recreate backend
```

```bash
# DE server
TAG='YOUR_32_HEX_PROMOTION_TAG'
cd /opt/krotpn-mtproto
sed -i -E "s/^MTPROTO_AD_TAG=.*/MTPROTO_AD_TAG=${TAG}/" .env
docker compose up -d --force-recreate mtproto-de-runtime
```

После restart откройте Admin Panel и сохраните тот же promotion tag ещё раз. Статус должен стать `applied`.
Promotion tag применяется глобально к MTProto runtime и не меняет уже выданные пользовательские proxy-ссылки.

> Не отправляйте в `@MTProxybot` значения `MTPROTO_BASE_SECRET_HEX`, `MTPROTO_SECRET_SALT` или полный `ee...` secret.

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
