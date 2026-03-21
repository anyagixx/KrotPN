#!/bin/bash
#
# KrotVPN Interactive Installer
# Run this command to install:
#   curl -fsSL https://raw.githubusercontent.com/anyagixx/KrotVPN/main/install.sh | bash
#
# This script installs everything on remote servers via SSH.
# Nothing is installed locally.
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Print functions
print_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║                         K R O T V P N                        ║"
    echo "║                                                              ║"
    echo "║              Interactive Installer v2.1.3                    ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_step() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ $1${NC}"; }

# Read input from terminal
ask() {
    local prompt="$1"
    local default="$2"
    local var="$3"
    
    if [ -n "$default" ]; then
        echo -ne "${YELLOW}${prompt} [${default}]: ${NC}"
    else
        echo -ne "${YELLOW}${prompt}: ${NC}"
    fi
    
    read -r value < /dev/tty
    
    if [ -z "$value" ] && [ -n "$default" ]; then
        value="$default"
    fi
    
    eval "$var='$value'"
}

# Read password with asterisks
ask_password() {
    local prompt="$1"
    local var="$2"
    
    echo -ne "${YELLOW}${prompt}: ${NC}"
    
    local password=""
    local char=""
    
    while IFS= read -r -n1 -s char < /dev/tty; do
        if [[ -z "$char" ]]; then
            echo ""
            break
        elif [[ "$char" == $'\x7f' ]] || [[ "$char" == $'\x08' ]]; then
            if [ -n "$password" ]; then
                password="${password%?}"
                echo -ne "\b \b"
            fi
        else
            password+="$char"
            echo -n "*"
        fi
    done
    
    eval "$var='$password'"
}

ask_yesno() {
    local prompt="$1"
    local default="$2"
    local var="$3"
    
    if [ "$default" = "y" ]; then
        echo -ne "${YELLOW}${prompt} [Y/n]: ${NC}"
    else
        echo -ne "${YELLOW}${prompt} [y/N]: ${NC}"
    fi
    
    read -r value < /dev/tty
    value=$(echo "$value" | tr '[:upper:]' '[:lower:]')
    
    if [ -z "$value" ]; then
        value="$default"
    fi
    
    if [ "$value" = "y" ] || [ "$value" = "yes" ]; then
        eval "$var='y'"
    else
        eval "$var='n'"
    fi
}

# SSH command wrapper
ssh_run() {
    local host="$1"
    local user="$2"
    local pass="$3"
    shift 3
    local cmd="$@"
    
    sshpass -p "$pass" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o ConnectTimeout=30 -o LogLevel=ERROR "$user@$host" "$cmd"
}

# Check prerequisites
check_prerequisites() {
    print_step "Step 1: Checking prerequisites"
    
    # Check sshpass
    if ! command -v sshpass &> /dev/null; then
        print_info "Installing sshpass..."
        if command -v sudo &> /dev/null; then
            sudo apt update -qq && sudo apt install -y -qq sshpass
        else
            apt update -qq && apt install -y -qq sshpass
        fi
    fi
    print_success "sshpass available"
    
    # Check SSH
    if ! command -v ssh &> /dev/null; then
        print_error "SSH client not found"
        exit 1
    fi
    print_success "SSH client available"
}

# Get server information
get_server_info() {
    print_step "Step 2: Server configuration"
    
    echo -e "${BLUE}KrotVPN requires two servers:${NC}"
    echo -e "  ${CYAN}• RU Server (Russia)${NC} - Entry node, hosts the application"
    echo -e "  ${CYAN}• DE Server (Germany/EU)${NC} - Exit node, provides internet access"
    echo ""
    
    ask "Enter RU Server IP address" "" RU_IP
    if [ -z "$RU_IP" ]; then
        print_error "RU Server IP is required"
        exit 1
    fi
    
    ask "Enter DE Server IP address" "" DE_IP
    if [ -z "$DE_IP" ]; then
        print_error "DE Server IP is required"
        exit 1
    fi
    
    echo ""
    echo -e "${GREEN}Configuration:${NC}"
    echo -e "  RU Server: ${CYAN}${RU_IP}${NC}"
    echo -e "  DE Server: ${CYAN}${DE_IP}${NC}"
    echo ""
    
    ask_yesno "Is this correct?" "y" CONFIRM
    if [ "$CONFIRM" != "y" ]; then
        print_error "Installation cancelled"
        exit 1
    fi
}

