# FILE: backend/tests/test_vpn_stealth_config.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify backend AWG client config rendering uses deploy-time profile and nullable PSK
#   SCOPE: AmneziaWGManager rendering and ConfigMixin encrypted preshared-key propagation
#   DEPENDS: M-003 (vpn), M-030 (awg-stealth-obfuscation)
#   LINKS: V-M-030
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   test_amneziawg_manager_loads_profile_from_awg0_conf - Existing RU awg0 profile is preserved
#   test_create_client_config_renders_profile_and_preshared_key - Raw config includes profile and PSK
#   test_config_mixin_passes_preshared_key_only_when_present - Legacy NULL-PSK clients still render
# END_MODULE_MAP

from datetime import datetime

import pytest

from app.vpn import config as vpn_config_module
from app.vpn.amneziawg import AmneziaWGManager
from app.vpn.config import ConfigMixin
from app.vpn.models import VPNClient, VPNNode, VPNServer


PROFILE_LINES = """Jc = 6
Jmin = 45
Jmax = 150
S1 = 88
S2 = 99
H1 = 100000001
H2 = 100000002
H3 = 100000003
H4 = 100000004
"""


def test_amneziawg_manager_loads_profile_from_awg0_conf(tmp_path):
    (tmp_path / "awg0.conf").write_text(f"[Interface]\n{PROFILE_LINES}", encoding="utf-8")

    manager = AmneziaWGManager(config_dir=str(tmp_path))

    assert manager.obfuscation == {
        "jc": 6,
        "jmin": 45,
        "jmax": 150,
        "s1": 88,
        "s2": 99,
        "h1": 100000001,
        "h2": 100000002,
        "h3": 100000003,
        "h4": 100000004,
    }


def test_create_client_config_renders_profile_and_preshared_key(tmp_path):
    manager = AmneziaWGManager(config_dir=str(tmp_path))
    manager.obfuscation = {
        "jc": 6,
        "jmin": 45,
        "jmax": 150,
        "s1": 88,
        "s2": 99,
        "h1": 100000001,
        "h2": 100000002,
        "h3": 100000003,
        "h4": 100000004,
    }

    config = manager.create_client_config(
        private_key="client-private",
        address="10.10.0.2",
        server_public_key="server-public",
        endpoint="203.0.113.10",
        preshared_key="client-psk",
    )

    assert "PresharedKey = client-psk" in config
    assert "Jc = 6" in config
    assert "Jmax = 150" in config
    assert "H4 = 100000004" in config


class DummyConfigService(ConfigMixin):
    def __init__(self):
        self.wg = DummyWG()

    async def get_route(self, route_id):
        return None

    async def get_node(self, node_id):
        return VPNNode(
            id=node_id,
            name="RU Entry Node",
            role="entry",
            country_code="RU",
            location="Russia",
            endpoint="203.0.113.10",
            public_key="entry-public",
            is_entry_node=True,
            is_exit_node=False,
        )

    async def get_server(self, server_id):
        return VPNServer(
            id=server_id,
            name="legacy",
            location="Russia",
            endpoint="203.0.113.10",
            public_key="legacy-public",
        )


class DummyWG:
    def __init__(self):
        self.calls = []

    def create_client_config(self, **kwargs):
        self.calls.append(kwargs)
        return "[Interface]\n[Peer]\n"


@pytest.mark.asyncio
async def test_config_mixin_passes_preshared_key_only_when_present(monkeypatch):
    service = DummyConfigService()
    decryptions = {
        "private-enc": "private-plain",
        "psk-enc": "psk-plain",
    }
    monkeypatch.setattr(vpn_config_module, "decrypt_data", lambda value: decryptions[value])

    client = VPNClient(
        id=1,
        user_id=10,
        server_id=5,
        entry_node_id=10,
        public_key="client-public",
        private_key_enc="private-enc",
        preshared_key_enc="psk-enc",
        address="10.10.0.2",
        created_at=datetime(2026, 4, 18),
    )

    await service.get_client_config(client)

    assert service.wg.calls[0]["private_key"] == "private-plain"
    assert service.wg.calls[0]["preshared_key"] == "psk-plain"

    legacy_client = client.model_copy(update={"preshared_key_enc": None})
    await service.get_client_config(legacy_client)

    assert "preshared_key" not in service.wg.calls[1]
