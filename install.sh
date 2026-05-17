#!/bin/bash
#
# KrotPN Interactive Installer v2.9.0
# Run this command to install:
#   curl -fsSL https://raw.githubusercontent.com/anyagixx/KrotPN/main/install.sh | bash
# FILE: install.sh
# VERSION: 2.9.0
# ROLE: SCRIPT
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Interactive KrotPN bootstrap helper for collecting operator deployment inputs.
#   SCOPE: Local prerequisites, RU/DE SSH credentials, admin credentials, Phase-35 wildcard TLS inputs, and remote deploy launch.
#   DEPENDS: M-012, M-048
#   LINKS: docs/modules/M-012.xml, docs/modules/M-048.xml, docs/plans/Phase-35.xml, docs/verification/V-M-048.xml
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   ask/ask_password/ask_yesno - Safe interactive input helpers.
#   validate_public_domain - Reject unsafe public-domain input before remote command construction.
#   validate_tls_path - Reject unsafe certificate file paths before remote command construction.
#   validate_remote_tls_files - Verify prepared wildcard TLS files on the RU server.
#   get_tls_config - Collect Phase-35 public domain and wildcard certificate paths.
#   deploy - Materialize temporary deploy config on RU and run deploy/deploy-on-server.sh.
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.9.0 - Added Phase-35 operator-provided wildcard TLS prompts and remote preflight.
# END_CHANGE_SUMMARY
#
# GRACE-lite operational contract:
# - This script is an interactive bootstrap helper, not a hardened deployment system.
# - It supports both password-based and key-based SSH authentication.
# - Server IPs are provided interactively and never hardcoded.
# - Agents changing this file must review secrets handling, host trust assumptions and cleanup behavior.
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

DEFAULT_PUBLIC_DOMAIN="krotpn.xyz"
DEFAULT_TLS_FULLCHAIN_PATH="/root/krotpn-ssl/fullchain1.pem"
DEFAULT_TLS_PRIVKEY_PATH="/root/krotpn-ssl/privkey1.pem"

print_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║                         K R O T V P N                        ║"
    echo "║                                                              ║"
    echo "║              Interactive Installer v2.9.0                   ║"
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
print_info() { echo -e "${BLUE}ℹ $1${NC}"; }

# SSH helper — uses sshpass if password is set, otherwise key-based
ssh_cmd() {
    local user="$1"
    local host="$2"
    shift 2
    if [ -n "$SSH_PASS" ]; then
        sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -o LogLevel=ERROR "$user@$host" "$@"
    else
        ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -o LogLevel=ERROR "$user@$host" "$@"
    fi
}

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
    
    # Safe assignment without eval
    case "$var" in
        RU_IP) RU_IP="$value" ;;
        DE_IP) DE_IP="$value" ;;
        RU_USER) RU_USER="$value" ;;
        DE_USER) DE_USER="$value" ;;
        ADMIN_EMAIL) ADMIN_EMAIL="$value" ;;
        PUBLIC_DOMAIN) PUBLIC_DOMAIN="$value" ;;
        TLS_FULLCHAIN_PATH) TLS_FULLCHAIN_PATH="$value" ;;
        TLS_PRIVKEY_PATH) TLS_PRIVKEY_PATH="$value" ;;
        CONFIRM) CONFIRM="$value" ;;
        START) START="$value" ;;
        *) print_error "Unknown variable: $var"; exit 1 ;;
    esac
}

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
    
    # Safe assignment without eval
    case "$var" in
        ADMIN_PASSWORD) ADMIN_PASSWORD="$password" ;;
        ADMIN_PASSWORD_CONFIRM) ADMIN_PASSWORD_CONFIRM="$password" ;;
        RU_PASS) RU_PASS="$password" ;;
        DE_PASS) DE_PASS="$password" ;;
        *) print_error "Unknown variable: $var"; exit 1 ;;
    esac
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
    
    local result="n"
    if [ "$value" = "y" ] || [ "$value" = "yes" ]; then
        result="y"
    fi
    
    case "$var" in
        CONFIRM) CONFIRM="$result" ;;
        START) START="$result" ;;
        *) print_error "Unknown variable: $var"; exit 1 ;;
    esac
}

