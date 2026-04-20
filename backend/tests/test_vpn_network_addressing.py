# FILE: backend/tests/test_vpn_network_addressing.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify configurable VPN network addressing and 500/1000-device capacity helpers
#   SCOPE: Subnet derivation, capacity rejection, allocation bounds, and migration guard behavior
#   DEPENDS: M-032 (vpn-network-addressing-capacity)
#   LINKS: V-M-032
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   test_build_vpn_network_settings_derives_recommended_172_subnets - Fresh deploy defaults resolve to 172.29 pools
#   test_capacity_profile_1000_rejects_24_and_accepts_22 - Capacity gate rejects too-small client pools
#   test_next_client_ip_skips_gateway_and_used_addresses - Allocator stays inside selected subnet
#   test_choose_reprovision_address_preserves_existing_address_without_rotation - Migration guard avoids silent renumbering
#   test_choose_reprovision_address_rotates_when_explicitly_enabled - Explicit rotation allocates from new pool
# END_MODULE_MAP

import pytest

from app.core.vpn_network import (
    build_vpn_network_settings,
    choose_reprovision_address,
    next_client_ip,
    validate_client_capacity,
)


def test_build_vpn_network_settings_derives_recommended_172_subnets():
    network = build_vpn_network_settings(
        client_subnet="172.29.0.0/22",
        relay_subnet="172.29.255.0/30",
        capacity_profile=1000,
    )

    assert network.client_subnet == "172.29.0.0/22"
    assert network.client_gateway == "172.29.0.1"
    assert network.relay_subnet == "172.29.255.0/30"
    assert network.relay_de_address == "172.29.255.1"
    assert network.relay_ru_address == "172.29.255.2"
    assert network.usable_address_count >= 1000


def test_capacity_profile_1000_rejects_24_and_accepts_22():
    with pytest.raises(ValueError, match="less than VPN_CAPACITY_PROFILE=1000"):
        validate_client_capacity("172.29.0.0/24", 1000)

    assert validate_client_capacity("172.29.0.0/22", 1000) >= 1000


def test_next_client_ip_skips_gateway_and_used_addresses():
    address = next_client_ip(
        {"172.29.0.2", "172.29.0.3"},
        client_subnet="172.29.0.0/22",
        gateway_address="172.29.0.1",
        capacity_profile=1000,
    )

    assert address == "172.29.0.4"


def test_choose_reprovision_address_preserves_existing_address_without_rotation():
    address = choose_reprovision_address(
        existing_address="10.10.0.20",
        used_ips=set(),
        client_subnet="172.29.0.0/22",
        rotate_enabled=False,
        capacity_profile=1000,
    )

    assert address == "10.10.0.20"


def test_choose_reprovision_address_rotates_when_explicitly_enabled():
    address = choose_reprovision_address(
        existing_address="10.10.0.20",
        used_ips=set(),
        client_subnet="172.29.0.0/22",
        rotate_enabled=True,
        capacity_profile=1000,
    )

    assert address == "172.29.0.2"
