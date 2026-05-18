#!/bin/bash
#
# KrotPN Server Deployment Script v3.3.1 (Full Tunnel)
# Run this script ON the RU server
# FILE: deploy/deploy-on-server.sh
# VERSION: 3.3.1
# ROLE: SCRIPT
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Provision the RU entry host, DE exit host, application runtime, Phase-35 operator wildcard TLS edge material, Phase-36 Resend email provider env, and Phase-38 DE-backed MTProto edge.
#   SCOPE: Host prerequisites, AmneziaWG tunnel setup, app env generation, TLS certificate validation/install, Resend config validation, nginx fallback/SNI-router rendering, DE MTProto runtime deployment, private policy API wiring, and Docker Compose startup.
#   DEPENDS: M-012, M-030, M-032, M-040, M-041, M-044, M-046, M-048, M-050
#   LINKS: docs/modules/M-012.xml, docs/modules/M-040.xml, docs/modules/M-041.xml, docs/modules/M-044.xml, docs/modules/M-046.xml, docs/modules/M-048.xml, docs/modules/M-050.xml, docs/plans/Phase-35.xml, docs/plans/Phase-36.xml, docs/plans/Phase-38.xml, docs/verification/V-M-048.xml, docs/verification/V-M-050.xml
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   validate_public_domain - Validate operator public-domain input before use in env/nginx config.
#   validate_tls_path - Validate absolute operator certificate paths.
#   validate_operator_tls_certificate - Verify cert/key readability, expiry, key match, and SAN coverage without leaking private keys.
#   install_operator_tls_certificate - Atomically install validated cert/key to /opt/KrotPN/ssl.
#   generate_self_signed_dev_certificate - Explicit dev/test fallback, blocked for production unless selected.
#   validate_resend_email_config - Validate Resend API key, URL, and sender without printing secrets.
#   render_nginx_domain_config - Render ignored runtime nginx fallback and HAProxy SNI-router configs for the selected domain/DE target.
#   deploy_de_mtproto_runtime - Copy runtime artifacts, TLS material, and redacted env to DE and start the private policy runtime.
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v3.3.1 - Keep public admin 8443 separate from private Phase-38 web fallback on 9443.
#   LAST_CHANGE: v3.3.0 - Added Phase-38 DE MTProto runtime deployment and RU HAProxy SNI-router wiring.
#   LAST_CHANGE: v3.2.0 - Enable MTProto shared-443 runtime sidecar and backend policy bridge token wiring.
#   LAST_CHANGE: v3.1.3 - Enable Resend email provider env wiring and fail closed when the API key is missing.
#   LAST_CHANGE: v3.1.2 - Generate required MTProto base secret and salt during fresh deploy env creation.
#   LAST_CHANGE: v3.1.1 - Reject /opt/KrotPN certificate source paths to avoid clone-time source deletion.
# END_CHANGE_SUMMARY
#
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

