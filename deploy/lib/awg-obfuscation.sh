#!/bin/bash
# FILE: deploy/lib/awg-obfuscation.sh
# VERSION: 1.0.0
# ROLE: SCRIPT
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Deploy-time AmneziaWG stealth profile generation, preservation, rendering, and host hardening
#   SCOPE: Bash helpers for CLIENT_PROFILE and RELAY_PROFILE used by RU/DE deployment scripts
#   DEPENDS: bash, awk, python3, sysctl, iptables
#   LINKS: M-030 (awg-stealth-obfuscation), M-012 (deploy-surface), V-M-030
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   awg_profile_generate - Generate bounded random profile variables for a prefix
#   awg_profile_load - Parse and validate profile variables from an existing AWG config
#   awg_profile_validate - Validate prefixed profile variables against approved ranges
#   awg_profile_ensure - Preserve existing profile unless STEALTH_ROTATE=1, otherwise generate
#   awg_profile_require_equal - Abort when two prefixed profiles differ
#   awg_profile_lines - Render AWG config lines from a prefixed profile
#   awg_profile_env_lines - Render dotenv lines from a prefixed profile
#   awg_profile_args - Render shell-safe positional args for remote scripts
#   awg_configure_userspace - Prefer amneziawg-go userspace only when installed
#   awg_apply_host_hardening - Additive sysctl/raw-table tuning for AWG UDP traffic
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v3.0.0 - Added deploy helper for bounded AWG stealth profiles and safe host tuning
# END_CHANGE_SUMMARY

AWG_PROFILE_KEYS=(JC JMIN JMAX S1 S2 H1 H2 H3 H4)

awg_profile_set() {
    local prefix="$1"
    local key="$2"
    local value="$3"
    printf -v "${prefix}${key}" '%s' "$value"
}

awg_profile_get() {
    local prefix="$1"
    local key="$2"
    local var="${prefix}${key}"
    printf '%s' "${!var:-}"
}

awg_profile_rand() {
    local minimum="$1"
    local maximum="$2"
    python3 - "$minimum" "$maximum" << 'PY'
import secrets
import sys

minimum = int(sys.argv[1])
maximum = int(sys.argv[2])
print(minimum + secrets.randbelow(maximum - minimum + 1))
PY
}

awg_profile_validate_one() {
    local prefix="$1"
    local key="$2"
    local minimum="$3"
    local maximum="$4"
    local value
    value="$(awg_profile_get "$prefix" "$key")"

    if ! [[ "$value" =~ ^[0-9]+$ ]]; then
        echo "[Deploy][awg-profile][AWG_PROFILE_MISMATCH] ${prefix}${key} is not numeric" >&2
        return 1
    fi
    if (( value < minimum || value > maximum )); then
        echo "[Deploy][awg-profile][AWG_PROFILE_MISMATCH] ${prefix}${key} outside approved range" >&2
        return 1
    fi
}

awg_profile_validate() {
    local prefix="$1"
    awg_profile_validate_one "$prefix" JC 4 8 || return 1
    awg_profile_validate_one "$prefix" JMIN 40 50 || return 1
    awg_profile_validate_one "$prefix" JMAX 100 200 || return 1
    awg_profile_validate_one "$prefix" S1 15 150 || return 1
    awg_profile_validate_one "$prefix" S2 15 150 || return 1
    awg_profile_validate_one "$prefix" H1 100000000 2147483647 || return 1
    awg_profile_validate_one "$prefix" H2 100000000 2147483647 || return 1
    awg_profile_validate_one "$prefix" H3 100000000 2147483647 || return 1
    awg_profile_validate_one "$prefix" H4 100000000 2147483647 || return 1
}

awg_profile_generate() {
    local prefix="$1"
    awg_profile_set "$prefix" JC "$(awg_profile_rand 4 8)"
    awg_profile_set "$prefix" JMIN "$(awg_profile_rand 40 50)"
    awg_profile_set "$prefix" JMAX "$(awg_profile_rand 100 200)"
    awg_profile_set "$prefix" S1 "$(awg_profile_rand 15 150)"
    awg_profile_set "$prefix" S2 "$(awg_profile_rand 15 150)"
    awg_profile_set "$prefix" H1 "$(awg_profile_rand 100000000 2147483647)"
    awg_profile_set "$prefix" H2 "$(awg_profile_rand 100000000 2147483647)"
    awg_profile_set "$prefix" H3 "$(awg_profile_rand 100000000 2147483647)"
    awg_profile_set "$prefix" H4 "$(awg_profile_rand 100000000 2147483647)"
    awg_profile_validate "$prefix"
    echo "[Deploy][awg-profile][AWG_PROFILE_GENERATED] ${prefix%_} profile generated" >&2
}

