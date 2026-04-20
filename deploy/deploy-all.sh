#!/bin/bash
#
# KrotPN Fully Automated Deployment Script v3.0.0 (Full Tunnel)
# Uses SSH key-based authentication
#
# Usage: ./deploy/deploy-all.sh
# Environment variables: RU_IP, RU_USER, DE_IP, DE_USER
# GRACE-lite operational contract:
# - This is a high-risk script: it provisions servers, writes secrets and mutates host networking.
# - All traffic routes via DE server (Full Tunnel, 0.0.0.0/0).
# - No split-tunneling, ipset, or mangle rules.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib/awg-obfuscation.sh
source "${SCRIPT_DIR}/lib/awg-obfuscation.sh"
# shellcheck source=deploy/lib/vpn-network.sh
source "${SCRIPT_DIR}/lib/vpn-network.sh"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration from environment or defaults
RU_IP="${RU_IP:-}"
RU_USER="${RU_USER:-root}"
DE_IP="${DE_IP:-}"
DE_USER="${DE_USER:-root}"
VPN_PORT="${VPN_PORT:-443}"
VPN_NETWORK_ROTATE="${VPN_NETWORK_ROTATE:-0}"

# SSH command wrapper
ssh_ru() {
    ssh -o ConnectTimeout=30 -o LogLevel=ERROR "$RU_USER@$RU_IP" "$@"
}

ssh_de() {
    ssh -o ConnectTimeout=30 -o LogLevel=ERROR "$DE_USER@$DE_IP" "$@"
}

scp_ru() {
    scp -o ConnectTimeout=30 -o LogLevel=ERROR "$1" "$RU_USER@$RU_IP:$2"
}

scp_de() {
    scp -o ConnectTimeout=30 -o LogLevel=ERROR "$1" "$DE_USER@$DE_IP:$2"
}

# Print banner
echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           KrotPN Automated Deployment v3.0.0               ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  RU Server (Entry): ${RU_IP}                            ║"
echo "║  DE Server (Exit):  ${DE_IP}                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check connections
echo -e "${BLUE}[CHECK] Testing SSH connections...${NC}"

if ! ssh_ru "echo ok" 2>/dev/null | grep -q "ok"; then
    echo -e "${RED}ERROR: Cannot connect to RU server${NC}"
    exit 1
fi
echo -e "${GREEN}✓ RU server accessible${NC}"

if ! ssh_de "echo ok" 2>/dev/null | grep -q "ok"; then
    echo -e "${RED}ERROR: Cannot connect to DE server${NC}"
    exit 1
fi
echo -e "${GREEN}✓ DE server accessible${NC}"
scp_ru "${SCRIPT_DIR}/lib/awg-obfuscation.sh" /tmp/krotpn-awg-obfuscation.sh
scp_de "${SCRIPT_DIR}/lib/awg-obfuscation.sh" /tmp/krotpn-awg-obfuscation.sh
scp_ru "${SCRIPT_DIR}/lib/vpn-network.sh" /tmp/krotpn-vpn-network.sh
scp_de "${SCRIPT_DIR}/lib/vpn-network.sh" /tmp/krotpn-vpn-network.sh
echo ""

# ============================================================
# PHASE 1: RU Server - Generate Keys
# ============================================================
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}PHASE 1: RU Server - Installing dependencies & generating keys${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo ""

ssh_ru "STEALTH_ROTATE='${STEALTH_ROTATE:-0}' VPN_PORT='${VPN_PORT}' VPN_CLIENT_SUBNET='${VPN_CLIENT_SUBNET:-}' VPN_CLIENT_GATEWAY='${VPN_CLIENT_GATEWAY:-}' VPN_RELAY_SUBNET='${VPN_RELAY_SUBNET:-}' VPN_RELAY_DE_ADDRESS='${VPN_RELAY_DE_ADDRESS:-}' VPN_RELAY_RU_ADDRESS='${VPN_RELAY_RU_ADDRESS:-}' VPN_CAPACITY_PROFILE='${VPN_CAPACITY_PROFILE:-}' VPN_NETWORK_ROTATE='${VPN_NETWORK_ROTATE:-0}' bash -s" << 'REMOTE_SCRIPT'
set -e
source /tmp/krotpn-awg-obfuscation.sh
source /tmp/krotpn-vpn-network.sh

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${RED}[RU] Missing required command: ${cmd}${NC}"
        exit 1
    fi
}

