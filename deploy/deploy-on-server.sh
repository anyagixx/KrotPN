#!/bin/bash
#
# KrotPN Server Deployment Script v3.0.0 (Full Tunnel)
# Run this script ON the RU server
# GRACE-lite operational contract:
# - This script is executed on the RU host and consumes temporary config from /tmp/krotpn_deploy.conf.
# - It decodes remote credentials, provisions RU host services and reaches the DE host over SSH.
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

VPN_PORT="${VPN_PORT:-443}"

cleanup_sensitive_files() {
    rm -f /tmp/krotpn_deploy.conf /tmp/de_setup.sh
}

trap cleanup_sensitive_files EXIT

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${RED}[ERROR] Required command not found: ${cmd}${NC}"
        exit 1
    fi
}

# Install sshpass if not available (needed for password-based DE auth)
if ! command -v sshpass &> /dev/null; then
    echo -e "${BLUE}[INSTALL] Installing sshpass...${NC}"
    apt-get update -qq && apt-get install -y -qq sshpass 2>/dev/null
    if command -v sshpass &> /dev/null; then
        echo -e "${GREEN}✓ sshpass installed${NC}"
    else
        echo -e "${RED}[ERROR] Failed to install sshpass${NC}"
        exit 1
    fi
fi

# SSH wrapper for DE server (password-based auth)
ssh_de() {
    sshpass -p "$DE_PASS" ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=30 -o LogLevel=ERROR "$DE_USER@$DE_IP" "$@"
}

# SCP wrapper for DE server (password-based auth)
scp_de() {
    sshpass -p "$DE_PASS" scp -o StrictHostKeyChecking=accept-new -o LogLevel=ERROR "$@" "$DE_USER@$DE_IP:$2"
}

# Read configuration from file
if [ -f /tmp/krotpn_deploy.conf ]; then
    echo -e "${BLUE}[CONFIG] Loading configuration from file...${NC}"
    source /tmp/krotpn_deploy.conf
else
    echo -e "${RED}[ERROR] Configuration file not found: /tmp/krotpn_deploy.conf${NC}"
    echo "Please run install.sh first"
    exit 1
fi

ADMIN_EMAIL="${ADMIN_EMAIL:-admin@krotpn.com}"
if [ -z "$ADMIN_PASSWORD" ]; then
    ADMIN_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
    GENERATED_ADMIN_PASSWORD=1
else
    GENERATED_ADMIN_PASSWORD=0
fi

# Validate required variables
if [ -z "$DE_IP" ] || [ -z "$DE_USER" ]; then
    echo -e "${RED}[ERROR] Missing required configuration${NC}"
    echo "Required: DE_IP, DE_USER"
    exit 1
fi

# Get RU IPv4 address (force IPv4, multiple fallbacks)
echo -e "${BLUE}[DETECT] Getting RU server IPv4 address...${NC}"
RU_IP=$(curl -4 -s --connect-timeout 5 https://api4.ipify.org 2>/dev/null || \
        curl -4 -s --connect-timeout 5 https://ipv4.icanhazip.com 2>/dev/null || \
        curl -4 -s --connect-timeout 5 https://v4.ident.me 2>/dev/null || \
        ip -4 addr show | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '127.0.0.1' | head -1)

if [ -z "$RU_IP" ] || [[ "$RU_IP" == *":"* ]]; then
    echo -e "${RED}[ERROR] Could not detect IPv4 address${NC}"
    exit 1
fi
echo -e "${GREEN}[OK] RU IPv4: ${RU_IP}${NC}"

# Print banner
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║           KrotPN Automated Deployment v3.0.0               ║${NC}"
echo -e "${CYAN}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${CYAN}║  RU Server (Entry): ${RU_IP}                            ║${NC}"
echo -e "${CYAN}║  DE Server (Exit):  ${DE_IP}                            ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Test connection to DE
echo -e "${BLUE}[CHECK] Testing connection to DE server...${NC}"
if ssh_de "echo ok" 2>/dev/null | grep -q "ok"; then
    echo -e "${GREEN}✓ DE server accessible${NC}"
