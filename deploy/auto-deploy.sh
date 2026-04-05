#!/bin/bash
#
# KrotVPN全自动部署脚本
# Запусти на своём компьютере - всё само развернётся
#
# Usage: ./auto-deploy.sh
# GRACE-lite operational contract:
# - This is an opinionated auto-deploy path with hardcoded server IP defaults.
# - It assumes SSH key-based access and mutates both RU and DE hosts.
# - Treat it as convenience automation, not as a hardened universal deployment mechanism.
#

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Конфигурация серверов
RU_IP="${RU_IP:-}"
DE_IP="${DE_IP:-}"
VPN_PORT="51821"

echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     KrotVPN - Автоматический деплой          ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "RU сервер: ${GREEN}${RU_IP}${NC}"
echo -e "DE сервер: ${GREEN}${DE_IP}${NC}"
echo ""

# Проверка SSH
echo -e "${YELLOW}[1/6] Проверка SSH доступа...${NC}"

if ! ssh -o ConnectTimeout=5 -o BatchMode=yes root@${DE_IP} "echo ok" 2>/dev/null; then
    echo -e "${RED}✗ Нет доступа к DE серверу${NC}"
    echo -e "${YELLOW}Выполни: ssh-copy-id root@${DE_IP}${NC}"
    exit 1
fi
echo -e "${GREEN}✓ DE сервер доступен${NC}"

if ! ssh -o ConnectTimeout=5 -o BatchMode=yes root@${RU_IP} "echo ok" 2>/dev/null; then
    echo -e "${RED}✗ Нет доступа к RU серверу${NC}"
    echo -e "${YELLOW}Выполни: ssh-copy-id root@${RU_IP}${NC}"
    exit 1
fi
echo -e "${GREEN}✓ RU сервер доступен${NC}"

# ============================================
# DEPLOY DE SERVER
# ============================================
echo ""
echo -e "${YELLOW}[2/6] Установка DE сервера (Германия)...${NC}"

ssh root@${DE_IP} 'bash -s' << 'DESCRIPT'
set -e

echo "===> Обновление системы..."
apt update && apt upgrade -y

echo "===> Установка зависимостей..."
apt install -y software-properties-common python3-launchpadlib gnupg2 \
    linux-headers-$(uname -r) curl wget git ipset iptables ufw qrencode

echo "===> Установка AmneziaWG..."
if ! command -v awg &> /dev/null; then
    add-apt-repository ppa:amnezia/ppa -y
    apt update
    apt install -y amneziawg amneziawg-tools
fi

echo "===> Включение IP форвардинга..."
echo "net.ipv4.ip_forward=1" > /etc/sysctl.d/99-krotvpn.conf
sysctl -p /etc/sysctl.d/99-krotvpn.conf

echo "===> Генерация ключей..."
mkdir -p /etc/amnezia/amneziawg
cd /etc/amnezia/amneziawg
awg genkey | tee de_private.key | awg pubkey > de_public.key

echo "===> Создание конфигурации (без пира пока)..."
cat > /etc/amnezia/amneziawg/awg0.conf << EOF
[Interface]
PrivateKey = $(cat de_private.key)
Address = 10.200.0.1/24
ListenPort = 51821
Jc = 120
Jmin = 50
Jmax = 1000
S1 = 111
S2 = 222
H1 = 1
H2 = 2
H3 = 3
H4 = 4
EOF

