#!/usr/bin/env bash
#
# FILE: scripts/phase39-mtproto-live-smoke.sh
# VERSION: 1.1.0
# ROLE: SCRIPT
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Run redacted live MTProto availability diagnostics for one issued KrotPN assignment.
#   SCOPE: RU assignment lookup, private policy health, public 443 route, fake-TLS accept proof, DE downstream reachability, and operator desktop handoff.
#   DEPENDS: M-012, M-043, M-044, M-050, M-051
#   LINKS: docs/modules/M-051.xml, docs/verification/V-M-051.xml
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   sq - Quote shell values for remote bash.
#   mask_sni - Redact personal SNI labels in operator output.
#   load_access_config - Resolve RU/DE SSH connection inputs from env or the operator access file.
#   ssh_run/ssh_ru/ssh_de - Run remote commands without printing credentials.
#   remote_env_value_* - Read one whitelisted env value without dumping raw env files.
#   check_active_assignment - Verify one active MTProto assignment exists.
#   check_policy_health - Verify runtime policy health and policy count.
#   check_public_route - Verify RU public TCP 443 accepts connections.
#   check_fake_tls_accept - Verify issued fake-TLS ClientHello receives a valid runtime response.
#   check_de_fallback_guard - Verify live DE runtime fallback is the private KPprotoN HTTPS listener.
#   check_telegram_downstream - Verify DE runtime has at least one reachable Telegram downstream.
#   BLOCK_PHASE39_LIVE_SMOKE - Redacted live availability flow.
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.1.0 - Updated DE fallback guard for Phase-41 KPprotoN private 18443.
#   LAST_CHANGE: v1.0.0 - Added Phase-39 redacted live MTProto availability smoke.
# END_CHANGE_SUMMARY

set -euo pipefail

RU_IP="${RU_IP:-${RU_HOST:-}}"
RU_USER="${RU_USER:-}"
RU_PASS="${RU_PASS:-${RU_PASSWORD:-}}"
DE_IP="${DE_IP:-${DE_HOST:-}}"
DE_USER="${DE_USER:-}"
DE_PASS="${DE_PASS:-${DE_PASSWORD:-}}"
ACCESS_FILE="${ACCESS_FILE:-}"
REDACTED=0
APPLY_FALLBACK_GUARD=0

usage() {
    printf '%s\n' "Usage: $0 --redacted [--access-file PATH] [--apply-fallback-guard]"
    printf '%s\n' "Optional env: RU_IP/RU_USER/RU_PASS DE_IP/DE_USER/DE_PASS ACCESS_FILE"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --redacted)
            REDACTED=1
            shift
            ;;
        --access-file)
            ACCESS_FILE="${2:-}"
            shift 2
            ;;
        --apply-fallback-guard)
            APPLY_FALLBACK_GUARD=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf '%s\n' "[M-051][availability_smoke][ABORT] unknown_arg=$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [ "$REDACTED" -ne 1 ]; then
    printf '%s\n' "[M-051][availability_smoke][ABORT] code=redacted_mode_required"
    exit 2
fi

sq() {
    printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}

mask_sni() {
    local sni="${1:-}"
    local label=""
    local domain=""

    if [ -z "$sni" ]; then
        printf '<missing-sni>'
        return 0
    fi

    label="${sni%%.*}"
    domain="${sni#*.}"
    if [ "$domain" = "$sni" ]; then
        domain=""
    fi

    if [ "${#label}" -le 8 ]; then
        printf '%s...' "${label:0:2}"
    elif [ -n "$domain" ]; then
        printf '%s...%s.%s' "${label:0:4}" "${label: -4}" "$domain"
    else
        printf '%s...%s' "${label:0:4}" "${label: -4}"
    fi
}