else
    echo -e "${RED}✗ Cannot connect to DE server${NC}"
    echo -e "${YELLOW}  Check that DE server is reachable and SSH keys are configured${NC}"
    exit 1
fi
echo ""

# ============================================================
# PHASE 1: Setup RU Server
# ============================================================
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}PHASE 1: RU Server - Installing dependencies${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo ""

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
echo -e "${GREEN}✓ Docker installed${NC}"

echo -e "${BLUE}[RU] Installing AmneziaWG...${NC}"
if ! command -v awg &> /dev/null; then
    add-apt-repository ppa:amnezia/ppa -y
    apt update -qq
    apt install -y -qq amneziawg amneziawg-tools
fi
awg_configure_userspace
echo -e "${GREEN}✓ AmneziaWG installed${NC}"

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
RU_SERVER_PRIVATE=$(cat ru_server_private.key)
RU_CLIENT_PUBLIC=$(cat ru_client_public.key)
RU_CLIENT_PRIVATE=$(cat ru_client_private.key)

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

echo -e "${GREEN}✓ Keys generated${NC}"
echo -e "  Server Public: ${RU_SERVER_PUBLIC}"
echo -e "  Client Public: ${RU_CLIENT_PUBLIC}"
echo -e "  Private keys stored on disk with root-only permissions"
echo ""

# ============================================================
# PHASE 2: Setup DE Server
# ============================================================
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}PHASE 2: DE Server - Installation${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo ""

# Create script for DE server
cat > /tmp/de_setup.sh << 'DESCRIPT'
#!/bin/bash
set -e

RU_CLIENT_PUBLIC="$1"
VPN_PORT="$2"
DE_IP="$3"
RELAY_JC="$4"
RELAY_JMIN="$5"
RELAY_JMAX="$6"
RELAY_S1="$7"
RELAY_S2="$8"
RELAY_H1="$9"
RELAY_H2="${10}"
RELAY_H3="${11}"
RELAY_H4="${12}"

source /tmp/krotpn-awg-obfuscation.sh
source /tmp/krotpn-vpn-network.sh

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${RED}[ERROR] Required command not found: ${cmd}${NC}"
        exit 1
    fi
}

