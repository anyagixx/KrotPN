#!/bin/bash
# FILE: deploy/lib/vpn-network.sh
# VERSION: 1.1.0
# ROLE: SCRIPT
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Deploy-time VPN network derivation, validation, and reboot-safe runtime routing for client/relay subnets
#   SCOPE: Fresh-deploy defaults, existing-interface preservation, capacity checks, env rendering, route/NAT address variables, and RU/DE runtime restore systemd units
#   DEPENDS: bash, python3, awk
#   LINKS: M-032 (vpn-network-addressing-capacity), M-012 (deploy-surface), V-M-032
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   vpn_network_apply_defaults - Derive gateway/interface CIDRs and relay addresses from env values
#   vpn_network_resolve - Preserve existing RU interface networks unless VPN_NETWORK_ROTATE=1, then validate
#   vpn_network_validate - Reject overlapping/too-small/fresh-10.0.0.0/8 address pools
#   vpn_network_require_address_match - Abort if an existing interface would be silently renumbered
#   vpn_network_env_lines - Render shell-safe assignments for remote deploy phases
#   vpn_runtime_write_ru_restore_service - Install reboot-safe RU routing/NAT restore script and unit
#   vpn_runtime_write_de_restore_service - Install reboot-safe DE forwarding/NAT restore script and unit
#   vpn_runtime_enable_restore_service - Enable and run the KrotPN runtime routing restore unit
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v3.3.0 - Added krotpn-vpn-runtime.service renderers so full-tunnel routing/NAT survives host reboot.
#   LAST_CHANGE: v3.2.0 - Added non-10.0.0.0/8 fresh defaults and 500/1000-device capacity validation
# END_CHANGE_SUMMARY

VPN_NETWORK_DEFAULT_CLIENT_SUBNET="172.29.0.0/22"
VPN_NETWORK_DEFAULT_RELAY_SUBNET="172.29.255.0/30"

vpn_network_extract_address() {
    local file="$1"
    [ -f "$file" ] || return 1
    awk -F= '
        tolower($1) ~ "^[[:space:]]*address[[:space:]]*$" {
            value=$2
            sub(/[[:space:]]*#.*/, "", value)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
            print value
            exit
        }
    ' "$file"
}

vpn_network_apply_defaults() {
    export VPN_CLIENT_SUBNET="${VPN_CLIENT_SUBNET:-${VPN_SUBNET:-$VPN_NETWORK_DEFAULT_CLIENT_SUBNET}}"
    export VPN_RELAY_SUBNET="${VPN_RELAY_SUBNET:-$VPN_NETWORK_DEFAULT_RELAY_SUBNET}"
    export VPN_NETWORK_ROTATE="${VPN_NETWORK_ROTATE:-0}"
    if [ -z "${VPN_CAPACITY_PROFILE:-}" ]; then
        if [ "${VPN_NETWORK_PRESERVED:-0}" = "1" ]; then
            export VPN_CAPACITY_PROFILE="0"
        else
            export VPN_CAPACITY_PROFILE="1000"
        fi
    else
        export VPN_CAPACITY_PROFILE
    fi

    eval "$(
        python3 - <<'PY'
import ipaddress
import os
import shlex

client_subnet = ipaddress.ip_network(os.environ["VPN_CLIENT_SUBNET"], strict=False)
relay_subnet = ipaddress.ip_network(os.environ["VPN_RELAY_SUBNET"], strict=False)
if client_subnet.version != 4 or relay_subnet.version != 4:
    raise SystemExit("Only IPv4 VPN subnets are supported")

client_hosts = list(client_subnet.hosts())
relay_hosts = list(relay_subnet.hosts())
if len(client_hosts) < 2:
    raise SystemExit("VPN client subnet must contain gateway plus at least one client")
if len(relay_hosts) < 2:
    raise SystemExit("VPN relay subnet must contain DE and RU addresses")

client_gateway = os.environ.get("VPN_CLIENT_GATEWAY") or str(client_hosts[0])
relay_de_address = os.environ.get("VPN_RELAY_DE_ADDRESS") or str(relay_hosts[0])
relay_ru_address = os.environ.get("VPN_RELAY_RU_ADDRESS") or str(relay_hosts[1])

values = {
    "VPN_CLIENT_SUBNET": str(client_subnet),
    "VPN_CLIENT_GATEWAY": client_gateway,
    "VPN_CLIENT_INTERFACE_CIDR": f"{client_gateway}/{client_subnet.prefixlen}",
    "VPN_RELAY_SUBNET": str(relay_subnet),
    "VPN_RELAY_DE_ADDRESS": relay_de_address,
    "VPN_RELAY_RU_ADDRESS": relay_ru_address,
    "VPN_RELAY_DE_CIDR": f"{relay_de_address}/{relay_subnet.prefixlen}",
    "VPN_RELAY_RU_CIDR": f"{relay_ru_address}/{relay_subnet.prefixlen}",
    "VPN_RELAY_RU_ALLOWED_IP": f"{relay_ru_address}/32",
    "VPN_CAPACITY_PROFILE": os.environ.get("VPN_CAPACITY_PROFILE", "0"),
    "VPN_NETWORK_ROTATE": os.environ.get("VPN_NETWORK_ROTATE", "0"),
    "VPN_NETWORK_PRESERVED": os.environ.get("VPN_NETWORK_PRESERVED", "0"),
}
for key, value in values.items():
    print(f"export {key}={shlex.quote(str(value))}")
PY
    )"
}