chmod 600 /etc/amnezia/amneziawg/*.conf

echo "===> Настройка firewall..."
ufw --force reset
ufw allow 22/tcp
ufw allow 51821/udp
ufw default deny FORWARD
ufw allow in on awg0
ufw allow out on awg0
ufw --force enable

echo "===> Клонирование проекта..."
cd /opt
if [ -d "KrotVPN" ]; then
    cd KrotVPN && git pull
else
    git clone https://github.com/anyagixx/KrotVPN.git
    cd KrotVPN
fi

echo "===> Генерация секретов..."
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
DATA_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@krotvpn.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")}"

cat > .env << EOF
APP_NAME=KrotVPN
APP_VERSION=2.4.20
DEBUG=false
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8000

SECRET_KEY=${SECRET_KEY}
DATA_ENCRYPTION_KEY=${DATA_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

DB_USER=krotvpn
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=krotvpn
DATABASE_URL=postgresql+asyncpg://krotvpn:${DB_PASSWORD}@db:5432/krotvpn

REDIS_URL=redis://redis:6379/0

CORS_ORIGINS=["http://${RU_IP}","http://localhost"]

ADMIN_EMAIL=${ADMIN_EMAIL}
ADMIN_PASSWORD=${ADMIN_PASSWORD}

VPN_SUBNET=10.10.0.0/24
VPN_PORT=51821
VPN_DNS=8.8.8.8, 1.1.1.1
VPN_MTU=1360
VPN_SERVER_PUBLIC_KEY=${RU_SERVER_PUBLIC_KEY}
VPN_SERVER_ENDPOINT=${RU_IP}

AWG_JC=120
AWG_JMIN=50
AWG_JMAX=1000
AWG_S1=111
AWG_S2=222
AWG_H1=1
AWG_H2=2
AWG_H3=3
AWG_H4=4

TRIAL_DAYS=3
REFERRAL_BONUS_DAYS=7
REFERRAL_MIN_PAYMENT=100.0

DOMAIN=${RU_IP}
EOF

chmod 600 .env

echo "===> RU сервер готов!"
echo "RU_CLIENT_PUBLIC_KEY=${RU_CLIENT_PUBLIC_KEY}"
RUSCRIPT

# Получаем RU client public key
RU_CLIENT_PUBLIC_KEY=$(ssh root@${RU_IP} "cat /etc/amnezia/amneziawg/ru_client_public.key")
echo -e "${GREEN}RU Client Public Key: ${RU_CLIENT_PUBLIC_KEY}${NC}"

# ============================================
# ADD RU PEER TO DE SERVER
# ============================================
echo ""
echo -e "${YELLOW}[4/6] Добавление RU пира на DE сервер...${NC}"

ssh root@${DE_IP} RU_CLIENT_PUBLIC_KEY="${RU_CLIENT_PUBLIC_KEY}" 'bash -s' << 'ADDPEER'
RU_CLIENT_PUBLIC_KEY=$RU_CLIENT_PUBLIC_KEY

# Добавляем пир в конфиг
cat >> /etc/amnezia/amneziawg/awg0.conf << EOF

[Peer]
PublicKey = ${RU_CLIENT_PUBLIC_KEY}
AllowedIPs = 10.200.0.2/32
EOF

# Запускаем AmneziaWG
awg-quick up awg0 2>/dev/null || true

echo "RU peer added to DE server"
ADDPEER

echo -e "${GREEN}✓ RU peer добавлен на DE сервер${NC}"

# ============================================
# START SERVICES ON RU SERVER
# ============================================
echo ""
echo -e "${YELLOW}[5/6] Запуск сервисов на RU сервере...${NC}"

ssh root@${RU_IP} 'bash -s' << 'STARTSERVICES'
# Запускаем AmneziaWG
echo "===> Запуск AmneziaWG..."
awg-quick up awg0 2>/dev/null || true
awg-quick up awg-client 2>/dev/null || true
systemctl enable awg-quick@awg0 >/dev/null 2>&1 || true
systemctl enable awg-quick@awg-client >/dev/null 2>&1 || true
ip route add 10.200.0.0/24 dev awg-client 2>/dev/null || true

# Настраиваем routing
echo "===> Настройка routing..."
/usr/local/bin/setup_routing.sh

# Создаём systemd сервисы
cat > /etc/systemd/system/krotvpn-routing.service << 'SERVICE'
[Unit]
Description=KrotVPN Routing
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/setup_routing.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable krotvpn-routing

# Запускаем Docker
echo "===> Запуск Docker контейнеров..."
cd /opt/KrotVPN
docker compose up -d --build

echo "===> Ожидание запуска backend..."
sleep 15

# Проверяем
echo "===> Проверка туннеля к DE..."
ping -c 3 10.200.0.1 || echo "Туннель не работает!"

echo "===> Проверка backend..."
curl -sf http://localhost:8000/health && echo " - OK" || echo " - FAILED"

STARTSERVICES

# ============================================
# FINAL CHECK
# ============================================
echo ""
echo -e "${YELLOW}[6/6] Финальная проверка...${NC}"

# Проверяем DE
echo -e "${BLUE}DE сервер:${NC}"
ssh root@${DE_IP} "awg show"

# Проверяем RU
echo ""
echo -e "${BLUE}RU сервер:${NC}"
ssh root@${RU_IP} "awg show"

echo ""
echo -e "${BLUE}Docker:${NC}"
ssh root@${RU_IP} "docker ps"

# ============================================
# DONE
# ============================================
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           ДЕПЛОЙ ЗАВЕРШЁН!                   ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Доступ к сервису:${NC}"
echo -e "  Frontend:    ${GREEN}http://${RU_IP}${NC}"
echo -e "  Admin Panel: ${GREEN}http://${RU_IP}:8080${NC}"
echo -e "  Backend API: ${GREEN}http://${RU_IP}:8000${NC}"
echo -e "  Health:      ${GREEN}http://${RU_IP}:8000/health${NC}"
echo ""
echo -e "${BLUE}Создание VPN клиента:${NC}"
echo -e "  ssh root@${RU_IP} '/opt/KrotVPN/deploy/create-client.sh user1'"
echo ""