verify_host_routing_tools() {
    local tools=(ip iptables awg awg-quick curl grep)
    for tool in "${tools[@]}"; do
        require_command "$tool"
    done
    echo -e "${GREEN}✓ DE host routing toolchain verified${NC}"
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
echo -e "${GREEN}✓ AmneziaWG installed${NC}"
verify_host_routing_tools

echo -e "${BLUE}[DE] Enabling IP forwarding...${NC}"
echo "net.ipv4.ip_forward=1" > /etc/sysctl.d/99-krotpn.conf
sysctl -p /etc/sysctl.d/99-krotpn.conf > /dev/null

echo -e "${BLUE}[DE] Generating keys...${NC}"
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

echo -e "${GREEN}✓ Keys generated${NC}"
echo -e "  DE Public: ${DE_PUBLIC}"

echo -e "${BLUE}[DE] Creating AmneziaWG config...${NC}"
cat > /etc/amnezia/amneziawg/awg0.conf << EOF
[Interface]
PrivateKey = ${DE_PRIVATE}
Address = ${VPN_RELAY_DE_CIDR}
ListenPort = ${VPN_PORT}
$(awg_profile_lines RELAY_)

[Peer]
PublicKey = ${RU_CLIENT_PUBLIC}
AllowedIPs = ${VPN_RELAY_RU_ALLOWED_IP}
EOF

chmod 600 /etc/amnezia/amneziawg/awg0.conf
echo -e "${GREEN}✓ Config created${NC}"

echo -e "${BLUE}[DE] Configuring firewall...${NC}"
ufw --force reset > /dev/null 2>&1
ufw default allow FORWARD > /dev/null 2>&1
ufw allow 22/tcp > /dev/null 2>&1
ufw allow ${VPN_PORT}/udp > /dev/null 2>&1
ufw allow in on awg0 > /dev/null 2>&1
ufw allow out on awg0 > /dev/null 2>&1
ufw --force enable > /dev/null 2>&1

# Add FORWARD rules for tunnel traffic
iptables -D FORWARD -i awg0 -o eth0 -j ACCEPT 2>/dev/null || true
iptables -D FORWARD -i eth0 -o awg0 -j ACCEPT 2>/dev/null || true
iptables -I FORWARD 1 -i awg0 -o eth0 -j ACCEPT
iptables -I FORWARD 2 -i eth0 -o awg0 -j ACCEPT

# NAT rule for both relay and client traffic
EXT_IF=$(ip route | grep default | awk '{print $5}' | head -1)
iptables -t nat -C POSTROUTING -s ${VPN_RELAY_SUBNET} -o $EXT_IF -j MASQUERADE 2>/dev/null || \
    iptables -t nat -A POSTROUTING -s ${VPN_RELAY_SUBNET} -o $EXT_IF -j MASQUERADE
iptables -t nat -C POSTROUTING -s ${VPN_CLIENT_SUBNET} -o $EXT_IF -j MASQUERADE 2>/dev/null || \
    iptables -t nat -A POSTROUTING -s ${VPN_CLIENT_SUBNET} -o $EXT_IF -j MASQUERADE

mkdir -p /etc/iptables
iptables-save > /etc/iptables/rules.v4
awg_apply_host_hardening "${VPN_PORT}"

echo -e "${GREEN}✓ Firewall configured${NC}"

echo -e "${BLUE}[DE] Starting AmneziaWG...${NC}"
awg-quick down awg0 2>/dev/null || true
awg-quick up awg0

sleep 1
if ip link show awg0 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ AmneziaWG interface awg0 is UP${NC}"
    awg show
else
    echo -e "${RED}✗ AmneziaWG failed to start!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ DE server ready!${NC}"
DESCRIPT

chmod +x /tmp/de_setup.sh

# Copy and run on DE server
echo -e "${BLUE}[RU] Copying setup script to DE server...${NC}"
sshpass -p "$DE_PASS" scp -o StrictHostKeyChecking=accept-new -o LogLevel=ERROR /tmp/de_setup.sh "$DE_USER@$DE_IP:/tmp/"
sshpass -p "$DE_PASS" scp -o StrictHostKeyChecking=accept-new -o LogLevel=ERROR "${SCRIPT_DIR}/lib/awg-obfuscation.sh" "$DE_USER@$DE_IP:/tmp/krotpn-awg-obfuscation.sh"
sshpass -p "$DE_PASS" scp -o StrictHostKeyChecking=accept-new -o LogLevel=ERROR "${SCRIPT_DIR}/lib/vpn-network.sh" "$DE_USER@$DE_IP:/tmp/krotpn-vpn-network.sh"

echo -e "${BLUE}[RU] Running setup on DE server...${NC}"
ssh_de "STEALTH_ROTATE='${STEALTH_ROTATE:-0}' VPN_CLIENT_SUBNET='${VPN_CLIENT_SUBNET}' VPN_CLIENT_GATEWAY='${VPN_CLIENT_GATEWAY}' VPN_RELAY_SUBNET='${VPN_RELAY_SUBNET}' VPN_RELAY_DE_ADDRESS='${VPN_RELAY_DE_ADDRESS}' VPN_RELAY_RU_ADDRESS='${VPN_RELAY_RU_ADDRESS}' VPN_CAPACITY_PROFILE='${VPN_CAPACITY_PROFILE}' VPN_NETWORK_ROTATE='${VPN_NETWORK_ROTATE}' VPN_NETWORK_PRESERVED='${VPN_NETWORK_PRESERVED:-0}' bash /tmp/de_setup.sh '$RU_CLIENT_PUBLIC' '$VPN_PORT' '$DE_IP'$(awg_profile_args RELAY_)"

# Get DE public key
DE_PUBLIC_KEY=$(ssh_de "cat /etc/amnezia/amneziawg/de_public.key")
echo -e "${GREEN}✓ Got DE public key: ${DE_PUBLIC_KEY}${NC}"

# Verify DE AmneziaWG is accessible
echo -e "${BLUE}[RU] Verifying DE AmneziaWG status...${NC}"
DE_AWG_STATUS=$(ssh_de "awg show 2>/dev/null || echo 'FAILED'")
if echo "$DE_AWG_STATUS" | grep -q "peer"; then
    echo -e "${GREEN}✓ DE AmneziaWG is running${NC}"
else
    echo -e "${RED}✗ DE AmneziaWG is NOT running properly${NC}"
    echo "$DE_AWG_STATUS"
fi
echo ""

# ============================================================
# PHASE 3: Complete RU Setup
# ============================================================
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}PHASE 3: RU Server - Completing setup${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo ""

cd /etc/amnezia/amneziawg

echo -e "${BLUE}[RU] Creating tunnel config to DE...${NC}"
cat > awg-client.conf << EOF
[Interface]
PrivateKey = ${RU_CLIENT_PRIVATE}
Address = ${VPN_RELAY_RU_CIDR}
Table = off
$(awg_profile_lines RELAY_)

[Peer]
PublicKey = ${DE_PUBLIC_KEY}
Endpoint = ${DE_IP}:${VPN_PORT}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
EOF

echo -e "${BLUE}[RU] Creating VPN server config...${NC}"
cat > awg0.conf << EOF
[Interface]
PrivateKey = ${RU_SERVER_PRIVATE}
Address = ${VPN_CLIENT_INTERFACE_CIDR}
ListenPort = ${VPN_PORT}
$(awg_profile_lines CLIENT_)
EOF

chmod 600 *.conf
echo -e "${GREEN}✓ Configs created${NC}"

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

# Firewall
echo -e "${BLUE}[RU] Configuring firewall...${NC}"
ufw --force reset > /dev/null
ufw allow 22/tcp > /dev/null
ufw allow 80/tcp > /dev/null
ufw allow 443/tcp > /dev/null
ufw allow 8080/tcp > /dev/null
ufw allow 8443/tcp > /dev/null
ufw allow 8000/tcp > /dev/null
ufw allow ${VPN_PORT}/udp > /dev/null
ufw default allow FORWARD > /dev/null
ufw allow in on awg0 > /dev/null
ufw allow out on awg0 > /dev/null
ufw allow in on awg-client > /dev/null
ufw allow out on awg-client > /dev/null
ufw --force enable > /dev/null
awg_apply_host_hardening "${VPN_PORT}"
echo -e "${GREEN}✓ Firewall configured${NC}"

# Add explicit route to DE server via main gateway (prevent SSH hang)
echo -e "${BLUE}[RU] Adding route to DE server via main gateway...${NC}"
DE_GW=$(ip route | grep default | awk '{print $3}' | head -1)
if [ -n "$DE_GW" ]; then
    ip route add ${DE_IP}/32 via ${DE_GW} 2>/dev/null || true
    echo -e "${GREEN}✓ Route to DE added via ${DE_GW}${NC}"
else
    echo -e "${YELLOW}Warning: Could not detect default gateway${NC}"
fi

# Start AmneziaWG
echo -e "${BLUE}[RU] Starting AmneziaWG...${NC}"
awg-quick down awg0 2>/dev/null || true
awg-quick up awg0
systemctl enable awg-quick@awg0 >/dev/null 2>&1 || true
awg-quick down awg-client 2>/dev/null || true
awg-quick up awg-client
systemctl enable awg-quick@awg-client >/dev/null 2>&1 || true

# Route to tunnel subnet
echo -e "${BLUE}[RU] Adding route to DE tunnel subnet...${NC}"
ip route add ${VPN_RELAY_SUBNET} dev awg-client 2>/dev/null || true
echo -e "${GREEN}✓ Route to ${VPN_RELAY_SUBNET} added${NC}"

# Show routing table for debugging
echo -e "${BLUE}[RU] Current routes to DE tunnel:${NC}"
ip route show | grep -E "(awg-client|${VPN_RELAY_SUBNET%%/*})" || echo "No routes found"

# Verify awg-client is up
echo -e "${BLUE}[RU] Verifying awg-client interface...${NC}"
if ip link show awg-client > /dev/null 2>&1; then
    echo -e "${GREEN}✓ awg-client interface is UP${NC}"
    ip addr show awg-client | grep inet
else
    echo -e "${RED}✗ awg-client interface is DOWN${NC}"
fi

# Show AmneziaWG status
echo -e "${BLUE}[RU] AmneziaWG status:${NC}"
awg show

# ============================================================
# Full Tunnel: Simple FORWARD rules between awg0 and awg-client
# ============================================================
# All client traffic arriving on awg0 is forwarded
# through the awg-client tunnel to DE. No ipset, no mangle.
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

# Test tunnel - try multiple times
echo -e "${BLUE}[RU] Testing tunnel to DE (${VPN_RELAY_DE_ADDRESS})...${NC}"
TUNNEL_OK=false
for i in 1 2 3 4 5; do
    sleep 2
    if ping -c 2 -W 3 ${VPN_RELAY_DE_ADDRESS} > /dev/null 2>&1; then
        TUNNEL_OK=true
        echo -e "${GREEN}✓ Tunnel to DE is working! (attempt $i)${NC}"
        break
    else
        echo -e "${YELLOW}  Attempt $i failed, retrying...${NC}"
    fi
done

if [ "$TUNNEL_OK" = false ]; then
    echo -e "${RED}✗ Tunnel test failed after 5 attempts${NC}"
    echo -e "${YELLOW}  Debugging info:${NC}"
    echo -e "${YELLOW}  - RU awg-client status:${NC}"
    awg show awg-client 2>/dev/null || echo "    Cannot show awg-client"
    echo -e "${YELLOW}  - Routes:${NC}"
    ip route show | grep -E "(awg|${VPN_RELAY_SUBNET%%/*})" || echo "    No relevant routes"
    echo -e "${YELLOW}  - DE AmneziaWG status:${NC}"
    ssh_de "awg show" 2>/dev/null || echo "    Cannot connect to DE"
fi

# ============================================================
# Policy Routing: Client traffic MUST go through tunnel to DE
# ============================================================
# Without this, client packets from the selected client subnet go to the default
# route (eth0/internet) instead of through awg-client to DE.
# ============================================================

echo -e "${BLUE}[RU] Configuring policy routing for VPN clients...${NC}"

# Create custom routing table if not exists
if ! grep -q "100.*vpnclients" /etc/iproute2/rt_tables 2>/dev/null; then
    echo "100 vpnclients" >> /etc/iproute2/rt_tables
    echo "  Created routing table 'vpnclients' (id 100)"
fi

# Add rule: all packets from client subnet use table 100
ip rule add from ${VPN_CLIENT_SUBNET} lookup 100 2>/dev/null || true
echo "  Added ip rule: from ${VPN_CLIENT_SUBNET} lookup vpnclients"

# Add default route via awg-client in table 100
ip route add default dev awg-client table 100 2>/dev/null || true
echo "  Added default route via awg-client in table vpnclients"

# Persist policy routing across reboots
cat > /etc/network/if-up.d/krotpn-policy-routing << ROUTING_SCRIPT
#!/bin/sh
# Restore VPN client policy routing after interface restart
echo "100 vpnclients" >> /etc/iproute2/rt_tables 2>/dev/null || true
ip rule add from ${VPN_CLIENT_SUBNET} lookup 100 2>/dev/null || true
ip route add default dev awg-client table 100 2>/dev/null || true
ROUTING_SCRIPT
chmod +x /etc/network/if-up.d/krotpn-policy-routing
echo "  ✅ Policy routing persisted across reboots"

# Update KrotPN
echo -e "${BLUE}[RU] Updating KrotPN application...${NC}"
cd /opt/KrotPN
CURRENT_BRANCH=$(git symbolic-ref --short -q HEAD || true)
if [ -n "$CURRENT_BRANCH" ]; then
    git pull --ff-only origin "$CURRENT_BRANCH"
else
    echo -e "${YELLOW}[RU] Detached HEAD detected, skipping git pull${NC}"
fi

# Generate SSL
echo -e "${BLUE}[RU] Generating SSL certificate...${NC}"
mkdir -p /opt/KrotPN/ssl
cd /opt/KrotPN/ssl
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout server.key -out server.crt \
    -subj "/C=RU/ST=Moscow/L=Moscow/O=KrotPN/OU=IT/CN=krotpn.local" 2>/dev/null
chmod 600 server.key
chmod 644 server.crt
echo -e "${GREEN}✓ SSL certificate generated${NC}"

# Generate .env
echo -e "${BLUE}[RU] Creating configuration...${NC}"
cd /opt/KrotPN
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
DATA_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")

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
VPN_SERVER_NAME=RU Entry Node
VPN_SERVER_LOCATION=Russia
VPN_SERVER_MAX_CLIENTS=1000
VPN_ENTRY_SERVER_PUBLIC_KEY=${RU_SERVER_PUBLIC}
VPN_ENTRY_SERVER_ENDPOINT=${RU_IP}
VPN_ENTRY_SERVER_NAME=RU Entry Node
VPN_ENTRY_SERVER_LOCATION=Russia
VPN_ENTRY_SERVER_COUNTRY_CODE=RU
VPN_ENTRY_SERVER_MAX_CLIENTS=1000
VPN_EXIT_SERVER_PUBLIC_KEY=${DE_PUBLIC_KEY}
VPN_EXIT_SERVER_ENDPOINT=${DE_IP}
VPN_EXIT_SERVER_NAME=DE Exit Node
VPN_EXIT_SERVER_LOCATION=Germany
VPN_EXIT_SERVER_COUNTRY_CODE=DE
VPN_EXIT_SERVER_MAX_CLIENTS=1000
VPN_DEFAULT_ROUTE_NAME=RU -> DE

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
echo -e "${GREEN}✓ Configuration created${NC}"
echo -e "${YELLOW}[SECURITY] Admin credentials were displayed during install. Do not reuse.${NC}"

# Create systemd service for awg0 peer sync (only the sync, no routing)
echo -e "${BLUE}[RU] Creating systemd services...${NC}"

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
echo -e "${GREEN}✓ Systemd services created${NC}"

# Docker
echo -e "${BLUE}[RU] Building and starting Docker containers...${NC}"
cd /opt/KrotPN
mkdir -p logs
chown 1000:1000 logs
docker compose up -d --build

echo ""
sleep 5
echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}        DEPLOYMENT COMPLETE!${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Frontend:    ${CYAN}https://${RU_IP}${NC}"
echo -e "  Admin Panel: ${CYAN}https://${RU_IP}:8443${NC}"
echo -e "  Backend API: ${CYAN}https://${RU_IP}:8000${NC}"
echo ""
echo -e "  Create VPN client:"
echo -e "  ${YELLOW}/opt/KrotPN/deploy/create-client.sh my_client${NC}"
echo ""

# Cleanup happens via trap