# Get SSH credentials
get_credentials() {
    print_step "Step 3: SSH credentials"
    
    echo -e "${BLUE}Enter SSH credentials for your servers:${NC}"
    echo ""
    
    # RU Server
    echo -e "${CYAN}RU Server (${RU_IP}):${NC}"
    ask "  SSH username" "root" RU_USER
    ask_password "  SSH password" RU_PASS
    if [ -z "$RU_PASS" ]; then
        print_error "Password is required"
        exit 1
    fi
    echo ""
    
    # DE Server
    echo -e "${CYAN}DE Server (${DE_IP}):${NC}"
    ask "  SSH username" "root" DE_USER
    ask_password "  SSH password" DE_PASS
    if [ -z "$DE_PASS" ]; then
        print_error "Password is required"
        exit 1
    fi
    echo ""
    
    # Test connections
    print_info "Testing connection to RU server..."
    if ssh_run "$RU_IP" "$RU_USER" "$RU_PASS" "echo ok" 2>/dev/null | grep -q "ok"; then
        print_success "RU server connection OK"
    else
        print_error "Cannot connect to RU server. Check credentials."
        exit 1
    fi
    
    print_info "Testing connection to DE server..."
    if ssh_run "$DE_IP" "$DE_USER" "$DE_PASS" "echo ok" 2>/dev/null | grep -q "ok"; then
        print_success "DE server connection OK"
    else
        print_error "Cannot connect to DE server. Check credentials."
        exit 1
    fi
}