vpn_network_preserve_interface() {
    local file="$1"
    local role="$2"
    local address
    address="$(vpn_network_extract_address "$file" 2>/dev/null || true)"
    [ -n "$address" ] || return 0

    eval "$(
        python3 - "$address" "$role" <<'PY'
import ipaddress
import shlex
import sys

interface = ipaddress.ip_interface(sys.argv[1])
role = sys.argv[2]
network = interface.network
hosts = list(network.hosts())
values = {"VPN_NETWORK_PRESERVED": "1"}
if role == "client":
    values["VPN_CLIENT_SUBNET"] = str(network)
    values["VPN_CLIENT_GATEWAY"] = str(interface.ip)
else:
    values["VPN_RELAY_SUBNET"] = str(network)
    values["VPN_RELAY_RU_ADDRESS"] = str(interface.ip)
    if hosts:
        values["VPN_RELAY_DE_ADDRESS"] = str(hosts[0] if str(hosts[0]) != str(interface.ip) else hosts[1])
for key, value in values.items():
    print(f"export {key}={shlex.quote(str(value))}")
PY
    )"
    echo "[DeployVPN][vpn-network][NETWORK_PRESERVED] ${file} ${address}" >&2
}

vpn_network_validate() {
    python3 - <<'PY'
import ipaddress
import os
import sys

client_subnet = ipaddress.ip_network(os.environ["VPN_CLIENT_SUBNET"], strict=False)
relay_subnet = ipaddress.ip_network(os.environ["VPN_RELAY_SUBNET"], strict=False)
client_gateway = ipaddress.ip_address(os.environ["VPN_CLIENT_GATEWAY"])
relay_de = ipaddress.ip_address(os.environ["VPN_RELAY_DE_ADDRESS"])
relay_ru = ipaddress.ip_address(os.environ["VPN_RELAY_RU_ADDRESS"])
capacity_profile = int(os.environ.get("VPN_CAPACITY_PROFILE", "0") or "0")
preserved = os.environ.get("VPN_NETWORK_PRESERVED", "0") == "1"
allow_10 = os.environ.get("VPN_ALLOW_10_SUBNETS", "0") == "1"
openvpn_supernet = ipaddress.ip_network("10.0.0.0/8")

def fail(message: str, marker: str) -> None:
    print(f"[DeployVPN][vpn-network][{marker}] {message}", file=sys.stderr)
    raise SystemExit(1)

if client_subnet.overlaps(relay_subnet):
    fail(f"client_subnet={client_subnet} overlaps relay_subnet={relay_subnet}", "OVERLAP_DETECTED")
if client_gateway not in client_subnet:
    fail(f"VPN_CLIENT_GATEWAY={client_gateway} outside {client_subnet}", "OVERLAP_DETECTED")
if relay_de not in relay_subnet or relay_ru not in relay_subnet or relay_de == relay_ru:
    fail("relay DE/RU addresses are invalid for selected relay subnet", "OVERLAP_DETECTED")
if not preserved and not allow_10 and (
    client_subnet.overlaps(openvpn_supernet) or relay_subnet.overlaps(openvpn_supernet)
):
    fail("fresh KrotPN deployment must not use 10.0.0.0/8 tunnel networks", "OVERLAP_DETECTED")

usable = len(list(client_subnet.hosts())) - 1
if capacity_profile > 0 and usable < capacity_profile:
    fail(
        f"client_subnet={client_subnet} usable={usable} capacity_profile={capacity_profile}",
        "CAPACITY_VALIDATED",
    )

print(
    "[DeployVPN][configure_client_interface][CLIENT_SUBNET_APPLIED] "
    f"client_subnet={client_subnet} gateway={client_gateway} usable={usable} "
    f"capacity_profile={capacity_profile}",
    file=sys.stderr,
)
print(
    "[DeployVPN][configure_relay_interface][RELAY_SUBNET_APPLIED] "
    f"relay_subnet={relay_subnet} de={relay_de} ru={relay_ru}",
    file=sys.stderr,
)
PY
}