verify_host_routing_tools() {
    local tools=(ip iptables awg awg-quick curl)
    for tool in "${tools[@]}"; do
        require_command "$tool"
    done
    echo -e "${GREEN}[RU] Host routing toolchain verified${NC}"
}

echo -e "${BLUE}[RU] Updating system...${NC}"
apt update -qq && apt upgrade -y -qq

echo -e "${BLUE}[RU] Installing dependencies...${NC}"
apt install -y -qq software-properties-common python3-launchpadlib gnupg2 \
    linux-headers-$(uname -r) curl wget git iptables ufw qrencode \
    python3-pip python3-cryptography ca-certificates gnupg openssl

echo -e "${BLUE}[RU] Installing Docker...${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sh /tmp/get-docker.sh
    apt install -y -qq docker-compose-plugin
fi

echo -e "${BLUE}[RU] Installing AmneziaWG...${NC}"
if ! command -v awg &> /dev/null; then
    add-apt-repository ppa:amnezia/ppa -y
    apt update -qq
    apt install -y -qq amneziawg amneziawg-tools
fi
awg_configure_userspace
verify_host_routing_tools

echo -e "${BLUE}[RU] Enabling IP forwarding...${NC}"
echo "net.ipv4.ip_forward=1" > /etc/sysctl.d/99-krotpn.conf
sysctl -p /etc/sysctl.d/99-krotpn.conf > /dev/null

echo -e "${BLUE}[RU] Generating AmneziaWG keys...${NC}"
mkdir -p /etc/amnezia/amneziawg
cd /etc/amnezia/amneziawg

if [ ! -f /etc/amnezia/amneziawg/ru_server_private.key ]; then
    echo -e "${BLUE}[RU] Generating new AmneziaWG keys...${NC}"
    awg genkey | tee ru_server_private.key | awg pubkey > ru_server_public.key
    awg genkey | tee ru_client_private.key | awg pubkey > ru_client_public.key
else
    echo -e "${GREEN}[RU] Reusing existing AmneziaWG keys${NC}"
fi

RU_SERVER_PUBLIC=$(cat ru_server_public.key)
RU_CLIENT_PUBLIC=$(cat ru_client_public.key)

EXISTING_VPN_PORT="$(awg_profile_extract /etc/amnezia/amneziawg/awg0.conf ListenPort 2>/dev/null || true)"
if [ "${STEALTH_ROTATE:-0}" != "1" ] && [ -n "$EXISTING_VPN_PORT" ]; then
    VPN_PORT="$EXISTING_VPN_PORT"
    echo -e "${GREEN}[RU] Preserving existing VPN UDP port ${VPN_PORT}${NC}"
fi
awg_profile_ensure CLIENT_ /etc/amnezia/amneziawg/awg0.conf "${STEALTH_ROTATE:-0}"
awg_profile_ensure RELAY_ /etc/amnezia/amneziawg/awg-client.conf "${STEALTH_ROTATE:-0}"
awg_profile_lines CLIENT_ > /etc/amnezia/amneziawg/krotpn-client-profile.conf
awg_profile_lines RELAY_ > /etc/amnezia/amneziawg/krotpn-relay-profile.conf
chmod 600 /etc/amnezia/amneziawg/krotpn-*-profile.conf
vpn_network_resolve /etc/amnezia/amneziawg/awg0.conf /etc/amnezia/amneziawg/awg-client.conf

echo -e "${GREEN}[RU] Keys generated:${NC}"
echo -e "  Server Public: ${RU_SERVER_PUBLIC}"
echo -e "  Client Public: ${RU_CLIENT_PUBLIC}"
REMOTE_SCRIPT

PRESERVED_VPN_PORT=$(ssh_ru "source /tmp/krotpn-awg-obfuscation.sh; awg_profile_extract /etc/amnezia/amneziawg/awg0.conf ListenPort 2>/dev/null || true")
if [ -n "$PRESERVED_VPN_PORT" ]; then
    VPN_PORT="$PRESERVED_VPN_PORT"