# Deploy to servers
deploy() {
    print_step "Step 4: Starting deployment"
    
    echo -e "${BLUE}This will:${NC}"
    echo -e "  1. Clone KrotVPN repository on RU server"
    echo -e "  2. Install dependencies on both servers"
    echo -e "  3. Install and configure AmneziaWG"
    echo -e "  4. Set up VPN tunnel between servers"
    echo -e "  5. Install Docker and run KrotVPN containers"
    echo -e "  6. Generate SSL certificates for HTTPS"
    echo ""
    
    ask_yesno "Start deployment?" "y" START_DEPLOY
    if [ "$START_DEPLOY" != "y" ]; then
        print_error "Deployment cancelled"
        exit 1
    fi
    
    print_info "This will take 10-15 minutes. Please wait..."
    echo ""
    
    # Run deployment script on RU server
    # Pass credentials and DE server info as environment variables
    ssh_run "$RU_IP" "$RU_USER" "$RU_PASS" "DE_IP='$DE_IP' DE_USER='$DE_USER' DE_PASS='$DE_PASS' bash -s" << 'REMOTE_DEPLOY'
#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

RU_IP=$(curl -s ifconfig.me)
VPN_PORT="51821"

echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}        KrotVPN Deployment on RU Server${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo ""

# SSH wrapper for DE server
ssh_de() {
    sshpass -p "$DE_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o ConnectTimeout=30 -o LogLevel=ERROR "$DE_USER@$DE_IP" "$@"
}

# ============================================================
# PHASE 1: Setup RU Server
# ============================================================
echo -e "${CYAN}[RU] Installing dependencies...${NC}"
apt update -qq && apt upgrade -y -qq
apt install -y -qq software-properties-common python3-launchpadlib gnupg2 \
    linux-headers-$(uname -r) curl wget git ipset iptables ufw qrencode \
    python3-pip python3-cryptography ca-certificates gnupg openssl sshpass

echo -e "${CYAN}[RU] Installing Docker...${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sh /tmp/get-docker.sh
    apt install -y -qq docker-compose-plugin
fi

echo -e "${CYAN}[RU] Installing AmneziaWG...${NC}"
if ! command -v awg &> /dev/null; then
    add-apt-repository ppa:amnezia/ppa -y
    apt update -qq
    apt install -y -qq amneziawg amneziawg-tools
fi

echo -e "${CYAN}[RU] Enabling IP forwarding...${NC}"
echo "net.ipv4.ip_forward=1" > /etc/sysctl.d/99-krotvpn.conf
sysctl -p /etc/sysctl.d/99-krotvpn.conf > /dev/null

echo -e "${CYAN}[RU] Generating AmneziaWG keys...${NC}"
mkdir -p /etc/amnezia/amneziawg
cd /etc/amnezia/amneziawg
awg genkey | tee ru_server_private.key | awg pubkey > ru_server_public.key
awg genkey | tee ru_client_private.key | awg pubkey > ru_client_public.key

RU_SERVER_PUBLIC=$(cat ru_server_public.key)
RU_CLIENT_PUBLIC=$(cat ru_client_public.key)
RU_CLIENT_PRIVATE=$(cat ru_client_private.key)
RU_SERVER_PRIVATE=$(cat ru_server_private.key)

echo -e "${GREEN}[RU] Keys generated${NC}"

# ============================================================
# PHASE 2: Setup DE Server
# ============================================================
echo ""
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}[DE] Setting up DE Server...${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"

ssh_de "RU_CLIENT_PUBLIC_KEY='${RU_CLIENT_PUBLIC}' VPN_PORT='${VPN_PORT}' bash -s" << 'DE_SCRIPT'
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}[DE] Installing dependencies...${NC}"
apt update -qq && apt upgrade -y -qq
apt install -y -qq software-properties-common python3-launchpadlib gnupg2 \
    linux-headers-$(uname -r) curl wget git ipset iptables ufw qrencode ca-certificates

echo -e "${CYAN}[DE] Installing AmneziaWG...${NC}"
if ! command -v awg &> /dev/null; then
    add-apt-repository ppa:amnezia/ppa -y
    apt update -qq
    apt install -y -qq amneziawg amneziawg-tools
fi

echo -e "${CYAN}[DE] Enabling IP forwarding...${NC}"
echo "net.ipv4.ip_forward=1" > /etc/sysctl.d/99-krotvpn.conf
sysctl -p /etc/sysctl.d/99-krotvpn.conf > /dev/null

echo -e "${CYAN}[DE] Generating keys...${NC}"
mkdir -p /etc/amnezia/amneziawg
cd /etc/amnezia/amneziawg
awg genkey | tee de_private.key | awg pubkey > de_public.key

DE_PRIVATE=$(cat de_private.key)
DE_PUBLIC=$(cat de_public.key)

echo -e "${CYAN}[DE] Creating AmneziaWG config...${NC}"
cat > /etc/amnezia/amneziawg/awg0.conf << EOF
[Interface]
PrivateKey = ${DE_PRIVATE}
Address = 10.200.0.1/24
ListenPort = ${VPN_PORT}
Jc = 120
Jmin = 50
Jmax = 1000
S1 = 111
S2 = 222
H1 = 1
H2 = 2
H3 = 3
H4 = 4

[Peer]
PublicKey = ${RU_CLIENT_PUBLIC_KEY}
AllowedIPs = 10.200.0.2/32
EOF

chmod 600 /etc/amnezia/amneziawg/awg0.conf

echo -e "${CYAN}[DE] Configuring firewall...${NC}"
ufw --force reset > /dev/null
ufw allow 22/tcp > /dev/null
ufw allow ${VPN_PORT}/udp > /dev/null
sed -i 's/DEFAULT_FORWARD_POLICY="DROP"/DEFAULT_FORWARD_POLICY="ACCEPT"/' /etc/default/ufw

