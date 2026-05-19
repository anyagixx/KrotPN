"""Official MTProxy supervisor behavior tests.

# FILE: backend/tests/test_official_mtproxy_supervisor.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify the Phase-40 official MTProxy supervisor does not restart live sessions on unchanged manifests.
#   SCOPE: Dynamic import of official-mtproxy/secret-control.py, idempotent manifest apply, dead-process restart fallback, and redacted health payload shape.
#   DEPENDS: M-052, M-053
#   LINKS: docs/modules/M-052.xml, docs/modules/M-053.xml, docs/verification/V-M-052.xml
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   _load_supervisor_module - Imports the hyphen-path supervisor module for direct tests.
#   _payload - Builds a one-secret runtime manifest with a valid fingerprint.
#   test_supervisor_skips_restart_for_unchanged_manifest_while_process_runs - Covers idempotent apply.
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added regression coverage for unchanged manifest restarts killing Telegram sessions.
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


# START_BLOCK_SUPERVISOR_TEST_HELPERS
def _load_supervisor_module():
    module_path = ROOT / "official-mtproxy" / "secret-control.py"
    spec = importlib.util.spec_from_file_location("krotpn_official_mtproxy_secret_control", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _payload(secret_hex: str) -> dict[str, object]:
    fingerprint = hashlib.sha256(bytes.fromhex(secret_hex)).hexdigest()[:16]
    return {
        "generated_at": "2026-05-19T00:00:00+00:00",
        "secrets": [
            {
                "assignment_id": 1,
                "user_id": 2,
                "sni": "u-idempotent.krotpn.xyz",
                "secret_hex": secret_hex,
                "secret_fingerprint": fingerprint,
            }
        ],
    }


class _FakeProcess:
    def __init__(self, *, running: bool) -> None:
        self.running = running

    def poll(self) -> int | None:
        return None if self.running else 1
# END_BLOCK_SUPERVISOR_TEST_HELPERS


# START_BLOCK_SUPERVISOR_IDEMPOTENCY_TESTS
def test_supervisor_skips_restart_for_unchanged_manifest_while_process_runs(tmp_path, monkeypatch):
    module = _load_supervisor_module()
    config = module.RuntimeConfig(
        data_dir=tmp_path,
        binary_path="/usr/local/bin/mtproto-proxy",
        proxy_port=443,
        stats_port=2398,
        workers=1,
        policy_bind_ip="127.0.0.1",
        policy_port=18080,
        policy_token="test-policy-token",
        manifest_path=tmp_path / "secrets.json",
        proxy_secret_path=tmp_path / "proxy-secret",
        proxy_config_path=tmp_path / "proxy-multi.conf",
        proxy_user="mtproxy",
        proxy_tag=None,
        nat_info="172.17.0.1:203.0.113.10",
        http_stats_enabled=True,
    )
    supervisor = module.MTProxySupervisor(config)
    restarts = {"count": 0}
    monkeypatch.setattr(
        supervisor,
        "fetch_stats_locked",
        lambda: module.MTProxyStats(
            ready_targets=17,
            active_targets=19,
            total_special_connections=0,
        ),
    )

    def fake_restart() -> None:
        restarts["count"] += 1
        supervisor._process = _FakeProcess(running=True)
        supervisor._last_error = None

    monkeypatch.setattr(supervisor, "restart_proxy_locked", fake_restart)

    first = supervisor.apply_manifest(_payload("1" * 32))
    second = supervisor.apply_manifest(_payload("1" * 32))

    assert restarts["count"] == 1
    assert first["manifest_fingerprint"] == second["manifest_fingerprint"]
    assert second["status"] == "healthy"

    supervisor._process = _FakeProcess(running=False)
    third = supervisor.apply_manifest(_payload("1" * 32))

    assert restarts["count"] == 2
    assert third["process_running"] is True
# END_BLOCK_SUPERVISOR_IDEMPOTENCY_TESTS
