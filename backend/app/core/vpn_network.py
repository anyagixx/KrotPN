# FILE: backend/app/core/vpn_network.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: VPN network addressing helpers for configurable client/relay subnets and capacity validation
#   SCOPE: CIDR normalization, gateway derivation, relay address derivation, client pool capacity checks, and migration guards
#   DEPENDS: stdlib (dataclasses, ipaddress), loguru
#   LINKS: M-032 (vpn-network-addressing-capacity), V-M-032
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   VPNNetworkSettings - Resolved client/relay network settings used by backend and deploy verification
#   build_vpn_network_settings - Normalize env values into a validated VPNNetworkSettings object
#   usable_client_address_count - Count usable client addresses after gateway reservation
#   validate_client_capacity - Reject capacity profiles larger than the usable client pool
#   next_client_ip - Return the first available client IP inside a selected subnet
#   choose_reprovision_address - Preserve existing tunnel address unless explicit network rotation is enabled
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v3.2.0 - Added configurable VPN subnet and 500/1000-device capacity helpers
# END_CHANGE_SUMMARY

"""VPN network addressing and capacity helpers."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress

from loguru import logger


DEFAULT_VPN_CLIENT_SUBNET = "172.29.0.0/22"
DEFAULT_VPN_RELAY_SUBNET = "172.29.255.0/30"
LEGACY_OPENVPN_SUPERNET = ipaddress.ip_network("10.0.0.0/8")


@dataclass(frozen=True)
class VPNNetworkSettings:
    """Resolved VPN client/relay network settings."""

    client_subnet: str
    client_gateway: str
    relay_subnet: str
    relay_de_address: str
    relay_ru_address: str
    capacity_profile: int
    rotate_enabled: bool
    usable_address_count: int


# START_BLOCK: normalize_subnet
def normalize_subnet(value: str) -> ipaddress.IPv4Network:
    """Normalize a CIDR string to an IPv4Network."""
    network = ipaddress.ip_network(value, strict=False)
    if network.version != 4:
        raise ValueError("Only IPv4 VPN subnets are supported")
    return network
# END_BLOCK: normalize_subnet


# START_BLOCK: derive_gateway
def derive_gateway(client_subnet: str) -> str:
    """Return the first usable host address for the client subnet."""
    network = normalize_subnet(client_subnet)
    hosts = list(network.hosts())
    if len(hosts) < 2:
        raise ValueError("VPN client subnet must contain a gateway and at least one client address")
    return str(hosts[0])
# END_BLOCK: derive_gateway


# START_BLOCK: derive_relay_addresses
def derive_relay_addresses(relay_subnet: str) -> tuple[str, str]:
    """Return default DE/RU relay addresses for a transit subnet."""
    network = normalize_subnet(relay_subnet)
    hosts = list(network.hosts())
    if len(hosts) < 2:
        raise ValueError("VPN relay subnet must contain at least two host addresses")
    return str(hosts[0]), str(hosts[1])
# END_BLOCK: derive_relay_addresses


# START_BLOCK: usable_client_address_count
def usable_client_address_count(client_subnet: str, *, gateway_address: str | None = None) -> int:
    """Count usable client addresses after reserving the gateway address."""
    network = normalize_subnet(client_subnet)
    hosts = {str(host) for host in network.hosts()}
    if not hosts:
        return 0

    gateway = gateway_address or derive_gateway(client_subnet)
    hosts.discard(gateway)
    return len(hosts)
# END_BLOCK: usable_client_address_count


# START_BLOCK: validate_client_capacity
def validate_client_capacity(
    client_subnet: str,
    capacity_profile: int,
    *,
    gateway_address: str | None = None,
) -> int:
    """Validate that a client subnet can satisfy a requested device capacity profile."""
    usable = usable_client_address_count(client_subnet, gateway_address=gateway_address)
    if capacity_profile > 0 and usable < capacity_profile:
        logger.error(
            "[VPNNetwork][validate_capacity][CAPACITY_VALIDATED] selected pool is too small",
            extra={
                "client_subnet": client_subnet,
                "capacity_profile": capacity_profile,
                "usable_address_count": usable,
            },
        )
        raise ValueError(
            f"VPN client subnet {client_subnet} has {usable} usable addresses, "
            f"less than VPN_CAPACITY_PROFILE={capacity_profile}"
        )

    logger.info(
        "[VPNNetwork][validate_capacity][CAPACITY_VALIDATED] client pool capacity validated",
        extra={
            "client_subnet": client_subnet,
            "capacity_profile": capacity_profile,
            "usable_address_count": usable,
        },
    )
    return usable
# END_BLOCK: validate_client_capacity


# START_BLOCK: build_vpn_network_settings
def build_vpn_network_settings(
    *,
    client_subnet: str = DEFAULT_VPN_CLIENT_SUBNET,
    client_gateway: str | None = None,
    relay_subnet: str = DEFAULT_VPN_RELAY_SUBNET,
    relay_de_address: str | None = None,
    relay_ru_address: str | None = None,
    capacity_profile: int = 0,
    rotate_enabled: bool = False,
) -> VPNNetworkSettings:
    """Build a fully resolved and validated VPN network settings object."""
    client_network = normalize_subnet(client_subnet)
    relay_network = normalize_subnet(relay_subnet)
    if client_network.overlaps(relay_network):
        logger.error(
            "[VPNNetwork][validate_overlap][OVERLAP_DETECTED] client and relay subnets overlap",
            extra={"client_subnet": str(client_network), "relay_subnet": str(relay_network)},
        )
        raise ValueError(f"VPN client subnet {client_network} overlaps relay subnet {relay_network}")

    resolved_gateway = client_gateway or derive_gateway(str(client_network))
    gateway_ip = ipaddress.ip_address(resolved_gateway)
    if gateway_ip not in client_network:
        raise ValueError(f"VPN_CLIENT_GATEWAY={resolved_gateway} is outside {client_network}")

    default_de, default_ru = derive_relay_addresses(str(relay_network))
    resolved_de = relay_de_address or default_de
    resolved_ru = relay_ru_address or default_ru
    for label, value in (("VPN_RELAY_DE_ADDRESS", resolved_de), ("VPN_RELAY_RU_ADDRESS", resolved_ru)):
        relay_ip = ipaddress.ip_address(value)
        if relay_ip not in relay_network:
            raise ValueError(f"{label}={value} is outside {relay_network}")
    if resolved_de == resolved_ru:
        raise ValueError("VPN relay DE and RU addresses must be different")

    usable = validate_client_capacity(
        str(client_network),
        int(capacity_profile),
        gateway_address=resolved_gateway,
    )
    settings = VPNNetworkSettings(
        client_subnet=str(client_network),
        client_gateway=resolved_gateway,
        relay_subnet=str(relay_network),
        relay_de_address=resolved_de,
        relay_ru_address=resolved_ru,
        capacity_profile=int(capacity_profile),
        rotate_enabled=bool(rotate_enabled),
        usable_address_count=usable,
    )
    logger.info(
        "[VPNNetwork][load_settings][SUBNET_CONFIGURED] VPN network settings loaded",
        extra={
            "client_subnet": settings.client_subnet,
            "relay_subnet": settings.relay_subnet,
            "capacity_profile": settings.capacity_profile,
            "usable_address_count": settings.usable_address_count,
            "rotate_enabled": settings.rotate_enabled,
        },
    )
    return settings
# END_BLOCK: build_vpn_network_settings


# START_BLOCK: next_client_ip
def next_client_ip(
    used_ips: set[str],
    *,
    client_subnet: str,
    gateway_address: str | None = None,
    capacity_profile: int = 0,
) -> str:
    """Return the first free client IP inside a selected subnet."""
    network = normalize_subnet(client_subnet)
    gateway = gateway_address or derive_gateway(str(network))
    validate_client_capacity(str(network), capacity_profile, gateway_address=gateway)

    for ip in network.hosts():
        candidate = str(ip)
        if candidate == gateway:
            continue
        if candidate not in used_ips:
            return candidate
    raise ValueError("No available IP addresses in VPN subnet")
# END_BLOCK: next_client_ip


# START_BLOCK: choose_reprovision_address
def choose_reprovision_address(
    *,
    existing_address: str,
    used_ips: set[str],
    client_subnet: str,
    rotate_enabled: bool,
    gateway_address: str | None = None,
    capacity_profile: int = 0,
) -> str:
    """Choose reprovision address while guarding against accidental pool migration."""
    network = normalize_subnet(client_subnet)
    existing_ip = ipaddress.ip_address(existing_address)
    if existing_ip not in network and not rotate_enabled:
        logger.warning(
            "[VPNNetwork][migration_guard][ROTATION_REQUIRED] preserving existing address until explicit rotation",
            extra={
                "existing_address": existing_address,
                "client_subnet": str(network),
                "rotate_enabled": rotate_enabled,
            },
        )
        return existing_address
    return next_client_ip(
        used_ips,
        client_subnet=str(network),
        gateway_address=gateway_address,
        capacity_profile=capacity_profile,
    )
# END_BLOCK: choose_reprovision_address