fi
NETWORK_ENV=$(ssh_ru "source /tmp/krotpn-vpn-network.sh; VPN_CLIENT_SUBNET='${VPN_CLIENT_SUBNET:-}' VPN_CLIENT_GATEWAY='${VPN_CLIENT_GATEWAY:-}' VPN_RELAY_SUBNET='${VPN_RELAY_SUBNET:-}' VPN_RELAY_DE_ADDRESS='${VPN_RELAY_DE_ADDRESS:-}' VPN_RELAY_RU_ADDRESS='${VPN_RELAY_RU_ADDRESS:-}' VPN_CAPACITY_PROFILE='${VPN_CAPACITY_PROFILE:-}' VPN_NETWORK_ROTATE='${VPN_NETWORK_ROTATE:-0}'; vpn_network_resolve /etc/amnezia/amneziawg/awg0.conf /etc/amnezia/amneziawg/awg-client.conf >/dev/null && vpn_network_env_lines")
eval "$NETWORK_ENV"
RELAY_PROFILE_ENV=$(ssh_ru "source /tmp/krotpn-awg-obfuscation.sh; awg_profile_load RELAY_ /etc/amnezia/amneziawg/krotpn-relay-profile.conf; awg_profile_env_lines RELAY_ RELAY_")
CLIENT_PROFILE_ENV=$(ssh_ru "source /tmp/krotpn-awg-obfuscation.sh; awg_profile_load CLIENT_ /etc/amnezia/amneziawg/krotpn-client-profile.conf; awg_profile_env_lines CLIENT_ CLIENT_")
RELAY_PROFILE_ASSIGNMENTS=$(printf '%s' "$RELAY_PROFILE_ENV" | tr '\n' ' ')

echo ""

# ============================================================
# PHASE 2: DE Server - Full Setup
# ============================================================
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}PHASE 2: DE Server - Full installation and configuration${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo ""

# Get RU client public key
RU_CLIENT_PUBLIC_KEY=$(ssh_ru "cat /etc/amnezia/amneziawg/ru_client_public.key")

ssh_de "RU_CLIENT_PUBLIC_KEY='${RU_CLIENT_PUBLIC_KEY}' VPN_PORT='${VPN_PORT}' STEALTH_ROTATE='${STEALTH_ROTATE:-0}' VPN_CLIENT_SUBNET='${VPN_CLIENT_SUBNET}' VPN_CLIENT_GATEWAY='${VPN_CLIENT_GATEWAY}' VPN_RELAY_SUBNET='${VPN_RELAY_SUBNET}' VPN_RELAY_DE_ADDRESS='${VPN_RELAY_DE_ADDRESS}' VPN_RELAY_RU_ADDRESS='${VPN_RELAY_RU_ADDRESS}' VPN_CAPACITY_PROFILE='${VPN_CAPACITY_PROFILE}' VPN_NETWORK_ROTATE='${VPN_NETWORK_ROTATE}' VPN_NETWORK_PRESERVED='${VPN_NETWORK_PRESERVED:-0}' ${RELAY_PROFILE_ASSIGNMENTS} bash -s" << 'REMOTE_SCRIPT'
set -e
source /tmp/krotpn-awg-obfuscation.sh
source /tmp/krotpn-vpn-network.sh

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${RED}[DE] Missing required command: ${cmd}${NC}"
        exit 1
    fi
}

verify_host_routing_tools() {
    local tools=(ip iptables awg awg-quick curl)
    for tool in "${tools[@]}"; do
        require_command "$tool"
    done
    echo -e "${GREEN}[DE] Host routing toolchain verified${NC}"
}

echo -e "${BLUE}[DE] Updating system...${NC}"
apt update -qq && apt upgrade -y -qq

echo -e "${BLUE}[DE] Installing dependencies...${NC}"
apt install -y -qq software-properties-common python3-launchpadlib gnupg2 \
    linux-headers-$(uname -r) curl wget git iptables ufw qrencode ca-certificates

echo -e "${BLUE}[DE] Installing AmneziaWG...${NC}"
if ! command -v awg &> /dev/null; then
    add-apt-repository ppa:amnezia/ppa -y
    apt update -qq
    apt install -y -qq amneziawg amneziawg-tools
