# FILE: backend/tests/test_deploy_network_subnets_static.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Static verification for deploy-time configurable VPN client and relay subnets
#   SCOPE: Deploy script helper wiring, env propagation, old 10.10/10.200 removal, and shell syntax checks
#   DEPENDS: M-032 (vpn-network-addressing-capacity), M-012 (deploy-surface)
#   LINKS: V-M-032
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   test_deploy_scripts_use_vpn_network_helper - Ensures deploy scripts source/copy the network helper
#   test_deploy_scripts_do_not_hardcode_legacy_10_networks - Blocks old client/relay CIDR assumptions
#   test_deploy_env_exports_network_capacity_settings - Ensures backend .env receives network settings
#   test_vpn_network_helper_has_required_markers_and_guards - Checks deploy telemetry and migration guard markers
#   test_vpn_network_helper_preserves_legacy_24_without_implicit_capacity_profile - Checks safe upgrade behavior
# END_MODULE_MAP

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_deploy_scripts_use_vpn_network_helper():
    deploy_on_server = read("deploy/deploy-on-server.sh")
    deploy_all = read("deploy/deploy-all.sh")

    for script in (deploy_on_server, deploy_all):
        assert 'source "${SCRIPT_DIR}/lib/vpn-network.sh"' in script
        assert "vpn_network_resolve" in script
        assert "vpn_network_validate" in script
        assert "VPN_CLIENT_SUBNET" in script
        assert "VPN_RELAY_SUBNET" in script


def test_deploy_scripts_do_not_hardcode_legacy_10_networks():
    combined = "\n".join(
        [
            read("deploy/deploy-on-server.sh"),
            read("deploy/deploy-all.sh"),
        ]
    )

    assert "10.10.0.0/24" not in combined
    assert "10.10.0.1/24" not in combined
    assert "10.200.0.0/24" not in combined
    assert "10.200.0.1" not in combined
    assert "10.200.0.2" not in combined


def test_deploy_env_exports_network_capacity_settings():
    combined = "\n".join(
        [
            read("install.sh"),
            read("deploy/deploy-on-server.sh"),
            read("deploy/deploy-all.sh"),
            read(".env.example"),
            read(".env.production"),
        ]
    )

    for expected in (
        "VPN_CLIENT_SUBNET=172.29.0.0/22",
        "VPN_CLIENT_GATEWAY=172.29.0.1",
        "VPN_RELAY_SUBNET=172.29.255.0/30",
        "VPN_RELAY_DE_ADDRESS=172.29.255.1",
        "VPN_RELAY_RU_ADDRESS=172.29.255.2",
        "VPN_CAPACITY_PROFILE=1000",
        "VPN_NETWORK_ROTATE",
    ):
        assert expected in combined


def test_vpn_network_helper_has_required_markers_and_guards():
    helper = read("deploy/lib/vpn-network.sh")

    assert "CLIENT_SUBNET_APPLIED" in helper
    assert "RELAY_SUBNET_APPLIED" in helper
    assert "OVERLAP_DETECTED" in helper
    assert "CAPACITY_VALIDATED" in helper
    assert "ROTATION_REQUIRED" in helper
    assert "fresh KrotPN deployment must not use 10.0.0.0/8 tunnel networks" in helper


def test_vpn_network_helper_preserves_legacy_24_without_implicit_capacity_profile(tmp_path):
    awg0 = tmp_path / "awg0.conf"
    awg_client = tmp_path / "awg-client.conf"
    awg0.write_text("[Interface]\nAddress = 10.10.0.1/24\n", encoding="utf-8")
    awg_client.write_text("[Interface]\nAddress = 10.200.0.2/24\n", encoding="utf-8")

    result = subprocess.run(
        [
            "bash",
            "-c",
            (
                "source deploy/lib/vpn-network.sh; "
                f"vpn_network_resolve {awg0} {awg_client} >/dev/null; "
                "vpn_network_env_lines"
            ),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "VPN_CLIENT_SUBNET=10.10.0.0/24" in result.stdout
    assert "VPN_RELAY_SUBNET=10.200.0.0/24" in result.stdout
    assert "VPN_CAPACITY_PROFILE=0" in result.stdout