validate_public_domain() {
    local domain="$1"

    if [ -z "$domain" ]; then
        echo -e "${RED}[M-048][installer_tls][VALIDATE_INPUTS] Missing PUBLIC_DOMAIN${NC}"
        return 1
    fi

    if [[ "$domain" == http://* ]] || [[ "$domain" == https://* ]] || [[ "$domain" == */* ]]; then
        echo -e "${RED}[M-048][installer_tls][VALIDATE_INPUTS] PUBLIC_DOMAIN must be a bare domain name${NC}"
        return 1
    fi

    if [[ ! "$domain" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$ ]]; then
        echo -e "${RED}[M-048][installer_tls][VALIDATE_INPUTS] Invalid PUBLIC_DOMAIN: ${domain}${NC}"
        return 1
    fi

    return 0
}

validate_tls_path() {
    local path="$1"
    local label="$2"

    if [ -z "$path" ]; then
        echo -e "${RED}[M-048][installer_tls][VALIDATE_INPUTS] Missing ${label} path${NC}"
        return 1
    fi

    if [[ "$path" != /* ]]; then
        echo -e "${RED}[M-048][installer_tls][VALIDATE_INPUTS] ${label} path must be absolute${NC}"
        return 1
    fi

    if [[ ! "$path" =~ ^/[A-Za-z0-9._/@:+-]+$ ]]; then
        echo -e "${RED}[M-048][installer_tls][VALIDATE_INPUTS] ${label} path contains unsupported characters${NC}"
        return 1
    fi

    case "$path" in
        /opt/KrotPN|/opt/KrotPN/*)
            echo -e "${RED}[M-048][installer_tls][VALIDATE_INPUTS] ${label} path must not be under /opt/KrotPN because deploy refreshes that directory${NC}"
            return 1
            ;;
    esac

    return 0
}

validate_resend_api_key() {
    local api_key="$1"

    if [ -z "$api_key" ]; then
        echo -e "${RED}[M-012][deploy_resend][ABORT_MISSING_KEY] Missing RESEND_API_KEY${NC}"
        return 1
    fi

    if [[ "$api_key" == *$'\n'* ]] || [[ "$api_key" == *$'\r'* ]] || [[ "$api_key" =~ [[:space:]] ]]; then
        echo -e "${RED}[M-012][deploy_resend][ABORT_MISSING_KEY] RESEND_API_KEY must not contain whitespace${NC}"
        return 1
    fi

    if [[ ! "$api_key" =~ ^[-A-Za-z0-9._:=+/]{10,512}$ ]]; then
        echo -e "${RED}[M-012][deploy_resend][ABORT_MISSING_KEY] RESEND_API_KEY contains unsupported characters${NC}"
        return 1
    fi

    return 0
}

validate_email_from() {
    local email="$1"

    if [ -z "$email" ]; then
        echo -e "${RED}[M-012][deploy_resend][VALIDATE_INPUTS] Missing EMAIL_FROM${NC}"
        return 1
    fi

    if [[ "$email" == *$'\n'* ]] || [[ "$email" == *$'\r'* ]] || [[ "$email" =~ [[:space:]] ]]; then
        echo -e "${RED}[M-012][deploy_resend][VALIDATE_INPUTS] EMAIL_FROM must not contain whitespace${NC}"
        return 1
    fi

    if [[ ! "$email" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
        echo -e "${RED}[M-012][deploy_resend][VALIDATE_INPUTS] Invalid EMAIL_FROM format${NC}"
        return 1
    fi

    return 0
}

validate_resend_api_url() {
    local api_url="$1"

    if [ "$api_url" != "https://api.resend.com/emails" ]; then
        echo -e "${RED}[M-012][deploy_resend][VALIDATE_INPUTS] RESEND_API_URL must be https://api.resend.com/emails${NC}"
        return 1
    fi

    return 0
}

validate_resend_email_config() {
    if [ "$EMAIL_PROVIDER" != "resend" ]; then
        echo -e "${RED}[M-012][deploy_resend][ABORT_MISSING_KEY] EMAIL_PROVIDER must be resend for production email verification${NC}"
        exit 1
    fi

    validate_resend_api_key "$RESEND_API_KEY" || exit 1
    validate_resend_api_url "$RESEND_API_URL" || exit 1
    validate_email_from "$EMAIL_FROM" || exit 1

    echo -e "${BLUE}[M-012][deploy_resend][ENV_WIRING] Resend email provider configured for ${EMAIL_FROM}${NC}"
    echo -e "${BLUE}[M-012][deploy_resend][REDACT_SECRET] RESEND_API_KEY accepted and redacted${NC}"
    echo -e "${BLUE}[M-048][deploy_resend][ENV_WIRING] Resend env will be written with secret redaction${NC}"
}

ensure_openssl_available() {
    if command -v openssl >/dev/null 2>&1; then
        return 0
    fi

    echo -e "${BLUE}[M-048][installer_tls][VALIDATE_CERT_PATHS] Installing openssl for TLS validation...${NC}"
    apt-get update -qq && apt-get install -y -qq openssl ca-certificates
}

validate_operator_tls_certificate() {
    local domain="${PUBLIC_DOMAIN}"
    local wildcard_domain="*.${domain}"
    local cert_pub_hash=""
    local key_pub_hash=""
    local san_text=""
    local escaped_domain=""
    local not_after=""

    echo -e "${BLUE}[M-048][installer_tls][VALIDATE_CERT_PATHS] Validating operator wildcard TLS material...${NC}"

    validate_public_domain "$domain" || exit 1
    validate_tls_path "$TLS_FULLCHAIN_PATH" "TLS fullchain" || exit 1
    validate_tls_path "$TLS_PRIVKEY_PATH" "TLS private key" || exit 1
    ensure_openssl_available

    for path in "$TLS_FULLCHAIN_PATH" "$TLS_PRIVKEY_PATH"; do
        if [ ! -f "$path" ]; then
            echo -e "${RED}[M-048][deploy_tls][ABORT_BEFORE_DEPLOY] Missing TLS file: ${path}${NC}"
            exit 1
        fi
        if [ ! -r "$path" ]; then
            echo -e "${RED}[M-048][deploy_tls][ABORT_BEFORE_DEPLOY] TLS file is not readable: ${path}${NC}"
            exit 1
        fi
        if [ ! -s "$path" ]; then
            echo -e "${RED}[M-048][deploy_tls][ABORT_BEFORE_DEPLOY] TLS file is empty: ${path}${NC}"
            exit 1
        fi
    done

    openssl x509 -in "$TLS_FULLCHAIN_PATH" -noout >/dev/null 2>&1 || {
        echo -e "${RED}[M-048][deploy_tls][ABORT_BEFORE_DEPLOY] TLS fullchain is not a readable X.509 certificate${NC}"
        exit 1
    }
    openssl pkey -in "$TLS_PRIVKEY_PATH" -noout >/dev/null 2>&1 || {
        echo -e "${RED}[M-048][deploy_tls][ABORT_BEFORE_DEPLOY] TLS private key is not readable by openssl${NC}"
        exit 1
    }

    if ! openssl x509 -in "$TLS_FULLCHAIN_PATH" -checkend 86400 -noout >/dev/null 2>&1; then
        echo -e "${RED}[M-048][deploy_tls][ABORT_BEFORE_DEPLOY] TLS certificate is expired or expires in less than 24 hours${NC}"
        exit 1
    fi

    cert_pub_hash="$(openssl x509 -in "$TLS_FULLCHAIN_PATH" -pubkey -noout 2>/dev/null | openssl pkey -pubin -outform der 2>/dev/null | openssl dgst -sha256 2>/dev/null | awk '{print $2}')"
    key_pub_hash="$(openssl pkey -in "$TLS_PRIVKEY_PATH" -pubout -outform der 2>/dev/null | openssl dgst -sha256 2>/dev/null | awk '{print $2}')"
    if [ -z "$cert_pub_hash" ] || [ -z "$key_pub_hash" ] || [ "$cert_pub_hash" != "$key_pub_hash" ]; then
        echo -e "${RED}[M-048][installer_tls][VALIDATE_CERT_KEY_MATCH] TLS certificate and private key do not match${NC}"
        exit 1
    fi

    san_text="$(openssl x509 -in "$TLS_FULLCHAIN_PATH" -noout -ext subjectAltName 2>/dev/null || true)"
    escaped_domain="$(printf '%s' "$domain" | sed 's/[.[\*^$()+?{}|\\]/\\&/g')"
    if ! printf '%s\n' "$san_text" | grep -Eq "DNS:${escaped_domain}([,[:space:]]|$)"; then
        echo -e "${RED}[M-048][installer_tls][VALIDATE_SAN] TLS certificate SAN does not include ${domain}${NC}"
        exit 1
    fi
    if ! printf '%s\n' "$san_text" | grep -Eq "DNS:\*\.${escaped_domain}([,[:space:]]|$)"; then
        echo -e "${RED}[M-048][installer_tls][VALIDATE_SAN] TLS certificate SAN does not include ${wildcard_domain}${NC}"
        exit 1
    fi

    not_after="$(openssl x509 -in "$TLS_FULLCHAIN_PATH" -noout -enddate 2>/dev/null | sed 's/^notAfter=//')"
    echo -e "${GREEN}[M-048][installer_tls][VALIDATE_SAN] TLS certificate covers ${domain} and ${wildcard_domain}; expires ${not_after}${NC}"
}

install_operator_tls_certificate() {
    local ssl_dir="/opt/KrotPN/ssl"
    local tmp_cert=""
    local tmp_key=""

    echo -e "${BLUE}[M-048][deploy_tls][INSTALL_CERT] Installing operator wildcard TLS certificate...${NC}"
    mkdir -p "$ssl_dir"
    tmp_cert="$(mktemp "${ssl_dir}/server.crt.tmp.XXXXXX")"
    tmp_key="$(mktemp "${ssl_dir}/server.key.tmp.XXXXXX")"

    cp "$TLS_FULLCHAIN_PATH" "$tmp_cert"
    cp "$TLS_PRIVKEY_PATH" "$tmp_key"
    chown root:root "$tmp_cert" "$tmp_key"
    chmod 644 "$tmp_cert"
    chmod 600 "$tmp_key"
    mv "$tmp_cert" "${ssl_dir}/server.crt"
    mv "$tmp_key" "${ssl_dir}/server.key"
    echo -e "${GREEN}[M-048][deploy_tls][INSTALL_CERT] Operator TLS material installed at /opt/KrotPN/ssl/server.crt and /opt/KrotPN/ssl/server.key${NC}"
}

generate_self_signed_dev_certificate() {
    echo -e "${YELLOW}[M-048][deploy_tls][INSTALL_CERT] Generating self-signed TLS because TLS_CERTIFICATE_MODE=self-signed-dev${NC}"
    mkdir -p /opt/KrotPN/ssl
    cd /opt/KrotPN/ssl
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout server.key -out server.crt \
        -subj "/C=RU/ST=Moscow/L=Moscow/O=KrotPN/OU=IT/CN=krotpn.local" 2>/dev/null
    chmod 600 server.key
    chmod 644 server.crt
    echo -e "${GREEN}✓ Dev self-signed SSL certificate generated${NC}"
}

render_nginx_domain_config() {
    local source_conf="/opt/KrotPN/nginx/nginx.conf"
    local runtime_conf="/opt/KrotPN/nginx/nginx.runtime.conf"
    local router_source_conf="/opt/KrotPN/deploy/haproxy-phase38.cfg"
    local router_runtime_conf="/opt/KrotPN/deploy/haproxy.runtime.cfg"
    local mtproto_de_target="${EDGE_MTPROTO_DE_TARGET_HOST}:${EDGE_MTPROTO_DE_TARGET_PORT}"

    echo -e "${BLUE}[M-048][deploy_tls][ENV_WIRING] Rendering nginx runtime config for ${PUBLIC_DOMAIN}...${NC}"
    cp "$source_conf" "$runtime_conf"
    sed -i "s/krotpn.xyz/${PUBLIC_DOMAIN}/g" "$runtime_conf"
    chmod 644 "$runtime_conf"
    echo -e "${GREEN}[M-048][deploy_tls][ENV_WIRING] nginx runtime config ready: ${runtime_conf}${NC}"

    echo -e "${BLUE}[M-050][ru_sni_router][ROUTE_WEB] Rendering RU SNI router web fallback for ${PUBLIC_DOMAIN}:443 -> 127.0.0.1:9443${NC}"
    echo -e "${BLUE}[M-050][ru_sni_router][ROUTE_MTPROTO] Rendering RU SNI router MTProto target ${mtproto_de_target}${NC}"
    cp "$router_source_conf" "$router_runtime_conf"
    sed -i "s/krotpn.xyz/${PUBLIC_DOMAIN}/g" "$router_runtime_conf"
    sed -i "s/127\\.0\\.0\\.1:19443/${mtproto_de_target}/g" "$router_runtime_conf"
    chmod 644 "$router_runtime_conf"
    echo -e "${GREEN}[M-050][ru_sni_router][ROUTE_UNKNOWN_SNI] Unknown SNI fallback remains RU nginx HTTPS fallback${NC}"
}

existing_env_value() {
    local key="$1"
    local env_file="${2:-/opt/KrotPN/.env}"

    if [ ! -f "$env_file" ]; then
        return 0
    fi

    awk -F= -v key="$key" '
        $1 == key {
            sub(/^[^=]*=/, "")
            print
            exit
        }
    ' "$env_file"
}

generate_or_preserve_secret() {
    local key="$1"
    local generator="$2"
    local validator_regex="$3"
    local existing=""

    existing="$(existing_env_value "$key")"
    if [ -n "$existing" ] && [[ "$existing" =~ $validator_regex ]]; then
        printf '%s' "$existing"
        return 0
    fi

    python3 -c "$generator"
}

deploy_de_mtproto_runtime() {
    local de_app_dir="/opt/krotpn-mtproto"
    local runtime_tar="/tmp/krotpn-mtproto-runtime.tgz"
    local policy_health_url="http://${MTPROTO_POLICY_BIND_IP}:${MTPROTO_POLICY_PORT}/krotpn/mtproto/policy/health"

    echo -e "${BLUE}[M-050][de_mtproto_runtime][START_RUNTIME] Preparing DE MTProto runtime on ${DE_IP}...${NC}"

    tar --exclude='_build' --exclude='rebar3.crashdump' -C /opt/KrotPN -czf "$runtime_tar" mtproto-runtime
    ssh_de "rm -rf '${de_app_dir}/mtproto-runtime' && mkdir -p '${de_app_dir}/ssl'"
    sshpass -p "$DE_PASS" scp -o StrictHostKeyChecking=accept-new -o LogLevel=ERROR "$runtime_tar" "$DE_USER@$DE_IP:/tmp/krotpn-mtproto-runtime.tgz"
    ssh_de "tar -xzf /tmp/krotpn-mtproto-runtime.tgz -C '${de_app_dir}' && rm -f /tmp/krotpn-mtproto-runtime.tgz"
    rm -f "$runtime_tar"

    sshpass -p "$DE_PASS" scp -o StrictHostKeyChecking=accept-new -o LogLevel=ERROR /opt/KrotPN/deploy/mtproto-de-compose.yml "$DE_USER@$DE_IP:${de_app_dir}/docker-compose.yml"
    sshpass -p "$DE_PASS" scp -o StrictHostKeyChecking=accept-new -o LogLevel=ERROR /opt/KrotPN/ssl/server.crt "$DE_USER@$DE_IP:${de_app_dir}/ssl/server.crt"
    sshpass -p "$DE_PASS" scp -o StrictHostKeyChecking=accept-new -o LogLevel=ERROR /opt/KrotPN/ssl/server.key "$DE_USER@$DE_IP:${de_app_dir}/ssl/server.key"
    ssh_de "chmod 644 '${de_app_dir}/ssl/server.crt' && chmod 600 '${de_app_dir}/ssl/server.key'"

    sshpass -p "$DE_PASS" ssh -o StrictHostKeyChecking=accept-new -o LogLevel=ERROR "$DE_USER@$DE_IP" "cat > '${de_app_dir}/.env' && chmod 600 '${de_app_dir}/.env'" << EOF
MTPROTO_BASE_DOMAIN=${PUBLIC_DOMAIN}
MTPROTO_DE_RUNTIME_PORT=${EDGE_MTPROTO_DE_TARGET_PORT}
MTPROTO_BASE_SECRET_HEX=${MTPROTO_BASE_SECRET_HEX}
MTPROTO_SECRET_SALT=${MTPROTO_SECRET_SALT}
MTPROTO_RUNTIME_TOKEN=${MTPROTO_RUNTIME_TOKEN}
MTPROTO_POLICY_PORT=${MTPROTO_POLICY_PORT}
MTPROTO_POLICY_BIND_IP=${MTPROTO_POLICY_BIND_IP}
MTPROTO_POLICY_TLS_PORT=18443
DE_MTPROTO_DOMAIN_FRONTING=127.0.0.1:9443
EOF

    ssh_de "ufw allow proto tcp from '${RU_IP}' to any port '${EDGE_MTPROTO_DE_TARGET_PORT}' >/dev/null 2>&1 || true"
    ssh_de "ufw allow in on awg0 proto tcp from '${VPN_RELAY_RU_ADDRESS}' to any port '${MTPROTO_POLICY_PORT}' >/dev/null 2>&1 || true"
    ssh_de "ufw --force enable >/dev/null 2>&1 || true"
    echo -e "${GREEN}[M-050][de_policy_api][DENY_PUBLIC] DE policy API binds ${MTPROTO_POLICY_BIND_IP} and public firewall does not allow ${MTPROTO_POLICY_PORT}/tcp${NC}"

    ssh_de "cd '${de_app_dir}' && docker compose up -d --build"
    ssh_de "cd '${de_app_dir}' && set -a && . ./.env && set +a && curl -fsS -H \"x-krotpn-mtproto-token: \${MTPROTO_RUNTIME_TOKEN}\" '${policy_health_url}' >/dev/null"
    echo -e "${GREEN}[M-050][de_policy_api][HEALTH] Private DE MTProto policy health passed over ${MTPROTO_POLICY_BIND_IP}:${MTPROTO_POLICY_PORT}${NC}"
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
PUBLIC_DOMAIN="$(printf '%s' "${PUBLIC_DOMAIN:-krotpn.xyz}" | tr '[:upper:]' '[:lower:]')"
TLS_FULLCHAIN_PATH="${TLS_FULLCHAIN_PATH:-/root/krotpn-ssl/fullchain1.pem}"
TLS_PRIVKEY_PATH="${TLS_PRIVKEY_PATH:-/root/krotpn-ssl/privkey1.pem}"
TLS_CERTIFICATE_MODE="${TLS_CERTIFICATE_MODE:-operator-wildcard}"
EMAIL_PROVIDER="${EMAIL_PROVIDER:-resend}"
RESEND_API_KEY="${RESEND_API_KEY:-}"
RESEND_API_URL="${RESEND_API_URL:-https://api.resend.com/emails}"
EMAIL_FROM="$(printf '%s' "${EMAIL_FROM:-noreply@${PUBLIC_DOMAIN}}" | tr '[:upper:]' '[:lower:]')"
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

MTPROTO_POLICY_PORT="${MTPROTO_POLICY_PORT:-18080}"
EDGE_MTPROTO_MODE="${EDGE_MTPROTO_MODE:-de-backed}"
EDGE_MTPROTO_DE_TARGET_HOST="${EDGE_MTPROTO_DE_TARGET_HOST:-$DE_IP}"
EDGE_MTPROTO_DE_TARGET_PORT="${EDGE_MTPROTO_DE_TARGET_PORT:-443}"

validate_resend_email_config

case "$TLS_CERTIFICATE_MODE" in
    operator-wildcard)
        validate_operator_tls_certificate
        ;;
    self-signed-dev)
        validate_public_domain "$PUBLIC_DOMAIN" || exit 1
        echo -e "${YELLOW}[M-048][deploy_tls][INSTALL_CERT] self-signed-dev mode is enabled; do not use for production${NC}"
        ;;
    *)
        echo -e "${RED}[M-048][installer_tls][VALIDATE_INPUTS] Unsupported TLS_CERTIFICATE_MODE: ${TLS_CERTIFICATE_MODE}${NC}"
        exit 1
        ;;
esac

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
MTPROTO_POLICY_BIND_IP="${MTPROTO_POLICY_BIND_IP:-$VPN_RELAY_DE_ADDRESS}"
if [ "$MTPROTO_POLICY_BIND_IP" = "0.0.0.0" ]; then
    echo -e "${RED}[M-050][de_policy_api][DENY_PUBLIC] MTPROTO_POLICY_BIND_IP must not be 0.0.0.0${NC}"
    exit 1
fi

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

echo -e "${BLUE}[DE] Installing Docker for MTProto runtime...${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sh /tmp/get-docker.sh
    apt install -y -qq docker-compose-plugin
fi
echo -e "${GREEN}✓ Docker installed${NC}"

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
PostUp = ip route replace 149.154.160.0/20 dev %i; ip route replace 91.108.4.0/22 dev %i; ip route replace 91.108.56.0/22 dev %i; ip route replace 91.105.192.0/23 dev %i
PreDown = ip route del 149.154.160.0/20 dev %i 2>/dev/null || true; ip route del 91.108.4.0/22 dev %i 2>/dev/null || true; ip route del 91.108.56.0/22 dev %i 2>/dev/null || true; ip route del 91.105.192.0/23 dev %i 2>/dev/null || true
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

# START_BLOCK_MTPROTO_TELEGRAM_ROUTES
echo -e "${BLUE}[RU] Routing Telegram MTProto upstream ranges through DE tunnel...${NC}"
for tg_route in 149.154.160.0/20 91.108.4.0/22 91.108.56.0/22 91.105.192.0/23; do
    ip route replace "$tg_route" dev awg-client 2>/dev/null || true
done
echo -e "${GREEN}✓ Telegram MTProto upstream routes use awg-client${NC}"
# END_BLOCK_MTPROTO_TELEGRAM_ROUTES

# Show routing table for debugging
echo -e "${BLUE}[RU] Current routes to DE tunnel:${NC}"
ip route show | grep -E "(awg-client|${VPN_RELAY_SUBNET%%/*}|149\\.154\\.160\\.0|91\\.108\\.4\\.0|91\\.108\\.56\\.0|91\\.105\\.192\\.0)" || echo "No routes found"

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

# Install SSL
echo -e "${BLUE}[RU] Installing SSL certificate...${NC}"
case "$TLS_CERTIFICATE_MODE" in
    operator-wildcard)
        validate_operator_tls_certificate
        install_operator_tls_certificate
        ;;
    self-signed-dev)
        generate_self_signed_dev_certificate
        ;;
esac
render_nginx_domain_config

# Generate .env
echo -e "${BLUE}[RU] Creating configuration...${NC}"
cd /opt/KrotPN
SECRET_KEY=$(generate_or_preserve_secret SECRET_KEY "import secrets; print(secrets.token_urlsafe(32))" '^[-A-Za-z0-9._~+/=]{32,}$')
DATA_KEY=$(generate_or_preserve_secret DATA_ENCRYPTION_KEY "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" '^[A-Za-z0-9_-]{43}=$')
DB_PASSWORD=$(generate_or_preserve_secret DB_PASSWORD "import secrets; print(secrets.token_urlsafe(16))" '^[-A-Za-z0-9._~+/=]{16,}$')
MTPROTO_BASE_SECRET_HEX=$(generate_or_preserve_secret MTPROTO_BASE_SECRET_HEX "import secrets; print(secrets.token_hex(16))" '^[0-9a-f]{32}$')
MTPROTO_SECRET_SALT=$(generate_or_preserve_secret MTPROTO_SECRET_SALT "import secrets; print(secrets.token_hex(16))" '^[0-9a-f]{32}$')
MTPROTO_RUNTIME_TOKEN=$(generate_or_preserve_secret MTPROTO_RUNTIME_TOKEN "import secrets; print(secrets.token_urlsafe(32))" '^[-A-Za-z0-9._~+/=]{24,512}$')

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
CORS_ORIGINS=["https://${PUBLIC_DOMAIN}","https://www.${PUBLIC_DOMAIN}","https://${RU_IP}","http://${RU_IP}","http://localhost"]

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
EMAIL_PROVIDER=${EMAIL_PROVIDER}
RESEND_API_KEY=${RESEND_API_KEY}
RESEND_API_URL=${RESEND_API_URL}
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
EMAIL_FROM=${EMAIL_FROM}
EMAIL_VERIFICATION_URL_BASE=https://${PUBLIC_DOMAIN}/verify-email

# === REFERRAL ===
REFERRAL_BONUS_DAYS=7
REFERRAL_MIN_PAYMENT=100.0

# === PUBLIC DOMAIN / TLS EDGE ===
DOMAIN=${PUBLIC_DOMAIN}
FRONTEND_URL=https://${PUBLIC_DOMAIN}
MTPROTO_BASE_DOMAIN=${PUBLIC_DOMAIN}
MTPROTO_PROXY_PORT=443
MTPROTO_BASE_SECRET_HEX=${MTPROTO_BASE_SECRET_HEX}
MTPROTO_SECRET_SALT=${MTPROTO_SECRET_SALT}
MTPROTO_RUNTIME_POLICY_URL=http://${MTPROTO_POLICY_BIND_IP}:${MTPROTO_POLICY_PORT}/krotpn/mtproto/policy
MTPROTO_RUNTIME_TOKEN=${MTPROTO_RUNTIME_TOKEN}
MTPROTO_RUNTIME_TIMEOUT_SECONDS=3.0
MTPROTO_POLICY_PORT=${MTPROTO_POLICY_PORT}
MTPROTO_POLICY_BIND_IP=${MTPROTO_POLICY_BIND_IP}
EDGE_PUBLIC_DOMAIN=${PUBLIC_DOMAIN}
EDGE_CANONICAL_HOST=${PUBLIC_DOMAIN}
EDGE_TLS_CERTIFICATE_PATH=/etc/nginx/ssl/server.crt
EDGE_TLS_CERTIFICATE_KEY_PATH=/etc/nginx/ssl/server.key
EDGE_TLS_CERTIFICATE_MODE=${TLS_CERTIFICATE_MODE}
EDGE_SHARED_443_ENABLED=true
EDGE_HTTPS_FALLBACK_PORT=9443
EDGE_MTPROTO_MODE=${EDGE_MTPROTO_MODE}
EDGE_MTPROTO_DE_TARGET_HOST=${EDGE_MTPROTO_DE_TARGET_HOST}
EDGE_MTPROTO_DE_TARGET_PORT=${EDGE_MTPROTO_DE_TARGET_PORT}
NGINX_CONF_PATH=./nginx/nginx.runtime.conf
SNI_ROUTER_CONF_PATH=./deploy/haproxy.runtime.cfg
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

# DE MTProto runtime
echo -e "${BLUE}[M-050][de_mtproto_runtime][START_RUNTIME] Deploying DE-backed MTProto runtime...${NC}"
deploy_de_mtproto_runtime
echo -e "${GREEN}[M-050][de_mtproto_runtime][START_RUNTIME] DE-backed MTProto runtime deployed${NC}"

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
echo -e "  Frontend:    ${CYAN}https://${PUBLIC_DOMAIN}${NC}"
echo -e "  Admin Panel: ${CYAN}https://${PUBLIC_DOMAIN}:8443${NC}"
echo -e "  Backend API: ${CYAN}https://${PUBLIC_DOMAIN}/api${NC}"
echo ""
echo -e "  Create VPN client:"
echo -e "  ${YELLOW}/opt/KrotPN/deploy/create-client.sh my_client${NC}"
echo ""

# Cleanup happens via trap