vpn_network_resolve() {
    local client_config="${1:-/etc/amnezia/amneziawg/awg0.conf}"
    local relay_config="${2:-/etc/amnezia/amneziawg/awg-client.conf}"

    if [ "${VPN_NETWORK_ROTATE:-0}" != "1" ]; then
        vpn_network_preserve_interface "$client_config" client
        vpn_network_preserve_interface "$relay_config" relay
    fi

    vpn_network_apply_defaults
    vpn_network_validate
}

vpn_network_require_address_match() {
    local file="$1"
    local expected="$2"
    local label="$3"
    local existing
    existing="$(vpn_network_extract_address "$file" 2>/dev/null || true)"
    if [ "${VPN_NETWORK_ROTATE:-0}" != "1" ] && [ -n "$existing" ] && [ "$existing" != "$expected" ]; then
        echo "[DeployVPN][vpn-network][ROTATION_REQUIRED] ${label} has ${existing}, expected ${expected}; set VPN_NETWORK_ROTATE=1 to renumber" >&2
        return 1
    fi
}

vpn_network_env_lines() {
    local key
    for key in \
        VPN_CLIENT_SUBNET VPN_CLIENT_GATEWAY VPN_CLIENT_INTERFACE_CIDR \
        VPN_RELAY_SUBNET VPN_RELAY_DE_ADDRESS VPN_RELAY_RU_ADDRESS \
        VPN_RELAY_DE_CIDR VPN_RELAY_RU_CIDR VPN_RELAY_RU_ALLOWED_IP \
        VPN_CAPACITY_PROFILE VPN_NETWORK_ROTATE VPN_NETWORK_PRESERVED; do
        printf '%s=%q\n' "$key" "${!key:-}"
    done
}

vpn_runtime_write_common_unit() {
    local after_units="$1"
    local wants_units="$2"

    cat > /etc/systemd/system/krotpn-vpn-runtime.service << EOF
[Unit]
Description=KrotPN reboot-safe VPN routing and NAT restore
After=network-online.target ufw.service ${after_units}
Wants=network-online.target ${wants_units}

[Service]
Type=oneshot
ExecStart=/usr/local/bin/krotpn-restore-vpn-runtime.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
}

vpn_runtime_enable_restore_service() {
    systemctl daemon-reload
    systemctl enable krotpn-vpn-runtime.service >/dev/null 2>&1 || true
    systemctl restart krotpn-vpn-runtime.service
    systemctl is-active --quiet krotpn-vpn-runtime.service
    echo "[DeployVPN][vpn-runtime][BOOT_RESTORE_SERVICE] krotpn-vpn-runtime.service active"
}