first_value_matching() {
    local pattern="$1"
    [ -n "$ACCESS_FILE" ] && [ -f "$ACCESS_FILE" ] || return 0
    awk -v pattern="$pattern" '
        toupper($0) ~ pattern && $0 ~ /[:=]/ {
            line = $0
            sub(/^[^:=]*[:=][[:space:]]*/, "", line)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
            print line
            exit
        }
    ' "$ACCESS_FILE"
}

first_ip_by_index() {
    local index="$1"
    [ -n "$ACCESS_FILE" ] && [ -f "$ACCESS_FILE" ] || return 0
    grep -Eo '([0-9]{1,3}\.){3}[0-9]{1,3}' "$ACCESS_FILE" | awk '!seen[$0]++' | sed -n "${index}p"
}

extract_ip() {
    printf '%s\n' "$1" | grep -Eo '([0-9]{1,3}\.){3}[0-9]{1,3}' | head -n 1
}

extract_user() {
    printf '%s\n' "$1" | awk -F@ '
        NF > 1 {print $1; exit}
        NF == 1 && $1 !~ /[[:space:]]/ && $1 !~ /^([0-9]{1,3}\.){3}[0-9]{1,3}$/ {print $1; exit}
    '
}

load_access_config() {
    if [ -z "$ACCESS_FILE" ]; then
        if [ -f "$HOME/Загрузки/for_KrotPN.txt" ]; then
            ACCESS_FILE="$HOME/Загрузки/for_KrotPN.txt"
        elif [ -f "/home/truffle/Загрузки/for_KrotPN.txt" ]; then
            ACCESS_FILE="/home/truffle/Загрузки/for_KrotPN.txt"
        elif [ -f "$HOME/Downloads/for_KrotPN.txt" ]; then
            ACCESS_FILE="$HOME/Downloads/for_KrotPN.txt"
        fi
    fi

    local ru_host_value=""
    local de_host_value=""
    local ru_user_value=""
    local de_user_value=""

    ru_host_value="$(first_value_matching '(^|[^A-Z0-9])RU([^A-Z0-9]|_)*(IP|HOST)')"
    de_host_value="$(first_value_matching '(^|[^A-Z0-9])DE([^A-Z0-9]|_)*(IP|HOST)')"
    RU_IP="${RU_IP:-$(extract_ip "$ru_host_value")}"
    DE_IP="${DE_IP:-$(extract_ip "$de_host_value")}"

    if [ -z "$RU_IP" ]; then
        RU_IP="$(first_ip_by_index 1)"
    fi
    if [ -z "$DE_IP" ]; then
        DE_IP="$(first_ip_by_index 2)"
    fi

    ru_user_value="$(first_value_matching '(^|[^A-Z0-9])RU([^A-Z0-9]|_)*(USER|LOGIN|SSH)')"
    de_user_value="$(first_value_matching '(^|[^A-Z0-9])DE([^A-Z0-9]|_)*(USER|LOGIN|SSH)')"
    RU_USER="${RU_USER:-$(extract_user "$ru_user_value")}"
    DE_USER="${DE_USER:-$(extract_user "$de_user_value")}"
    RU_USER="${RU_USER:-root}"
    DE_USER="${DE_USER:-root}"

    RU_PASS="${RU_PASS:-$(first_value_matching '(^|[^A-Z0-9])RU([^A-Z0-9]|_)*(PASS|PASSWORD)')}"
    DE_PASS="${DE_PASS:-$(first_value_matching '(^|[^A-Z0-9])DE([^A-Z0-9]|_)*(PASS|PASSWORD)')}"
}

require_inputs() {
    if [ -z "$RU_IP" ] || [ -z "$DE_IP" ]; then
        printf '%s\n' "[M-051][availability_smoke][ABORT] code=missing_ru_or_de_host"
        exit 2
    fi

    if { [ -n "$RU_PASS" ] || [ -n "$DE_PASS" ]; } && ! command -v sshpass >/dev/null 2>&1; then
        printf '%s\n' "[M-051][availability_smoke][ABORT] code=sshpass_required_for_password_auth"
        exit 2
    fi
}