awg_profile_extract() {
    local file="$1"
    local config_key="$2"
    awk -F= -v key="$config_key" '
        tolower($1) ~ "^[[:space:]]*" tolower(key) "[[:space:]]*$" {
            value=$2
            sub(/[[:space:]]*#.*/, "", value)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
            print value
            exit
        }
    ' "$file"
}

awg_profile_load_key() {
    local prefix="$1"
    local file="$2"
    local config_key="$3"
    local var_key="$4"
    local value
    value="$(awg_profile_extract "$file" "$config_key")"
    if [ -z "$value" ]; then
        echo "[Deploy][awg-profile][AWG_PROFILE_MISMATCH] missing ${config_key} in ${file}" >&2
        return 1
    fi
    awg_profile_set "$prefix" "$var_key" "$value"
}

awg_profile_load() {
    local prefix="$1"
    local file="$2"
    [ -f "$file" ] || return 1
    awg_profile_load_key "$prefix" "$file" Jc JC || return 1
    awg_profile_load_key "$prefix" "$file" Jmin JMIN || return 1
    awg_profile_load_key "$prefix" "$file" Jmax JMAX || return 1
    awg_profile_load_key "$prefix" "$file" S1 S1 || return 1
    awg_profile_load_key "$prefix" "$file" S2 S2 || return 1
    awg_profile_load_key "$prefix" "$file" H1 H1 || return 1
    awg_profile_load_key "$prefix" "$file" H2 H2 || return 1
    awg_profile_load_key "$prefix" "$file" H3 H3 || return 1
    awg_profile_load_key "$prefix" "$file" H4 H4 || return 1
    awg_profile_validate "$prefix"
}

awg_profile_ensure() {
    local prefix="$1"
    local file="$2"
    local rotate="${3:-0}"

    if [ "$rotate" != "1" ] && [ -f "$file" ]; then
        if awg_profile_load "$prefix" "$file"; then
            echo "[Deploy][awg-profile][AWG_PROFILE_PRESERVED] ${prefix%_} profile preserved" >&2
            return 0
        fi
        echo "[Deploy][awg-profile][AWG_PROFILE_MISMATCH] ${file} has invalid profile; set STEALTH_ROTATE=1 to rotate explicitly" >&2
        return 1
    fi

    awg_profile_generate "$prefix"
}

awg_profile_require_equal() {
    local left_prefix="$1"
    local right_prefix="$2"
    local label="$3"
    local key
    for key in "${AWG_PROFILE_KEYS[@]}"; do
        if [ "$(awg_profile_get "$left_prefix" "$key")" != "$(awg_profile_get "$right_prefix" "$key")" ]; then
            echo "[Deploy][awg-profile][AWG_PROFILE_MISMATCH] ${label} mismatch on ${key}" >&2
            return 1
        fi
    done
    echo "[Deploy][awg-profile][AWG_PROFILE_PARITY_OK] ${label}" >&2
}

awg_profile_lines() {
    local prefix="$1"
    printf 'Jc = %s\n' "$(awg_profile_get "$prefix" JC)"
    printf 'Jmin = %s\n' "$(awg_profile_get "$prefix" JMIN)"
    printf 'Jmax = %s\n' "$(awg_profile_get "$prefix" JMAX)"
    printf 'S1 = %s\n' "$(awg_profile_get "$prefix" S1)"
    printf 'S2 = %s\n' "$(awg_profile_get "$prefix" S2)"
    printf 'H1 = %s\n' "$(awg_profile_get "$prefix" H1)"
    printf 'H2 = %s\n' "$(awg_profile_get "$prefix" H2)"
    printf 'H3 = %s\n' "$(awg_profile_get "$prefix" H3)"
    printf 'H4 = %s\n' "$(awg_profile_get "$prefix" H4)"
}

awg_profile_env_lines() {
    local prefix="$1"
    local env_prefix="$2"
    local key
    for key in "${AWG_PROFILE_KEYS[@]}"; do
        printf '%s%s=%s\n' "$env_prefix" "$key" "$(awg_profile_get "$prefix" "$key")"
    done
}

awg_profile_args() {
    local prefix="$1"
    local key
    for key in "${AWG_PROFILE_KEYS[@]}"; do
        printf " '%s'" "$(awg_profile_get "$prefix" "$key")"
    done
}

awg_configure_userspace() {
    if ! command -v amneziawg-go >/dev/null 2>&1; then
        return 0
    fi
    mkdir -p /etc/systemd/system/awg-quick@.service.d
    cat > /etc/systemd/system/awg-quick@.service.d/10-amneziawg-go.conf << 'EOF'
[Service]
Environment=WG_QUICK_USERSPACE_IMPLEMENTATION=/usr/local/bin/amneziawg-go
EOF
    systemctl daemon-reload >/dev/null 2>&1 || true
}

awg_apply_host_hardening() {
    local vpn_port="$1"
    cat > /etc/sysctl.d/98-krotpn-awg-performance.conf << 'EOF'
net.core.default_qdisc=fq
net.ipv4.tcp_congestion_control=bbr
net.core.rmem_max=16777216
net.core.wmem_max=16777216
net.core.rmem_default=262144
net.core.wmem_default=262144
EOF
    sysctl -p /etc/sysctl.d/98-krotpn-awg-performance.conf >/dev/null 2>&1 || true

    iptables -t raw -C PREROUTING -p udp --dport "$vpn_port" -j NOTRACK 2>/dev/null || \
        iptables -t raw -I PREROUTING 1 -p udp --dport "$vpn_port" -j NOTRACK 2>/dev/null || true
    iptables -t raw -C OUTPUT -p udp --sport "$vpn_port" -j NOTRACK 2>/dev/null || \
        iptables -t raw -I OUTPUT 1 -p udp --sport "$vpn_port" -j NOTRACK 2>/dev/null || true
}