vpn_runtime_write_ru_restore_service() {
    local de_public_ip="$1"

    cat > /usr/local/bin/krotpn-restore-vpn-runtime.sh << EOF
#!/bin/bash
set -euo pipefail

VPN_CLIENT_SUBNET='${VPN_CLIENT_SUBNET}'
VPN_RELAY_SUBNET='${VPN_RELAY_SUBNET}'
DE_PUBLIC_IP='${de_public_ip}'
VPN_CLIENT_TABLE_ID='100'
VPN_CLIENT_TABLE_NAME='vpnclients'

wait_for_link() {
    local link="\$1"
    local attempt
    for attempt in {1..45}; do
        if ip link show "\${link}" >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done
    echo "[DeployVPN][vpn-runtime][BOOT_RESTORE_SERVICE] missing interface \${link}" >&2
    return 1
}

wait_for_link awg0
wait_for_link awg-client

sysctl -w net.ipv4.ip_forward=1 >/dev/null

if ! grep -Eq "^[[:space:]]*\${VPN_CLIENT_TABLE_ID}[[:space:]]+\${VPN_CLIENT_TABLE_NAME}\$" /etc/iproute2/rt_tables 2>/dev/null; then
    sed -i "/[[:space:]]\${VPN_CLIENT_TABLE_NAME}\$/d" /etc/iproute2/rt_tables 2>/dev/null || true
    echo "\${VPN_CLIENT_TABLE_ID} \${VPN_CLIENT_TABLE_NAME}" >> /etc/iproute2/rt_tables
fi

while ip rule del from "\${VPN_CLIENT_SUBNET}" table "\${VPN_CLIENT_TABLE_ID}" 2>/dev/null; do :; done
ip rule add pref 100 from "\${VPN_CLIENT_SUBNET}" table "\${VPN_CLIENT_TABLE_ID}"
ip route replace default dev awg-client table "\${VPN_CLIENT_TABLE_ID}"
ip route replace "\${VPN_RELAY_SUBNET}" dev awg-client

if [ -n "\${DE_PUBLIC_IP}" ]; then
    DE_GW="\$(ip route show default | awk '{print \$3; exit}')"
    if [ -n "\${DE_GW}" ]; then
        ip route replace "\${DE_PUBLIC_IP}/32" via "\${DE_GW}" 2>/dev/null || true
    fi
fi

for tg_route in 149.154.160.0/20 91.108.4.0/22 91.108.56.0/22 91.105.192.0/23; do
    ip route replace "\${tg_route}" dev awg-client 2>/dev/null || true
done

iptables -C FORWARD -i awg0 -o awg-client -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -i awg0 -o awg-client -j ACCEPT
iptables -C FORWARD -i awg-client -o awg0 -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -i awg-client -o awg0 -j ACCEPT
iptables -t nat -C POSTROUTING -s "\${VPN_CLIENT_SUBNET}" -o awg-client -j MASQUERADE 2>/dev/null || iptables -t nat -I POSTROUTING 1 -s "\${VPN_CLIENT_SUBNET}" -o awg-client -j MASQUERADE

echo "[DeployVPN][vpn-runtime][BOOT_RESTORE_SERVICE] ru routing restored client_subnet=\${VPN_CLIENT_SUBNET}"
EOF
    chmod +x /usr/local/bin/krotpn-restore-vpn-runtime.sh
    vpn_runtime_write_common_unit "awg-quick@awg0.service awg-quick@awg-client.service" "awg-quick@awg0.service awg-quick@awg-client.service"
}

vpn_runtime_write_de_restore_service() {
    cat > /usr/local/bin/krotpn-restore-vpn-runtime.sh << EOF
#!/bin/bash
set -euo pipefail

VPN_CLIENT_SUBNET='${VPN_CLIENT_SUBNET}'
VPN_RELAY_SUBNET='${VPN_RELAY_SUBNET}'

wait_for_link() {
    local link="\$1"
    local attempt
    for attempt in {1..45}; do
        if ip link show "\${link}" >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done
    echo "[DeployVPN][vpn-runtime][BOOT_RESTORE_SERVICE] missing interface \${link}" >&2
    return 1
}

wait_for_link awg0
sysctl -w net.ipv4.ip_forward=1 >/dev/null

EXT_IF="\$(ip route show default | awk '{print \$5; exit}')"
if [ -z "\${EXT_IF}" ]; then
    echo "[DeployVPN][vpn-runtime][BOOT_RESTORE_SERVICE] missing default egress interface" >&2
    exit 1
fi

iptables -C FORWARD -i awg0 -o "\${EXT_IF}" -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -i awg0 -o "\${EXT_IF}" -j ACCEPT
iptables -C FORWARD -i "\${EXT_IF}" -o awg0 -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -i "\${EXT_IF}" -o awg0 -j ACCEPT
iptables -t nat -C POSTROUTING -s "\${VPN_RELAY_SUBNET}" -o "\${EXT_IF}" -j MASQUERADE 2>/dev/null || iptables -t nat -I POSTROUTING 1 -s "\${VPN_RELAY_SUBNET}" -o "\${EXT_IF}" -j MASQUERADE
iptables -t nat -C POSTROUTING -s "\${VPN_CLIENT_SUBNET}" -o "\${EXT_IF}" -j MASQUERADE 2>/dev/null || iptables -t nat -I POSTROUTING 1 -s "\${VPN_CLIENT_SUBNET}" -o "\${EXT_IF}" -j MASQUERADE

echo "[DeployVPN][vpn-runtime][BOOT_RESTORE_SERVICE] de routing restored ext_if=\${EXT_IF} client_subnet=\${VPN_CLIENT_SUBNET}"
EOF
    chmod +x /usr/local/bin/krotpn-restore-vpn-runtime.sh
    vpn_runtime_write_common_unit "awg-quick@awg0.service" "awg-quick@awg0.service"
}