fi
awg_configure_userspace
verify_host_routing_tools

echo -e "${BLUE}[DE] Enabling IP forwarding...${NC}"
echo "net.ipv4.ip_forward=1" > /etc/sysctl.d/99-krotpn.conf
sysctl -p /etc/sysctl.d/99-krotpn.conf > /dev/null

echo -e "${BLUE}[DE] Generating AmneziaWG keys...${NC}"
mkdir -p /etc/amnezia/amneziawg
cd /etc/amnezia/amneziawg

if [ ! -f /etc/amnezia/amneziawg/de_private.key ]; then
    echo -e "${BLUE}[DE] Generating new AmneziaWG keys...${NC}"
    awg genkey | tee de_private.key | awg pubkey > de_public.key
else
    echo -e "${GREEN}[DE] Reusing existing AmneziaWG keys${NC}"
fi

DE_PRIVATE=$(cat de_private.key)
DE_PUBLIC=$(cat de_public.key)

awg_profile_validate RELAY_
vpn_network_apply_defaults
vpn_network_validate
if [ "${STEALTH_ROTATE:-0}" != "1" ] && [ -f /etc/amnezia/amneziawg/awg0.conf ]; then
    awg_profile_load DE_RELAY_ /etc/amnezia/amneziawg/awg0.conf
    awg_profile_require_equal RELAY_ DE_RELAY_ "DE awg0 relay profile"
fi
vpn_network_require_address_match /etc/amnezia/amneziawg/awg0.conf "${VPN_RELAY_DE_CIDR}" "DE awg0 relay"

echo -e "${GREEN}[DE] Keys generated:${NC}"
echo -e "  Public: ${DE_PUBLIC}"

echo -e "${BLUE}[DE] Creating AmneziaWG configuration...${NC}"
cat > /etc/amnezia/amneziawg/awg0.conf << EOF
[Interface]
PrivateKey = ${DE_PRIVATE}
Address = ${VPN_RELAY_DE_CIDR}
ListenPort = ${VPN_PORT}
$(awg_profile_lines RELAY_)

[Peer]
PublicKey = ${RU_CLIENT_PUBLIC_KEY}
AllowedIPs = ${VPN_RELAY_RU_ALLOWED_IP}
EOF

chmod 600 /etc/amnezia/amneziawg/awg0.conf

echo -e "${BLUE}[DE] Configuring firewall...${NC}"
ufw --force reset > /dev/null
ufw default deny FORWARD > /dev/null
ufw allow 22/tcp > /dev/null
ufw allow ${VPN_PORT}/udp > /dev/null
ufw allow in on awg0 > /dev/null
ufw allow out on awg0 > /dev/null

# Add FORWARD rules for tunnel traffic
iptables -D FORWARD -i awg0 -o eth0 -j ACCEPT 2>/dev/null || true
iptables -D FORWARD -i eth0 -o awg0 -j ACCEPT 2>/dev/null || true
iptables -I FORWARD 1 -i awg0 -o eth0 -j ACCEPT
iptables -I FORWARD 2 -i eth0 -o awg0 -j ACCEPT

# Add NAT for both relay and client traffic
EXT_IF=$(ip route | grep default | awk '{print $5}' | head -1)
iptables -t nat -A POSTROUTING -s ${VPN_RELAY_SUBNET} -o $EXT_IF -j MASQUERADE
iptables -t nat -A POSTROUTING -s ${VPN_CLIENT_SUBNET} -o $EXT_IF -j MASQUERADE
mkdir -p /etc/iptables
iptables-save > /etc/iptables/rules.v4
awg_apply_host_hardening "${VPN_PORT}"

ufw --force enable > /dev/null

echo -e "${BLUE}[DE] Starting AmneziaWG...${NC}"
awg-quick down awg0 2>/dev/null || true
awg-quick up awg0

echo -e "${GREEN}[DE] Server ready!${NC}"
REMOTE_SCRIPT

echo ""

