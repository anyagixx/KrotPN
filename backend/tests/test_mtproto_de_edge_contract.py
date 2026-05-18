"""Phase-38 DE-backed MTProto edge settings contract tests.

# FILE: backend/tests/test_mtproto_de_edge_contract.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify backend Settings accept only private Phase-38 MTProto policy API targets.
#   SCOPE: Private DE policy URL, policy bind IP, SNI-router DE target settings, and unsafe URL rejection.
#   DEPENDS: M-001, M-044, M-050
#   LINKS: V-M-044, V-M-050, docs/modules/M-050.xml
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   test_private_de_policy_url_is_allowed - Allows RU backend to target DE policy API over the relay subnet.
#   test_public_or_wildcard_policy_url_is_rejected - Rejects public/wildcard policy URLs.
#   test_phase38_edge_target_settings_are_validated - Covers SNI-router DE target settings.
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-38 private DE policy URL and edge target settings coverage.
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

os.environ.setdefault("SECRET_KEY", "test-secret-key-with-enough-length")

from app.core.config import Settings


SECRET_KEY = "test-secret-key-with-enough-length"
RUNTIME_TOKEN = "test-runtime-token-with-enough-length"


# START_BLOCK_PHASE38_SETTINGS_CONTRACT
def test_private_de_policy_url_is_allowed():
    settings = Settings(
        _env_file=None,
        secret_key=SECRET_KEY,
        mtproto_runtime_policy_url="http://172.29.255.1:18080/krotpn/mtproto/policy",
        mtproto_runtime_token=RUNTIME_TOKEN,
        mtproto_policy_bind_ip="172.29.255.1",
    )

    assert (
        settings.mtproto_runtime_policy_url
        == "http://172.29.255.1:18080/krotpn/mtproto/policy"
    )
    assert settings.mtproto_policy_bind_ip == "172.29.255.1"


@pytest.mark.parametrize(
    "policy_url",
    [
        "https://172.29.255.1:18080/krotpn/mtproto/policy",
        "http://0.0.0.0:18080/krotpn/mtproto/policy",
        "http://8.8.8.8:18080/krotpn/mtproto/policy",
        "http://de-runtime.krotpn.xyz:18080/krotpn/mtproto/policy",
        "http://172.29.255.1:18080/unsafe",
    ],
)
def test_public_or_wildcard_policy_url_is_rejected(policy_url: str):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            secret_key=SECRET_KEY,
            mtproto_runtime_policy_url=policy_url,
            mtproto_runtime_token=RUNTIME_TOKEN,
        )


def test_phase38_edge_target_settings_are_validated():
    settings = Settings(
        _env_file=None,
        secret_key=SECRET_KEY,
        edge_mtproto_mode="de-backed",
        edge_mtproto_de_target_host="203.0.113.10",
        edge_mtproto_de_target_port=443,
        sni_router_conf_path="./deploy/haproxy.runtime.cfg",
    )

    assert settings.edge_mtproto_mode == "de-backed"
    assert settings.edge_mtproto_de_target_host == "203.0.113.10"
    assert settings.edge_mtproto_de_target_port == 443
    assert settings.sni_router_conf_path == "./deploy/haproxy.runtime.cfg"
# END_BLOCK_PHASE38_SETTINGS_CONTRACT
