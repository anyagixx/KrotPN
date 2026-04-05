#!/bin/bash
#
# KrotVPN Interactive Installer v2.5.0
# Run this command to install:
#   curl -fsSL https://raw.githubusercontent.com/anyagixx/KrotVPN/main/install.sh | bash
# GRACE-lite operational contract:
# - This script is an interactive bootstrap helper, not a hardened deployment system.
# - It requires SSH key-based authentication (no sshpass).
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

print_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║                         K R O T V P N                        ║"
    echo "║                                                              ║"
    echo "║              Interactive Installer v2.5.0                   ║"
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

get_admin_config() {
    print_step "Step 4: Admin credentials"

    echo -e "${BLUE}Set production admin credentials for KrotVPN:${NC}"
    echo ""

    ask "Admin email" "admin@krotvpn.com" ADMIN_EMAIL
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
    
    if ! command -v ssh &> /dev/null; then
        print_error "SSH client not found"
        exit 1
    fi
    print_success "SSH client available"

    # Verify SSH key-based auth is set up
    print_info "Verifying SSH key-based authentication..."
    print_info "Make sure you have added your public key to both servers:"
    print_info "  ssh-copy-id root@<RU_IP>"
    print_info "  ssh-copy-id root@<DE_IP>"
    print_success "SSH key-based auth required (no password auth)"
}

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

get_ssh_users() {
    print_step "Step 3: SSH users"
    
    echo -e "${BLUE}Enter SSH usernames (key-based auth required):${NC}"
    echo ""
    
    echo -e "${CYAN}RU Server (${RU_IP}):${NC}"
    ask "  SSH username" "root" RU_USER
    echo ""
    
    echo -e "${CYAN}DE Server (${DE_IP}):${NC}"
    ask "  SSH username" "root" DE_USER
    echo ""
    
    print_info "Testing SSH key-based connection to RU server..."
    if ssh -o BatchMode=yes -o ConnectTimeout=10 -o LogLevel=ERROR "$RU_USER@$RU_IP" "echo ok" 2>/dev/null | grep -q "ok"; then
        print_success "RU server connection OK (key-based)"
    else
        print_error "Cannot connect to RU server via SSH key."
        print_error "Run: ssh-copy-id $RU_USER@$RU_IP"
        exit 1
    fi
    
    print_info "Testing SSH key-based connection to DE server..."
    if ssh -o BatchMode=yes -o ConnectTimeout=10 -o LogLevel=ERROR "$DE_USER@$DE_IP" "echo ok" 2>/dev/null | grep -q "ok"; then
        print_success "DE server connection OK (key-based)"
    else
        print_error "Cannot connect to DE server via SSH key."
        print_error "Run: ssh-copy-id $DE_USER@$DE_IP"
        exit 1
    fi
}

deploy() {
    print_step "Step 5: Starting deployment"
    
    echo -e "${BLUE}This will:${NC}"
    echo -e "  1. Clone KrotVPN on RU server"
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
    
    # Create config file on RU server with plain env vars (no encoding)
    print_info "Creating configuration on RU server..."
    ssh "$RU_USER@$RU_IP" "umask 077 && cat > /tmp/krotvpn_deploy.conf" << EOF
DE_IP='${DE_IP}'
DE_USER='${DE_USER}'
RU_IP='${RU_IP}'
RU_USER='${RU_USER}'
ADMIN_EMAIL='${ADMIN_EMAIL}'
ADMIN_PASSWORD='${ADMIN_PASSWORD}'
EOF
    
    if [ $? -ne 0 ]; then
        print_error "Failed to create config file"
        exit 1
    fi
    print_success "Config created"
    
    # Clone repository
    print_info "Cloning KrotVPN repository..."
    ssh "$RU_USER@$RU_IP" "
        cd /opt
        rm -rf KrotVPN 2>/dev/null || true
        git clone https://github.com/anyagixx/KrotVPN.git
        chmod +x /opt/KrotVPN/deploy/*.sh
    "
    
    if [ $? -ne 0 ]; then
        print_error "Failed to clone repository"
        exit 1
    fi
    print_success "Repository cloned"
    
    # Run deployment script
    print_info "Running deployment script on RU server..."
    echo ""
    
    ssh -t "$RU_USER@$RU_IP" "cd /opt/KrotVPN && ./deploy/deploy-on-server.sh"
}

show_complete() {
    print_step "Installation Complete!"
    
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║              KrotVPN is now installed!                      ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo -e "${CYAN}Access your VPN service:${NC}"
    echo ""
    echo -e "  ${GREEN}Frontend:${NC}    https://${RU_IP}"
    echo -e "  ${GREEN}Admin Panel:${NC} https://${RU_IP}:8443"
    echo -e "  ${GREEN}Backend API:${NC} https://${RU_IP} (via nginx)"
    echo ""
    echo -e "${YELLOW}Note: Browser will warn about self-signed certificate.${NC}"
    echo -e "${YELLOW}Click 'Advanced' → 'Proceed' to continue.${NC}"
    echo ""
    echo -e "${CYAN}Create VPN client:${NC}"
    echo ""
    echo -e "  ssh root@${RU_IP} \"/opt/KrotVPN/deploy/create-client.sh my_client\""
    echo ""
    echo -e "${CYAN}Configured during install:${NC}"
    echo ""
    echo -e "  • ADMIN_EMAIL         - ${GREEN}${ADMIN_EMAIL}${NC}"
    echo -e "  • ADMIN_PASSWORD      - password entered during installation"
    echo ""
    echo -e "${CYAN}Configure later in /opt/KrotVPN/.env:${NC}"
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
    get_ssh_users
    get_admin_config
    deploy
    show_complete
}

main "$@"