ssh_run() {
    local host="$1"
    local user="$2"
    local pass="$3"
    local command="$4"
    local target="${user}@${host}"
    local options=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=12 -o LogLevel=ERROR)

    if [ -n "$pass" ]; then
        SSHPASS="$pass" sshpass -e ssh "${options[@]}" "$target" "bash -lc $(sq "$command")"
    else
        ssh "${options[@]}" "$target" "bash -lc $(sq "$command")"
    fi
}

ssh_ru() {
    ssh_run "$RU_IP" "$RU_USER" "$RU_PASS" "$1"
}

ssh_de() {
    ssh_run "$DE_IP" "$DE_USER" "$DE_PASS" "$1"
}

remote_env_value_ru() {
    local key="$1"
    ssh_ru "cd /opt/KrotPN && awk -F= -v key=$(sq "$key") '\$1 == key {sub(/^[^=]*=/, \"\"); print; exit}' .env"
}

remote_env_value_de() {
    local key="$1"
    ssh_de "cd /opt/krotpn-mtproto && awk -F= -v key=$(sq "$key") '\$1 == key {sub(/^[^=]*=/, \"\"); print; exit}' .env"
}

check_active_assignment() {
    local db_user="${1:-krotpn}"
    local db_name="${2:-krotpn}"
    local q_db_user=""
    local q_db_name=""
    local assignment=""

    printf -v q_db_user '%q' "$db_user"
    printf -v q_db_name '%q' "$db_name"
    assignment="$(ssh_ru "docker exec krotpn-db psql -U $q_db_user -d $q_db_name -Atc \"select id || '|' || user_id || '|' || status || '|' || sni from mtproto_assignments where status = 'ACTIVE' order by id desc limit 1;\"")"

    if [ -z "$assignment" ]; then
        printf '%s\n' "[M-051][availability_smoke][LOAD_ACTIVE_ASSIGNMENT] status=missing"
        exit 1
    fi

    IFS='|' read -r ASSIGNMENT_ID ASSIGNMENT_USER_ID ASSIGNMENT_STATUS ASSIGNMENT_SNI <<EOF_ASSIGNMENT
$assignment
EOF_ASSIGNMENT

    if [ "$ASSIGNMENT_STATUS" != "ACTIVE" ]; then
        printf '%s\n' "[M-051][availability_smoke][LOAD_ACTIVE_ASSIGNMENT] status=inactive assignment_id=${ASSIGNMENT_ID:-unknown}"
        exit 1
    fi

    printf '%s\n' "[M-051][availability_smoke][LOAD_ACTIVE_ASSIGNMENT] status=found assignment_id=${ASSIGNMENT_ID} user_id=${ASSIGNMENT_USER_ID} sni=$(mask_sni "$ASSIGNMENT_SNI")"
}

check_policy_health() {
    local policy_url="$1"
    local runtime_token="$2"
    local health_url="${policy_url%/}/health"
    local health_json=""
    local summary=""

    health_json="$(ssh_ru "curl -fsS --max-time 5 -H $(sq "x-krotpn-mtproto-token: $runtime_token") $(sq "$health_url")")"
    summary="$(printf '%s' "$health_json" | python3 -c 'import json,sys; data=json.load(sys.stdin); print("status=%s policy_count=%s" % (data.get("status", "unknown"), data.get("policy_count", "unknown")))')"

    printf '%s\n' "[M-051][availability_smoke][POLICY_HEALTH] ${summary}"
}

check_public_route() {
    python3 - "$RU_IP" <<'PY'
import socket
import sys

host = sys.argv[1]
try:
    with socket.create_connection((host, 443), timeout=5):
        print("[M-051][availability_smoke][ROUTE_PUBLIC_443] status=tcp_connect")
except OSError as exc:
    print(f"[M-051][availability_smoke][ROUTE_PUBLIC_443] status=connect_failed code={exc.__class__.__name__}")
    sys.exit(1)
PY
}