cat > /etc/ufw/before.rules << 'NAT'
*nat
:POSTROUTING ACCEPT [0:0]
-A POSTROUTING -s 10.200.0.0/24 -o eth0 -j MASQUERADE
COMMIT
NAT

ufw --force enable > /dev/null

echo -e "${CYAN}[DE] Starting AmneziaWG...${NC}"
awg-quick down awg0 2>/dev/null || true
awg-quick up awg0

echo -e "${GREEN}[DE] Server ready!${NC}"
echo "DE_PUBLIC_KEY=${DE_PUBLIC}"
DE_SCRIPT

# Get DE public key
DE_PUBLIC_KEY=$(ssh_de "cat /etc/amnezia/amneziawg/de_public.key")
echo -e "${GREEN}[RU] Got DE public key${NC}"

# ============================================================
# PHASE 3: Complete RU Server Setup
# ============================================================
echo ""
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}[RU] Completing configuration...${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"

cd /etc/amnezia/amneziawg

# Create tunnel config to DE
cat > awg-client.conf << EOF
[Interface]
PrivateKey = ${RU_CLIENT_PRIVATE}
Address = 10.200.0.2/24
DNS = 8.8.8.8
Jc = 120
Jmin = 50
Jmax = 1000
S1 = 111
S2 = 222
H1 = 1
H2 = 2
H3 = 3
H4 = 4

[Peer]
PublicKey = ${DE_PUBLIC_KEY}
Endpoint = ${DE_IP}:${VPN_PORT}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
EOF

# Create VPN server config
cat > awg0.conf << EOF
[Interface]
PrivateKey = ${RU_SERVER_PRIVATE}
Address = 10.10.0.1/24
ListenPort = ${VPN_PORT}
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

chmod 600 *.conf

# Setup scripts
cat > /usr/local/bin/update_ru_ips.sh << 'UPDATE_SCRIPT'
#!/bin/bash
ipset create ru_ips hash:net 2>/dev/null || ipset flush ru_ips
ipset add ru_ips 10.0.0.0/8 2>/dev/null || true
ipset add ru_ips 192.168.0.0/16 2>/dev/null || true
ipset add ru_ips 172.16.0.0/12 2>/dev/null || true
ipset add ru_ips 127.0.0.0/8 2>/dev/null || true
curl -sL --connect-timeout 10 https://raw.githubusercontent.com/ipverse/rir-ip/master/country/ru/ipv4-aggregated.txt 2>/dev/null | \
    grep -v '^#' | grep -E '^[0-9]' | while read line; do
        ipset add ru_ips $line 2>/dev/null || true
    done
echo "RU IPset updated"
UPDATE_SCRIPT
chmod +x /usr/local/bin/update_ru_ips.sh

cat > /usr/local/bin/setup_routing.sh << 'ROUTING_SCRIPT'
#!/bin/bash
CLIENT_IF="awg0"
TUNNEL_IF="awg-client"
FWMARK=255
ROUTING_TABLE=100

ipset create ru_ips hash:net 2>/dev/null || ipset flush ru_ips
ipset create custom_direct hash:net 2>/dev/null || ipset flush custom_direct
ipset create custom_vpn hash:net 2>/dev/null || ipset flush custom_vpn

ip rule del fwmark $FWMARK lookup $ROUTING_TABLE 2>/dev/null || true
ip rule add fwmark $FWMARK lookup $ROUTING_TABLE

ip route del default dev $TUNNEL_IF table $ROUTING_TABLE 2>/dev/null || true
ip route add default dev $TUNNEL_IF table $ROUTING_TABLE

iptables -t mangle -F AMNEZIA_PREROUTING 2>/dev/null || true
iptables -t mangle -N AMNEZIA_PREROUTING 2>/dev/null || iptables -t mangle -F AMNEZIA_PREROUTING
iptables -t mangle -D PREROUTING -i $CLIENT_IF -j AMNEZIA_PREROUTING 2>/dev/null || true
iptables -t mangle -A PREROUTING -i $CLIENT_IF -j AMNEZIA_PREROUTING

iptables -t mangle -A AMNEZIA_PREROUTING -m set --match-set custom_vpn dst -j MARK --set-mark $FWMARK
iptables -t mangle -A AMNEZIA_PREROUTING -m set --match-set custom_vpn dst -j RETURN
iptables -t mangle -A AMNEZIA_PREROUTING -m set --match-set custom_direct dst -j RETURN
iptables -t mangle -A AMNEZIA_PREROUTING -m set --match-set ru_ips dst -j RETURN
iptables -t mangle -A AMNEZIA_PREROUTING -j MARK --set-mark $FWMARK

iptables -t nat -D POSTROUTING -o $TUNNEL_IF -j MASQUERADE 2>/dev/null || true
iptables -t nat -A POSTROUTING -o $TUNNEL_IF -j MASQUERADE
iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE 2>/dev/null || true
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

iptables -A FORWARD -i $CLIENT_IF -j ACCEPT
iptables -A FORWARD -o $CLIENT_IF -j ACCEPT

echo "Split-tunneling configured!"
ROUTING_SCRIPT
chmod +x /usr/local/bin/setup_routing.sh

/usr/local/bin/update_ru_ips.sh

# Firewall
echo -e "${CYAN}[RU] Configuring firewall...${NC}"
ufw --force reset > /dev/null
ufw allow 22/tcp > /dev/null
ufw allow 80/tcp > /dev/null
ufw allow 443/tcp > /dev/null
ufw allow 8080/tcp > /dev/null
ufw allow 8443/tcp > /dev/null
ufw allow 8000/tcp > /dev/null
ufw allow ${VPN_PORT}/udp > /dev/null
sed -i 's/DEFAULT_FORWARD_POLICY="DROP"/DEFAULT_FORWARD_POLICY="ACCEPT"/' /etc/default/ufw
ufw --force enable > /dev/null

# Start AmneziaWG
echo -e "${CYAN}[RU] Starting AmneziaWG...${NC}"
awg-quick down awg0 2>/dev/null || true
awg-quick up awg0
awg-quick down awg-client 2>/dev/null || true
awg-quick up awg-client

/usr/local/bin/setup_routing.sh

# Test tunnel
sleep 2
if ping -c 3 10.200.0.1 > /dev/null 2>&1; then
    echo -e "${GREEN}[RU] ✓ Tunnel to DE is working!${NC}"
else
    echo -e "${RED}[RU] ✗ Tunnel test failed${NC}"
fi

# Clone KrotVPN
echo -e "${CYAN}[RU] Cloning KrotVPN...${NC}"
cd /opt
if [ -d "KrotVPN" ]; then
    cd KrotVPN && git pull
else
    git clone https://github.com/anyagixx/KrotVPN.git
    cd KrotVPN
fi

# Generate SSL
echo -e "${CYAN}[RU] Generating SSL certificate...${NC}"
mkdir -p /opt/KrotVPN/ssl
cd /opt/KrotVPN/ssl
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout server.key -out server.crt \
    -subj "/C=RU/ST=Moscow/L=Moscow/O=KrotVPN/OU=IT/CN=krotvpn.local" 2>/dev/null
chmod 600 server.key
chmod 644 server.crt

# Generate .env
echo -e "${CYAN}[RU] Creating configuration...${NC}"
cd /opt/KrotVPN
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
DATA_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")

cat > .env << EOF
# === APPLICATION ===
APP_NAME=KrotVPN
APP_VERSION=2.1.3
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
DB_USER=krotvpn
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=krotvpn
DATABASE_URL=postgresql+asyncpg://krotvpn:${DB_PASSWORD}@db:5432/krotvpn

# === REDIS ===
REDIS_URL=redis://redis:6379/0

# === CORS ===
CORS_ORIGINS=["https://${RU_IP}","http://${RU_IP}","http://localhost"]

# === ADMIN ===
ADMIN_EMAIL=admin@krotvpn.com
ADMIN_PASSWORD=ChangeMeImmediately123!

# === VPN CONFIGURATION ===
VPN_SUBNET=10.10.0.0/24
VPN_PORT=${VPN_PORT}
VPN_DNS=8.8.8.8, 1.1.1.1
VPN_MTU=1360
VPN_SERVER_PUBLIC_KEY=${RU_SERVER_PUBLIC}
VPN_SERVER_ENDPOINT=${RU_IP}

# === AMNEZIAWG OBFUSCATION ===
AWG_JC=120
AWG_JMIN=50
AWG_JMAX=1000
AWG_S1=111
AWG_S2=222
AWG_H1=1
AWG_H2=2
AWG_H3=3
AWG_H4=4

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
EMAIL_FROM=noreply@krotvpn.com

# === REFERRAL ===
REFERRAL_BONUS_DAYS=7
REFERRAL_MIN_PAYMENT=100.0

# === DOMAIN ===
DOMAIN=${RU_IP}
EOF

chmod 600 .env

# Systemd services
cat > /etc/systemd/system/krotvpn-routing.service << 'SERVICE'
[Unit]
Description=KrotVPN Split-Tunneling Routing
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/setup_routing.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
SERVICE

cat > /etc/systemd/system/krotvpn-ru-ips.service << 'SERVICE'
[Unit]
Description=KrotVPN RU IPset Update
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/update_ru_ips.sh

[Install]
WantedBy=multi-user.target
SERVICE

cat > /etc/systemd/system/krotvpn-ru-ips.timer << 'TIMER'
[Unit]
Description=Daily RU IPset Update

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
TIMER

systemctl daemon-reload
systemctl enable krotvpn-routing krotvpn-ru-ips.timer
systemctl start krotvpn-routing

# Docker
echo -e "${CYAN}[RU] Building and starting Docker containers...${NC}"
docker compose up -d --build

echo ""
echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}        DEPLOYMENT COMPLETE!${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Frontend:    https://${RU_IP}"
echo -e "  Admin Panel: https://${RU_IP}:8443"
echo -e "  Backend API: https://${RU_IP}:8000"
REMOTE_DEPLOY
}