validate_public_domain() {
    local domain="$1"

    if [ -z "$domain" ]; then
        print_error "Public domain is required"
        return 1
    fi

    if [[ "$domain" == http://* ]] || [[ "$domain" == https://* ]] || [[ "$domain" == */* ]]; then
        print_error "Enter only the domain name, for example krotpn.xyz"
        return 1
    fi

    if [[ ! "$domain" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$ ]]; then
        print_error "Invalid domain format: $domain"
        return 1
    fi

    return 0
}

validate_tls_path() {
    local path="$1"
    local label="$2"

    if [ -z "$path" ]; then
        print_error "$label path is required"
        return 1
    fi

    if [[ "$path" != /* ]]; then
        print_error "$label path must be absolute, for example /root/krotpn-ssl/fullchain1.pem"
        return 1
    fi

    if [[ ! "$path" =~ ^/[A-Za-z0-9._/@:+-]+$ ]]; then
        print_error "$label path contains unsupported characters"
        return 1
    fi

    return 0
}

validate_remote_tls_files() {
    print_info "[M-048][installer_tls][VALIDATE_CERT_PATHS] Validating wildcard TLS files on RU server..."

    if sshpass -p "$RU_PASS" ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -o LogLevel=ERROR "$RU_USER@$RU_IP" \
        "bash -s -- '$PUBLIC_DOMAIN' '$TLS_FULLCHAIN_PATH' '$TLS_PRIVKEY_PATH'" <<'REMOTE_TLS'
set -e

domain="$1"
fullchain_path="$2"
privkey_path="$3"
wildcard_domain="*.${domain}"

fail() {
    echo "[M-048][installer_tls][ABORT_BEFORE_DEPLOY] $1" >&2
    exit 1
}

for path in "$fullchain_path" "$privkey_path"; do
    [ -f "$path" ] || fail "Missing TLS file: $path"
    [ -r "$path" ] || fail "TLS file is not readable: $path"
    [ -s "$path" ] || fail "TLS file is empty: $path"
done

command -v openssl >/dev/null 2>&1 || fail "openssl is required on the RU server for TLS validation"

openssl x509 -in "$fullchain_path" -noout >/dev/null 2>&1 || fail "fullchain is not a readable X.509 certificate"
openssl pkey -in "$privkey_path" -noout >/dev/null 2>&1 || fail "private key is not readable by openssl"

if ! openssl x509 -in "$fullchain_path" -checkend 86400 -noout >/dev/null 2>&1; then
    fail "certificate is expired or expires in less than 24 hours"
fi

cert_pub_hash="$(openssl x509 -in "$fullchain_path" -pubkey -noout 2>/dev/null | openssl pkey -pubin -outform der 2>/dev/null | openssl dgst -sha256 2>/dev/null | awk '{print $2}')"
key_pub_hash="$(openssl pkey -in "$privkey_path" -pubout -outform der 2>/dev/null | openssl dgst -sha256 2>/dev/null | awk '{print $2}')"
[ -n "$cert_pub_hash" ] || fail "could not derive certificate public key fingerprint"
[ -n "$key_pub_hash" ] || fail "could not derive private key public fingerprint"
[ "$cert_pub_hash" = "$key_pub_hash" ] || fail "certificate and private key do not match"
echo "[M-048][installer_tls][VALIDATE_CERT_KEY_MATCH] certificate and private key match"

san_text="$(openssl x509 -in "$fullchain_path" -noout -ext subjectAltName 2>/dev/null || true)"
escaped_domain="$(printf '%s' "$domain" | sed 's/[.[\*^$()+?{}|\\]/\\&/g')"
printf '%s\n' "$san_text" | grep -Eq "DNS:${escaped_domain}([,[:space:]]|$)" || fail "certificate SAN does not include ${domain}"
printf '%s\n' "$san_text" | grep -Eq "DNS:\*\.${escaped_domain}([,[:space:]]|$)" || fail "certificate SAN does not include ${wildcard_domain}"

not_after="$(openssl x509 -in "$fullchain_path" -noout -enddate 2>/dev/null | sed 's/^notAfter=//')"
echo "[M-048][installer_tls][VALIDATE_SAN] wildcard TLS files are valid for ${domain} and ${wildcard_domain}; expires ${not_after}"
REMOTE_TLS
    then
        print_success "Wildcard TLS files validated"
    else
        print_error "Wildcard TLS validation failed. Fix the files on RU server and run install again."
        exit 1
    fi
}

get_tls_config() {
    print_step "Step 4: Domain and wildcard TLS"

    echo -e "${BLUE}Prepare these files on the RU server before deployment:${NC}"
    echo -e "  ${CYAN}${DEFAULT_TLS_FULLCHAIN_PATH}${NC}"
    echo -e "  ${CYAN}${DEFAULT_TLS_PRIVKEY_PATH}${NC}"
    echo ""

    while true; do
        ask "Project public domain" "$DEFAULT_PUBLIC_DOMAIN" PUBLIC_DOMAIN
        PUBLIC_DOMAIN=$(printf '%s' "$PUBLIC_DOMAIN" | tr '[:upper:]' '[:lower:]')
        validate_public_domain "$PUBLIC_DOMAIN" && break
    done

    while true; do
        ask "RU fullchain certificate path" "$DEFAULT_TLS_FULLCHAIN_PATH" TLS_FULLCHAIN_PATH
        validate_tls_path "$TLS_FULLCHAIN_PATH" "Fullchain certificate" && break
    done

    while true; do
        ask "RU private key path" "$DEFAULT_TLS_PRIVKEY_PATH" TLS_PRIVKEY_PATH
        validate_tls_path "$TLS_PRIVKEY_PATH" "Private key" && break
    done

    print_info "[M-048][installer_tls][VALIDATE_INPUTS] Domain and TLS paths accepted"
    validate_remote_tls_files
}

get_admin_config() {
    print_step "Step 5: Admin credentials"

    echo -e "${BLUE}Set production admin credentials for KrotPN:${NC}"
    echo ""

    ask "Admin email" "admin@krotpn.com" ADMIN_EMAIL
    if [ -z "$ADMIN_EMAIL" ]; then
        print_error "Admin email is required"
        exit 1
    fi

    while true; do
        ask_password "Admin password" ADMIN_PASSWORD
        if [ -z "$ADMIN_PASSWORD" ]; then
            print_error "Admin password is required"
            continue
        fi

        if [ "${#ADMIN_PASSWORD}" -lt 12 ]; then
            print_error "Admin password must be at least 12 characters"
            continue
        fi

        ask_password "Confirm admin password" ADMIN_PASSWORD_CONFIRM
        if [ "$ADMIN_PASSWORD" != "$ADMIN_PASSWORD_CONFIRM" ]; then
            print_error "Passwords do not match"
            continue
        fi

        break
    done
}

check_prerequisites() {
    print_step "Step 1: Checking prerequisites"
    
    # Install git if not available
    if ! command -v git &> /dev/null; then
        print_info "git not found — installing..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get update -qq && sudo apt-get install -y -qq git 2>/dev/null
        elif command -v yum &> /dev/null; then
            sudo yum install -y -q git 2>/dev/null
        elif command -v brew &> /dev/null; then
            brew install git 2>/dev/null
        fi
        if command -v git &> /dev/null; then
            print_success "git installed"
        else
            print_error "Failed to install git. Please install it manually."
            exit 1
        fi
    else
        print_success "git available"
    fi
    
    # Install sshpass if not available
    if ! command -v sshpass &> /dev/null; then
        print_info "sshpass not found — installing..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get update -qq && sudo apt-get install -y -qq sshpass 2>/dev/null
        elif command -v yum &> /dev/null; then
            sudo yum install -y -q sshpass 2>/dev/null
        elif command -v brew &> /dev/null; then
            brew install sshpass 2>/dev/null
        fi
        if command -v sshpass &> /dev/null; then
            print_success "sshpass installed"
        else
            print_error "Failed to install sshpass. Please install it manually."
            exit 1
        fi
    else
        print_success "sshpass available"
    fi
    
    if command -v ssh &> /dev/null; then
        print_success "SSH client available"
    else
        print_error "SSH client not found"
        exit 1
    fi
}

get_server_info() {
    print_step "Step 2: Server configuration"
    
    echo -e "${BLUE}KrotPN requires two servers:${NC}"
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

get_ssh_credentials() {
    print_step "Step 3: SSH credentials"
    
    echo -e "${BLUE}Enter SSH credentials for both servers:${NC}"
    echo ""
    
    echo -e "${CYAN}RU Server (${RU_IP}):${NC}"
    ask "  SSH username" "root" RU_USER
    ask_password "  SSH password" RU_PASS
    echo ""
    
    echo -e "${CYAN}DE Server (${DE_IP}):${NC}"
    ask "  SSH username" "root" DE_USER
    ask_password "  SSH password" DE_PASS
    echo ""
    
    # Test RU connection
    print_info "Testing SSH connection to RU server..."
    if sshpass -p "$RU_PASS" ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -o LogLevel=ERROR "$RU_USER@$RU_IP" "echo ok" 2>/dev/null | grep -q "ok"; then
        print_success "RU server connection OK"
    else
        print_error "Cannot connect to RU server. Check IP, username, and password."
        exit 1
    fi
    
    # Test DE connection
    print_info "Testing SSH connection to DE server..."
    if sshpass -p "$DE_PASS" ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -o LogLevel=ERROR "$DE_USER@$DE_IP" "echo ok" 2>/dev/null | grep -q "ok"; then
        print_success "DE server connection OK"
    else
        print_error "Cannot connect to DE server. Check IP, username, and password."
        exit 1
    fi
}

deploy() {
    print_step "Step 6: Starting deployment"
    
    echo -e "${BLUE}This will:${NC}"
    echo -e "  1. Clone KrotPN on RU server"
    echo -e "  2. Install dependencies on both servers"
    echo -e "  3. Configure AmneziaWG VPN tunnel"
    echo -e "  4. Start Docker containers with HTTPS"
    echo ""
    
    ask_yesno "Start deployment?" "y" START
    if [ "$START" != "y" ]; then
        print_error "Deployment cancelled"
        exit 1
    fi
    
    print_info "Deploying... This will take 10-15 minutes."
    echo ""
    
    # Create config file on RU server with passwords for deploy script
    print_info "Creating configuration on RU server..."
    sshpass -p "$RU_PASS" ssh -o StrictHostKeyChecking=accept-new "$RU_USER@$RU_IP" "umask 077 && cat > /tmp/krotpn_deploy.conf" << EOF
DE_IP='${DE_IP}'
DE_USER='${DE_USER}'
DE_PASS='${DE_PASS}'
RU_IP='${RU_IP}'
RU_USER='${RU_USER}'
RU_PASS='${RU_PASS}'
ADMIN_EMAIL='${ADMIN_EMAIL}'
ADMIN_PASSWORD='${ADMIN_PASSWORD}'
PUBLIC_DOMAIN='${PUBLIC_DOMAIN}'
TLS_FULLCHAIN_PATH='${TLS_FULLCHAIN_PATH}'
TLS_PRIVKEY_PATH='${TLS_PRIVKEY_PATH}'
TLS_CERTIFICATE_MODE='operator-wildcard'
VPN_CLIENT_SUBNET='${VPN_CLIENT_SUBNET:-}'
VPN_CLIENT_GATEWAY='${VPN_CLIENT_GATEWAY:-}'
VPN_RELAY_SUBNET='${VPN_RELAY_SUBNET:-}'
VPN_RELAY_DE_ADDRESS='${VPN_RELAY_DE_ADDRESS:-}'
VPN_RELAY_RU_ADDRESS='${VPN_RELAY_RU_ADDRESS:-}'
VPN_CAPACITY_PROFILE='${VPN_CAPACITY_PROFILE:-}'
VPN_NETWORK_ROTATE='${VPN_NETWORK_ROTATE:-0}'
EOF
    
    if [ $? -ne 0 ]; then
        print_error "Failed to create config file"
        exit 1
    fi
    print_success "Config created"
    
    # Clone repository
    print_info "Cloning KrotPN repository..."
    sshpass -p "$RU_PASS" ssh -o StrictHostKeyChecking=accept-new "$RU_USER@$RU_IP" "
        # Install git if not available
        if ! command -v git &> /dev/null; then
            echo 'Installing git...'
            apt-get update
            apt-get install -y git
        fi
        cd /opt
        rm -rf KrotPN 2>/dev/null || true
        git clone https://github.com/anyagixx/KrotPN.git KrotPN
        chmod +x /opt/KrotPN/deploy/*.sh
    "
    
    if [ $? -ne 0 ]; then
        print_error "Failed to clone repository"
        exit 1
    fi
    print_success "Repository cloned"
    
    # Run deployment script
    print_info "Running deployment script on RU server..."
    echo ""
    
    sshpass -p "$RU_PASS" ssh -o StrictHostKeyChecking=accept-new -t "$RU_USER@$RU_IP" "cd /opt/KrotPN && ./deploy/deploy-on-server.sh"
}

show_complete() {
    print_step "Installation Complete!"
    
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║              KrotPN is now installed!                      ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo -e "${CYAN}Access your VPN service:${NC}"
    echo ""
    echo -e "  ${GREEN}Frontend:${NC}    https://${PUBLIC_DOMAIN}"
    echo -e "  ${GREEN}Admin Panel:${NC} https://${PUBLIC_DOMAIN}:8443"
    echo -e "  ${GREEN}Backend API:${NC} https://${PUBLIC_DOMAIN} (via nginx)"
    echo ""
    echo -e "${GREEN}Wildcard TLS certificate was provided by operator and reused by the project.${NC}"
    echo ""
    echo -e "${CYAN}Create VPN client:${NC}"
    echo ""
    echo -e "  ssh root@${RU_IP} \"/opt/KrotPN/deploy/create-client.sh my_client\""
    echo ""
    echo -e "${CYAN}Configured during install:${NC}"
    echo ""
    echo -e "  • ADMIN_EMAIL         - ${GREEN}${ADMIN_EMAIL}${NC}"
    echo -e "  • ADMIN_PASSWORD      - password entered during installation"
    echo -e "  • PUBLIC_DOMAIN       - ${GREEN}${PUBLIC_DOMAIN}${NC}"
    echo -e "  • TLS_FULLCHAIN_PATH  - ${GREEN}${TLS_FULLCHAIN_PATH}${NC}"
    echo -e "  • TLS_PRIVKEY_PATH    - private key path entered during installation"
    echo ""
    echo -e "${CYAN}Configure later in /opt/KrotPN/.env:${NC}"
    echo ""
    echo -e "  • YOOKASSA_SHOP_ID    - for payments"
    echo -e "  • YOOKASSA_SECRET_KEY - for payments"
    echo -e "  • TELEGRAM_BOT_TOKEN  - for Telegram bot"
    echo ""
}

main() {
    print_banner
    check_prerequisites
    get_server_info
    get_ssh_credentials
    get_tls_config
    get_admin_config
    deploy
    show_complete
}

main "$@"