check_fake_tls_accept() {
    local base_secret="$1"
    local secret_salt="$2"

    MTPROTO_BASE_SECRET_HEX="$base_secret" MTPROTO_SECRET_SALT="$secret_salt" python3 - "$RU_IP" "$ASSIGNMENT_SNI" <<'PY'
import hmac
import hashlib
import os
import secrets
import socket
import struct
import sys
import time

TLS_REC_CHANGE_CIPHER = 20
TLS_REC_HANDSHAKE = 22
TLS_REC_DATA = 23
TLS_10_VERSION = b"\x03\x01"
TLS_12_VERSION = b"\x03\x03"
TLS_CIPHERSUITE = b"\xc0\x2f"
DIGEST_POS = 11
DIGEST_LEN = 32


def frame(record_type, payload):
    return bytes([record_type]) + TLS_12_VERSION + struct.pack(">H", len(payload)) + payload


def make_sni(domain):
    domain_b = domain.encode()
    item = b"\x00" + struct.pack(">H", len(domain_b)) + domain_b
    body = struct.pack(">H", len(item)) + item
    return b"\x00\x00" + struct.pack(">H", len(body)) + body


def make_client_hello(secret, domain):
    timestamp = int(time.time())
    session_id = secrets.token_bytes(32)
    cipher_suites = bytes.fromhex("eaea130113021303c02bc02fc02cc030cca9cca8c013c014009c009d002f0035000a")
    key_share = bytes.fromhex("0033002b00295a5a000100001d0020a4146c3e8573565bb5f5c877a88a98dcbbd46a9b3ca1ab3df7217cc33b4b6d2c")
    supported_versions = bytes.fromhex("002b000b0a1a1a0304030303020301")
    real_extensions = key_share + supported_versions + make_sni(domain)
    tls_packet_len = 512
    hello_len = tls_packet_len - 4
    ext_len = tls_packet_len - (1 + 3 + 2 + 32 + 1 + len(session_id) + 2 + len(cipher_suites) + 1 + 1 + 2)
    pad_size = ext_len - len(real_extensions) - 4
    if pad_size < 0:
        raise ValueError("sni_too_long")
    extensions = real_extensions + struct.pack(">HH", 21, pad_size) + (b"\x00" * pad_size)

    def pack(fake_random):
        return (
            bytes([TLS_REC_HANDSHAKE]) + TLS_10_VERSION + struct.pack(">H", tls_packet_len)
            + b"\x01" + hello_len.to_bytes(3, "big") + TLS_12_VERSION
            + fake_random
            + bytes([len(session_id)]) + session_id
            + struct.pack(">H", len(cipher_suites)) + cipher_suites
            + b"\x01\x00"
            + struct.pack(">H", len(extensions)) + extensions
        )

    hello0 = pack(b"\x00" * DIGEST_LEN)
    digest = hmac.new(secret, hello0, hashlib.sha256).digest()
    encoded_timestamp = (b"\x00" * (DIGEST_LEN - 4)) + timestamp.to_bytes(4, "little")
    fake_random = bytes(left ^ right for left, right in zip(digest, encoded_timestamp))
    return pack(fake_random)


def parse_frame(data, offset):
    if len(data) < offset + 5:
        raise ValueError("incomplete_frame")
    record_type = data[offset]
    size = int.from_bytes(data[offset + 3:offset + 5], "big")
    end = offset + 5 + size
    if len(data) < end:
        raise ValueError("incomplete_frame_payload")
    return record_type, data[offset + 5:end], data[offset:end], end


def validate_server_response(secret, client_hello, response):
    first_type, handshake, first_frame, offset = parse_frame(response, 0)
    second_type, _change_cipher, second_frame, offset = parse_frame(response, offset)
    third_type, _data, third_frame, _offset = parse_frame(response, offset)
    if first_type != TLS_REC_HANDSHAKE or second_type != TLS_REC_CHANGE_CIPHER or third_type != TLS_REC_DATA:
        raise ValueError("unexpected_record_sequence")
    if len(handshake) < 38 or handshake[0] != 2:
        raise ValueError("unexpected_server_hello")

    actual_digest = handshake[6:38]
    hello0 = handshake[:6] + (b"\x00" * DIGEST_LEN) + handshake[38:]
    first_frame0 = frame(TLS_REC_HANDSHAKE, hello0)
    client_digest = client_hello[DIGEST_POS:DIGEST_POS + DIGEST_LEN]
    expected_digest = hmac.new(secret, client_digest + first_frame0 + second_frame + third_frame, hashlib.sha256).digest()
    if not hmac.compare_digest(actual_digest, expected_digest):
        raise ValueError("invalid_server_digest")


host = sys.argv[1]
sni = sys.argv[2].strip().lower().rstrip(".")
base_secret = os.environ.get("MTPROTO_BASE_SECRET_HEX", "").strip().lower()
secret_salt = os.environ.get("MTPROTO_SECRET_SALT", "").strip().lower()
if len(base_secret) != 32 or len(secret_salt) != 32:
    print("[M-051][availability_smoke][FAKE_TLS_ACCEPT] status=config_missing")
    sys.exit(1)

secret = hashlib.sha256((secret_salt + base_secret + sni).encode()).digest()[:16]
client_hello = make_client_hello(secret, sni)

try:
    with socket.create_connection((host, 443), timeout=6) as sock:
        sock.settimeout(6)
        sock.sendall(client_hello)
        response = b""
        while len(response) < 1024:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            if len(response) >= 5:
                try:
                    _, _, _, offset1 = parse_frame(response, 0)
                    _, _, _, offset2 = parse_frame(response, offset1)
                    _, _, _, offset3 = parse_frame(response, offset2)
                    if len(response) >= offset3:
                        break
                except ValueError:
                    pass
        if not response:
            print("[M-051][availability_smoke][FAKE_TLS_ACCEPT] status=no_response")
            sys.exit(1)
        validate_server_response(secret, client_hello, response)
        print(f"[M-051][availability_smoke][FAKE_TLS_ACCEPT] status=accepted bytes={len(response)}")
except Exception as exc:
    print(f"[M-051][availability_smoke][FAKE_TLS_ACCEPT] status=failed code={exc.__class__.__name__}")
    sys.exit(1)
PY
}

