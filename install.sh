#!/bin/bash
#
# KrotVPN Interactive Installer
# Run this command to install:
#   curl -fsSL https://raw.githubusercontent.com/anyagixx/KrotVPN/main/install.sh | bash
#
# Or:
#   wget -qO- https://raw.githubusercontent.com/anyagixx/KrotVPN/main/install.sh | bash
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Print functions
print_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║    ██╗  ██╗██████╗ ███████╗██████╗  ██████╗ ██████╗ ██╗     ║"
    echo "║    ██║ ██╔╝██╔══██╗██╔════╝██╔══██╗██╔═══██╗██╔══██╗██║     ║"
    echo "║    █████╔╝ ██████╔╝█████╗  ██████╔╝██║   ██║██████╔╝██║     ║"
    echo "║    ██╔═██╗ ██╔══██╗██╔══╝  ██╔══██╗██║   ██║██╔═══╝ ██║     ║"
    echo "║    ██║  ██╗██║  ██║███████╗██║  ██║╚██████╔╝██║     ███████╗║"
    echo "║    ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚══════╝║"
    echo "║                                                              ║"
    echo "║              Interactive Installer v2.1.0                   ║"
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

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
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
    
    read -r value
    
    if [ -z "$value" ] && [ -n "$default" ]; then
        value="$default"
    fi
    
    eval "$var='$value'"
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
    
    read -r value
    
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

# Check if running on a server or locally
check_environment() {
    print_step "Step 1: Checking environment"
    
    # Check if we're on Linux
    if [ "$(uname -s)" != "Linux" ]; then
        print_error "This installer only works on Linux"
        print_info "If you're on Windows/Mac, use WSL2 or a Linux VM"
        exit 1
    fi
    print_success "Running on Linux"
    
    # Check if we have SSH
    if ! command -v ssh &> /dev/null; then
        print_error "SSH client not found"
        print_info "Install with: sudo apt install openssh-client"
        exit 1
    fi
    print_success "SSH client available"
    
    # Check if we have curl/wget
    if command -v curl &> /dev/null; then
        print_success "curl available"
        DOWNLOADER="curl"
    elif command -v wget &> /dev/null; then
        print_success "wget available"
        DOWNLOADER="wget"
    else
        print_error "Neither curl nor wget found"
        print_info "Install with: sudo apt install curl"
        exit 1
    fi
}