# Final message
show_complete() {
    print_step "Installation Complete!"
    
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║              🎉 KrotVPN is now installed! 🎉                ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo -e "${CYAN}Access your VPN service:${NC}"
    echo ""
    echo -e "  ${GREEN}Frontend:${NC}    https://${RU_IP}"
    echo -e "  ${GREEN}Admin Panel:${NC} https://${RU_IP}:8443"
    echo -e "  ${GREEN}Backend API:${NC} https://${RU_IP}:8000"
    echo ""
    echo -e "${YELLOW}Note: Your browser will warn about self-signed certificate.${NC}"
    echo -e "${YELLOW}Click 'Advanced' → 'Proceed' to continue.${NC}"
    echo ""
    echo -e "${CYAN}Create VPN client:${NC}"
    echo ""
    echo -e "  ssh root@${RU_IP} \"/opt/KrotVPN/deploy/create-client.sh my_client\""
    echo ""
    echo -e "${CYAN}Configure in /opt/KrotVPN/.env:${NC}"
    echo ""
    echo -e "  • YOOKASSA_SHOP_ID     - for payments"
    echo -e "  • YOOKASSA_SECRET_KEY  - for payments"
    echo -e "  • TELEGRAM_BOT_TOKEN   - for Telegram bot"
    echo -e "  • ADMIN_PASSWORD       - ${RED}change default!${NC}"
    echo ""
}

# Main
main() {
    print_banner
    check_prerequisites
    get_server_info
    get_credentials
    deploy
    show_complete
}

main "$@"