check_de_fallback_guard() {
    local bind_ip=""
    local domain_fronting=""
    local expected_domain_fronting=""

    bind_ip="$(remote_env_value_de MTPROTO_POLICY_BIND_IP)"
    bind_ip="${bind_ip:-127.0.0.1}"
    expected_domain_fronting="${bind_ip}:18443"
    domain_fronting="$(remote_env_value_de DE_MTPROTO_DOMAIN_FRONTING)"
    case "$domain_fronting" in
        "$expected_domain_fronting")
            printf '%s\n' "[M-050][de_mtproto_runtime][FALLBACK_PORT_GUARD] status=ok target=private_18443"
            ;;
        127.0.0.1:8443|127.0.0.1:9443)
            if [ "$APPLY_FALLBACK_GUARD" -eq 1 ]; then
                ssh_de "cd /opt/krotpn-mtproto && sed -i -E 's|^DE_MTPROTO_DOMAIN_FRONTING=.*$|DE_MTPROTO_DOMAIN_FRONTING=${expected_domain_fronting}|' .env && docker compose up -d >/dev/null 2>&1"
                domain_fronting="$(remote_env_value_de DE_MTPROTO_DOMAIN_FRONTING)"
                if [ "$domain_fronting" = "$expected_domain_fronting" ]; then
                    printf '%s\n' "[M-050][de_mtproto_runtime][FALLBACK_PORT_GUARD] status=corrected target=private_18443"
                    return 0
                fi
                printf '%s\n' "[M-050][de_mtproto_runtime][FALLBACK_PORT_GUARD] status=correction_failed"
                exit 1
            fi
            printf '%s\n' "[M-050][de_mtproto_runtime][FALLBACK_PORT_GUARD] status=stale_target"
            exit 1
            ;;
        *)
            printf '%s\n' "[M-050][de_mtproto_runtime][FALLBACK_PORT_GUARD] status=unexpected"
            exit 1
            ;;
    esac
}