# ============================================================
# PHASE 3: RU Server - Complete Setup
# ============================================================
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}PHASE 3: RU Server - Completing configuration & Docker${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo ""

# Get DE public key
DE_PUBLIC_KEY=$(ssh_de "cat /etc/amnezia/amneziawg/de_public.key")

ssh_ru "DE_PUBLIC_KEY='${DE_PUBLIC_KEY}' RU_IP='${RU_IP}' DE_IP='${DE_IP}' VPN_PORT='${VPN_PORT}' VPN_CLIENT_SUBNET='${VPN_CLIENT_SUBNET}' VPN_CLIENT_GATEWAY='${VPN_CLIENT_GATEWAY}' VPN_RELAY_SUBNET='${VPN_RELAY_SUBNET}' VPN_RELAY_DE_ADDRESS='${VPN_RELAY_DE_ADDRESS}' VPN_RELAY_RU_ADDRESS='${VPN_RELAY_RU_ADDRESS}' VPN_CAPACITY_PROFILE='${VPN_CAPACITY_PROFILE}' VPN_NETWORK_ROTATE='${VPN_NETWORK_ROTATE}' VPN_NETWORK_PRESERVED='${VPN_NETWORK_PRESERVED:-0}' bash -s" << 'REMOTE_SCRIPT'
set -e
source /tmp/krotpn-awg-obfuscation.sh
source /tmp/krotpn-vpn-network.sh

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

cd /etc/amnezia/amneziawg

RU_CLIENT_PRIVATE=$(cat ru_client_private.key)
RU_SERVER_PRIVATE=$(cat ru_server_private.key)
RU_SERVER_PUBLIC=$(cat ru_server_public.key)
awg_profile_load CLIENT_ /etc/amnezia/amneziawg/krotpn-client-profile.conf
awg_profile_load RELAY_ /etc/amnezia/amneziawg/krotpn-relay-profile.conf
vpn_network_apply_defaults
vpn_network_validate
vpn_network_require_address_match /etc/amnezia/amneziawg/awg0.conf "${VPN_CLIENT_INTERFACE_CIDR}" "RU awg0 client interface"
vpn_network_require_address_match /etc/amnezia/amneziawg/awg-client.conf "${VPN_RELAY_RU_CIDR}" "RU awg-client relay interface"

echo -e "${BLUE}[RU] Creating tunnel configuration to DE...${NC}"
cat > /etc/amnezia/amneziawg/awg-client.conf << EOF
[Interface]
PrivateKey = ${RU_CLIENT_PRIVATE}
Address = ${VPN_RELAY_RU_CIDR}
Table = off
DNS = 8.8.8.8
$(awg_profile_lines RELAY_)

[Peer]
PublicKey = ${DE_PUBLIC_KEY}
Endpoint = ${DE_IP}:${VPN_PORT}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
EOF

echo -e "${BLUE}[RU] Creating VPN server configuration...${NC}"
cat > /etc/amnezia/amneziawg/awg0.conf << EOF
[Interface]
PrivateKey = ${RU_SERVER_PRIVATE}
Address = ${VPN_CLIENT_INTERFACE_CIDR}
ListenPort = ${VPN_PORT}
$(awg_profile_lines CLIENT_)
EOF

chmod 600 /etc/amnezia/amneziawg/*.conf

# Create sync helper script
echo -e "${BLUE}[RU] Creating helper scripts...${NC}"

cat > /usr/local/bin/krotpn-sync-awg0.sh << 'SYNC_SCRIPT'
#!/bin/bash
set -e

TMP_FILE=$(mktemp)
cleanup() {
    rm -f "$TMP_FILE"
}
trap cleanup EXIT

awg-quick strip awg0 > "$TMP_FILE"
awg syncconf awg0 "$TMP_FILE"
SYNC_SCRIPT
chmod +x /usr/local/bin/krotpn-sync-awg0.sh

echo -e "${BLUE}[RU] Configuring firewall...${NC}"
ufw --force reset > /dev/null
ufw allow 22/tcp > /dev/null
ufw allow 80/tcp > /dev/null
ufw allow 443/tcp > /dev/null
ufw allow 8080/tcp > /dev/null
ufw allow 8443/tcp > /dev/null
# Port 8000 is no longer exposed externally; backend is only accessible via nginx
ufw allow ${VPN_PORT}/udp > /dev/null
ufw default deny FORWARD > /dev/null
ufw allow in on awg0 > /dev/null
ufw allow out on awg0 > /dev/null
ufw allow in on awg-client > /dev/null
ufw allow out on awg-client > /dev/null
ufw --force enable > /dev/null
awg_apply_host_hardening "${VPN_PORT}"

echo -e "${BLUE}[RU] Starting AmneziaWG...${NC}"
awg-quick down awg0 2>/dev/null || true
awg-quick up awg0
systemctl enable awg-quick@awg0 >/dev/null 2>&1 || true
awg-quick down awg-client 2>/dev/null || true
awg-quick up awg-client
systemctl enable awg-quick@awg-client >/dev/null 2>&1 || true
ip route add ${VPN_RELAY_SUBNET} dev awg-client 2>/dev/null || true

# ============================================================
# Full Tunnel: Simple FORWARD rules between awg0 and awg-client
# ============================================================

echo -e "${BLUE}[RU] Configuring Full Tunnel FORWARD rules...${NC}"

# Allow forwarding between awg0 (clients) and awg-client (tunnel to DE)
iptables -D FORWARD -i awg0 -o awg-client -j ACCEPT 2>/dev/null || true
iptables -D FORWARD -i awg-client -o awg0 -j ACCEPT 2>/dev/null || true
iptables -I FORWARD 1 -i awg0 -o awg-client -j ACCEPT
iptables -I FORWARD 2 -i awg-client -o awg0 -j ACCEPT
echo "  FORWARD: awg0 ↔ awg-client ACCEPT"

# NAT on RU: masquerade client traffic going through tunnel
iptables -t nat -D POSTROUTING -s ${VPN_CLIENT_SUBNET} -o awg-client -j MASQUERADE 2>/dev/null || true
iptables -t nat -I POSTROUTING 1 -s ${VPN_CLIENT_SUBNET} -o awg-client -j MASQUERADE
echo "  NAT RU: ${VPN_CLIENT_SUBNET} -> awg-client MASQUERADE"

echo -e "${GREEN}✓ Full Tunnel forwarding configured${NC}"

sleep 2
if ping -c 3 ${VPN_RELAY_DE_ADDRESS} > /dev/null 2>&1; then
    echo -e "${GREEN}[RU] ✓ Tunnel to DE is working!${NC}"
else
    echo -e "${RED}[RU] ✗ Tunnel test failed${NC}"
fi

echo -e "${BLUE}[RU] Cloning KrotPN...${NC}"
cd /opt
if [ -d "KrotPN" ]; then
    cd KrotPN && git pull
else
    git clone https://github.com/anyagixx/KrotPN.git
    cd KrotPN
fi

echo -e "${BLUE}[RU] Generating SSL certificate...${NC}"
mkdir -p /opt/KrotPN/ssl
cd /opt/KrotPN/ssl
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout server.key -out server.crt \
    -subj "/C=RU/ST=Moscow/L=Moscow/O=KrotPN/OU=IT/CN=krotpn.local" 2>/dev/null
chmod 600 server.key
chmod 644 server.crt
echo -e "${GREEN}[RU] SSL certificate generated${NC}"

echo -e "${BLUE}[RU] Generating secrets...${NC}"
cd /opt/KrotPN
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
DATA_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@krotpn.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")}"

cat > .env << EOF
# === APPLICATION ===
APP_NAME=KrotPN
APP_VERSION=3.0.0
DEBUG=false
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8000

# === SECURITY ===
SECRET_KEY=${SECRET_KEY}
DATA_ENCRYPTION_KEY=${DATA_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# === DATABASE ===
DB_USER=krotpn
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=krotpn
DATABASE_URL=postgresql+asyncpg://krotpn:${DB_PASSWORD}@db:5432/krotpn

# === REDIS ===
REDIS_URL=redis://redis:6379/0

# === CORS ===
CORS_ORIGINS=["https://${RU_IP}","http://${RU_IP}","http://localhost"]

# === ADMIN ===
ADMIN_EMAIL=${ADMIN_EMAIL}
ADMIN_PASSWORD=${ADMIN_PASSWORD}

# === VPN CONFIGURATION ===
VPN_SUBNET=${VPN_CLIENT_SUBNET}
VPN_CLIENT_SUBNET=${VPN_CLIENT_SUBNET}
VPN_CLIENT_GATEWAY=${VPN_CLIENT_GATEWAY}
VPN_RELAY_SUBNET=${VPN_RELAY_SUBNET}
VPN_RELAY_DE_ADDRESS=${VPN_RELAY_DE_ADDRESS}
VPN_RELAY_RU_ADDRESS=${VPN_RELAY_RU_ADDRESS}
VPN_CAPACITY_PROFILE=${VPN_CAPACITY_PROFILE}
VPN_NETWORK_ROTATE=${VPN_NETWORK_ROTATE}
VPN_PORT=${VPN_PORT}
VPN_DNS=8.8.8.8, 1.1.1.1
VPN_MTU=1360
VPN_SERVER_PUBLIC_KEY=${RU_SERVER_PUBLIC}
VPN_SERVER_ENDPOINT=${RU_IP}
VPN_ENTRY_SERVER_PUBLIC_KEY=${RU_SERVER_PUBLIC}
VPN_ENTRY_SERVER_ENDPOINT=${RU_IP}
VPN_EXIT_SERVER_PUBLIC_KEY=${DE_PUBLIC_KEY}
VPN_EXIT_SERVER_ENDPOINT=${DE_IP}

# === AMNEZIAWG OBFUSCATION ===
$(awg_profile_env_lines CLIENT_ "AWG_CLIENT_")
$(awg_profile_env_lines RELAY_ "AWG_RELAY_")
$(awg_profile_env_lines CLIENT_ "AWG_")

# === TRIAL ===
TRIAL_DAYS=3

# === YOOKASSA ===
YOOKASSA_SHOP_ID=
YOOKASSA_SECRET_KEY=

# === TELEGRAM ===
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_URL=

# === EMAIL ===
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
EMAIL_FROM=noreply@krotpn.com

# === REFERRAL ===
REFERRAL_BONUS_DAYS=7
REFERRAL_MIN_PAYMENT=100.0

# === DOMAIN ===
DOMAIN=${RU_IP}
EOF

chmod 600 .env

# Systemd service for awg0 peer sync only
cat > /etc/systemd/system/krotpn-sync-awg0.service << 'SERVICE'
[Unit]
Description=Sync awg0 peers for KrotPN
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/krotpn-sync-awg0.sh
SERVICE

cat > /etc/systemd/system/krotpn-sync-awg0.path << 'PATHUNIT'
[Unit]
Description=Watch awg0 config changes for KrotPN

[Path]
PathModified=/etc/amnezia/amneziawg/awg0.conf

[Install]
WantedBy=multi-user.target
PATHUNIT

systemctl daemon-reload
systemctl enable krotpn-sync-awg0.path
systemctl start krotpn-sync-awg0.path

echo -e "${BLUE}[RU] Building and starting Docker containers...${NC}"
docker compose up -d --build

echo -e "${GREEN}[RU] Server setup complete!${NC}"
REMOTE_SCRIPT

echo ""

# ============================================================
# FINAL CHECK
# ============================================================
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}FINAL CHECK: Verifying deployment${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${BLUE}[CHECK] Tunnel RU ↔ DE...${NC}"
if ssh_ru "ping -c 2 ${VPN_RELAY_DE_ADDRESS}" 2>/dev/null | grep -q "bytes from"; then
    echo -e "${GREEN}✓ Tunnel working${NC}"
else
    echo -e "${RED}✗ Tunnel not working${NC}"
fi

echo -e "${BLUE}[CHECK] Docker containers...${NC}"
sleep 5
ssh_ru "docker compose -f /opt/KrotPN/docker-compose.yml ps"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              DEPLOYMENT COMPLETE!                           ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║                                                              ║${NC}"
echo -e "${GREEN}║  🌐 Frontend:    https://${RU_IP}                           ${NC}"
echo -e "${GREEN}║  🔧 Admin Panel: https://${RU_IP}:8443                     ${NC}"
echo -e "${GREEN}║  🔌 Backend API: https://${RU_IP}:8000                     ${NC}"
echo -e "${GREEN}║                                                              ║${NC}"
echo -e "${YELLOW}║  ⚠️  Browser will warn about self-signed certificate.       ${NC}"
echo -e "${YELLOW}║     Click 'Advanced' → 'Proceed' to continue.               ${NC}"
echo -e "${GREEN}║                                                              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