# Get server information
get_server_info() {
    print_step "Step 2: Server configuration"
    
    echo -e "${BLUE}KrotVPN requires two servers:${NC}"
    echo -e "  ${CYAN}• RU Server (Russia)${NC} - Entry node, hosts the application"
    echo -e "  ${CYAN}• DE Server (Germany/EU)${NC} - Exit node, provides internet access"
    echo ""
    
    ask "Enter RU Server IP address (Russia)" "" RU_IP
    if [ -z "$RU_IP" ]; then
        print_error "RU Server IP is required"
        exit 1
    fi
    
    ask "Enter DE Server IP address (Germany/EU)" "" DE_IP
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

# Setup SSH keys
setup_ssh() {
    print_step "Step 3: SSH access setup"
    
    # Check if SSH key exists
    if [ ! -f ~/.ssh/id_rsa.pub ] && [ ! -f ~/.ssh/id_ed25519.pub ]; then
        echo -e "${BLUE}No SSH key found. We need to create one.${NC}"
        ask_yesno "Generate SSH key?" "y" GEN_KEY
        
        if [ "$GEN_KEY" = "y" ]; then
            print_info "Generating SSH key (press Enter for defaults)..."
            ssh-keygen -t ed25519 -C "krotvpn" -f ~/.ssh/id_ed25519 -N ""
            print_success "SSH key generated"
        else
            print_error "SSH key is required for automated deployment"
            exit 1
        fi
    else
        print_success "SSH key found"
    fi
    
    # Get the public key
    if [ -f ~/.ssh/id_ed25519.pub ]; then
        SSH_KEY=$(cat ~/.ssh/id_ed25519.pub)
    else
        SSH_KEY=$(cat ~/.ssh/id_rsa.pub)
    fi
    
    echo ""
    echo -e "${YELLOW}Your SSH public key:${NC}"
    echo -e "${CYAN}${SSH_KEY}${NC}"
    echo ""
    
    # Test SSH access to RU
    print_info "Testing SSH access to RU server (${RU_IP})..."
    if ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=no root@${RU_IP} "echo ok" 2>/dev/null; then
        print_success "RU server accessible via SSH"
        RU_SSH_OK=1
    else
        RU_SSH_OK=0
        print_warning "Cannot connect to RU server"
        echo ""
        echo -e "${YELLOW}You need to add your SSH key to the RU server.${NC}"
        echo -e "${YELLOW}Run this command on the RU server:${NC}"
        echo ""
        echo -e "${GREEN}  echo '${SSH_KEY}' >> ~/.ssh/authorized_keys${NC}"
        echo ""
        ask_yesno "Have you added the key to RU server?" "n" RU_KEY_ADDED
        if [ "$RU_KEY_ADDED" != "y" ]; then
            print_error "Please add the SSH key and run the installer again"
            exit 1
        fi
        
        # Test again
        if ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=no root@${RU_IP} "echo ok" 2>/dev/null; then
            print_success "RU server accessible via SSH"
            RU_SSH_OK=1
        else
            print_error "Still cannot connect to RU server"
            exit 1
        fi
    fi
    
    # Test SSH access to DE
    print_info "Testing SSH access to DE server (${DE_IP})..."
    if ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=no root@${DE_IP} "echo ok" 2>/dev/null; then
        print_success "DE server accessible via SSH"
        DE_SSH_OK=1
    else
        DE_SSH_OK=0
        print_warning "Cannot connect to DE server"
        echo ""
        echo -e "${YELLOW}You need to add your SSH key to the DE server.${NC}"
        echo -e "${YELLOW}Run this command on the DE server:${NC}"
        echo ""
        echo -e "${GREEN}  echo '${SSH_KEY}' >> ~/.ssh/authorized_keys${NC}"
        echo ""
        ask_yesno "Have you added the key to DE server?" "n" DE_KEY_ADDED
        if [ "$DE_KEY_ADDED" != "y" ]; then
            print_error "Please add the SSH key and run the installer again"
            exit 1
        fi
        
        # Test again
        if ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=no root@${DE_IP} "echo ok" 2>/dev/null; then
            print_success "DE server accessible via SSH"
            DE_SSH_OK=1
        else
            print_error "Still cannot connect to DE server"
            exit 1
        fi
    fi
}

# Clone repository
clone_repo() {
    print_step "Step 4: Downloading KrotVPN"
    
    INSTALL_DIR="${INSTALL_DIR:-/opt/KrotVPN}"
    
    if [ -d "$INSTALL_DIR" ]; then
        print_warning "Directory $INSTALL_DIR already exists"
        ask_yesno "Remove and reinstall?" "y" REINSTALL
        if [ "$REINSTALL" = "y" ]; then
            rm -rf "$INSTALL_DIR"
        else
            cd "$INSTALL_DIR"
            print_info "Using existing installation"
            return
        fi
    fi
    
    print_info "Cloning KrotVPN repository..."
    
    # Detect if we're running from curl or from local
    if [ -f "$(dirname "$0")/deploy/deploy-all.sh" ]; then
        # Running from local directory
        SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
        cp -r "$SCRIPT_DIR" "$INSTALL_DIR"
        print_success "Copied from local directory"
    else
        # Running from curl
        git clone https://github.com/anyagixx/KrotVPN.git "$INSTALL_DIR"
        print_success "Cloned from GitHub"
    fi
    
    cd "$INSTALL_DIR"
}

# Run deployment
run_deployment() {
    print_step "Step 5: Starting deployment"
    
    echo -e "${BLUE}This will:${NC}"
    echo -e "  1. Install dependencies on both servers"
    echo -e "  2. Install and configure AmneziaWG"
    echo -e "  3. Set up VPN tunnel between servers"
    echo -e "  4. Install Docker and run KrotVPN containers"
    echo -e "  5. Generate SSL certificates for HTTPS"
    echo ""
    
    ask_yesno "Start deployment?" "y" START_DEPLOY
    if [ "$START_DEPLOY" != "y" ]; then
        print_error "Deployment cancelled"
        exit 1
    fi
    
    print_info "This will take 10-15 minutes. Please wait..."
    echo ""
    
    # Run deploy-all.sh with the server IPs
    cd "$INSTALL_DIR"
    chmod +x deploy/deploy-all.sh
    ./deploy/deploy-all.sh "$RU_IP" "$DE_IP"
    
    DEPLOY_EXIT=$?
    
    if [ $DEPLOY_EXIT -ne 0 ]; then
        print_error "Deployment failed with exit code $DEPLOY_EXIT"
        print_info "Check the logs above for errors"
        exit 1
    fi
}

# Final instructions
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
    echo -e "${YELLOW}This is normal - click 'Advanced' → 'Proceed' to continue.${NC}"
    echo ""
    echo -e "${CYAN}Create your first VPN client:${NC}"
    echo ""
    echo -e "  ssh root@${RU_IP} \"/opt/KrotVPN/deploy/create-client.sh my_client\""
    echo ""
    echo -e "${CYAN}Configure in /opt/KrotVPN/.env:${NC}"
    echo ""
    echo -e "  • YOOKASSA_SHOP_ID     - for payments"
    echo -e "  • YOOKASSA_SECRET_KEY  - for payments"
    echo -e "  • TELEGRAM_BOT_TOKEN   - for Telegram bot"
    echo -e "  • ADMIN_PASSWORD       - change default password!"
    echo ""
    echo -e "${CYAN}Support:${NC}"
    echo ""
    echo -e "  GitHub: https://github.com/anyagixx/KrotVPN"
    echo ""
}

# Main
main() {
    print_banner
    check_environment
    get_server_info
    setup_ssh
    clone_repo
    run_deployment
    show_complete
}

main "$@"