check_telegram_downstream() {
    local bind_ip=""
    local policy_port=""
    local config_url=""
    local bootstrap_config=""
    local proxy_count=""
    local sample_hostport=""
    local sample_host=""
    local sample_port=""

    bind_ip="$(remote_env_value_de MTPROTO_POLICY_BIND_IP)"
    policy_port="$(remote_env_value_de MTPROTO_POLICY_PORT)"
    bind_ip="${bind_ip:-127.0.0.1}"
    policy_port="${policy_port:-18080}"
    config_url="http://${bind_ip}:${policy_port}/bootstrap/proxy-config"
    bootstrap_config="$(ssh_de "curl -fsS --max-time 5 $(sq "$config_url")")"
    proxy_count="$(printf '%s\n' "$bootstrap_config" | awk '/^proxy_for / {count += 1} END {print count + 0}')"

    if [ "${proxy_count:-0}" -le 0 ]; then
        printf '%s\n' "[M-051][availability_smoke][TELEGRAM_DOWNSTREAM] status=bootstrap_empty"
        exit 1
    fi

    sample_hostport="$(printf '%s\n' "$bootstrap_config" | awk '/^proxy_for / {print $3; exit}' | tr -d ';')"
    sample_host="${sample_hostport%:*}"
    sample_port="${sample_hostport##*:}"
    if ssh_de "timeout 3 bash -lc $(sq "</dev/tcp/${sample_host}/${sample_port}")"; then
        printf '%s\n' "[M-051][availability_smoke][TELEGRAM_DOWNSTREAM] status=reachable proxy_for_count=${proxy_count}"
    else
        printf '%s\n' "[M-051][availability_smoke][TELEGRAM_DOWNSTREAM] status=unreachable proxy_for_count=${proxy_count}"
        exit 1
    fi
}

# START_BLOCK_PHASE39_LIVE_SMOKE
load_access_config
require_inputs

DB_USER="$(remote_env_value_ru DB_USER)"
DB_NAME="$(remote_env_value_ru DB_NAME)"
DB_USER="${DB_USER:-krotpn}"
DB_NAME="${DB_NAME:-krotpn}"

check_active_assignment "$DB_USER" "$DB_NAME"

POLICY_URL="$(remote_env_value_ru MTPROTO_RUNTIME_POLICY_URL)"
RUNTIME_TOKEN="$(remote_env_value_ru MTPROTO_RUNTIME_TOKEN)"
BASE_SECRET="$(remote_env_value_ru MTPROTO_BASE_SECRET_HEX)"
SECRET_SALT="$(remote_env_value_ru MTPROTO_SECRET_SALT)"

if [ -z "$POLICY_URL" ] || [ -z "$RUNTIME_TOKEN" ] || [ -z "$BASE_SECRET" ] || [ -z "$SECRET_SALT" ]; then
    printf '%s\n' "[M-051][availability_smoke][ABORT] code=missing_mtproto_runtime_env"
    exit 1
fi

check_policy_health "$POLICY_URL" "$RUNTIME_TOKEN"
check_public_route
check_fake_tls_accept "$BASE_SECRET" "$SECRET_SALT"
check_de_fallback_guard
check_telegram_downstream

printf '%s\n' "[M-051][availability_smoke][TELEGRAM_DESKTOP_PROOF] status=operator_required action=retry_with_primary_telegram_button"
# END_BLOCK_PHASE39_LIVE_SMOKE
