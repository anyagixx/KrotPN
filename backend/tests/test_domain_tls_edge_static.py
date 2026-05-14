"""Phase-32 domain TLS edge static verification.

# FILE: backend/tests/test_domain_tls_edge_static.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify krotpn.xyz domain/TLS/shared-443 edge contract without touching live DNS
#   SCOPE: Settings defaults, nginx redirect/fallback config, tracked env template, protected deploy/install guard, rollback runbook
#   DEPENDS: M-046, M-001, M-012, M-044
#   LINKS: V-M-046, docs/modules/M-046.xml, docs/plans/Phase-32.xml
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   test_settings_defaults_are_canonical_krotpn_xyz - M-001 edge settings contract
#   test_nginx_forces_canonical_domain_http_to_https - M-046 redirect contract
#   test_nginx_keeps_https_fallback_and_tls_paths - M-046 HTTPS fallback and TLS path contract
#   test_env_example_declares_domain_tls_contract - Operator env template contract
#   test_compose_keeps_nginx_as_only_public_edge_owner - M-012 single 443 owner guard
#   test_deploy_install_scripts_are_not_modified - Protected deploy/install guard
#   test_cutover_runbook_contains_live_smoke_and_rollback_gates - Live-required handoff guard
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-32 static edge verification
# END_CHANGE_SUMMARY
"""

import os
import subprocess
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-with-enough-length")

from app.core.config import Settings


ROOT = Path(__file__).resolve().parents[2]


# START_BLOCK_PHASE32_EDGE_STATIC_HELPERS
def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _changed_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]
# END_BLOCK_PHASE32_EDGE_STATIC_HELPERS


# START_BLOCK_PHASE32_EDGE_STATIC_TESTS
def test_settings_defaults_are_canonical_krotpn_xyz():
    settings = Settings(_env_file=None, secret_key="test-secret-key-with-enough-length")

    assert settings.frontend_url == "https://krotpn.xyz"
    assert settings.mtproto_base_domain == "krotpn.xyz"
    assert settings.mtproto_proxy_port == 443
    assert settings.edge_public_domain == "krotpn.xyz"
    assert settings.edge_canonical_host == "krotpn.xyz"
    assert settings.edge_https_url == "https://krotpn.xyz"
    assert settings.edge_wildcard_domain == "*.krotpn.xyz"
    assert settings.edge_tls_certificate_path == "/etc/nginx/ssl/server.crt"
    assert settings.edge_tls_certificate_key_path == "/etc/nginx/ssl/server.key"
    assert settings.edge_tls_certificate_mode == "operator-wildcard"


def test_nginx_forces_canonical_domain_http_to_https():
    nginx = _read("nginx/nginx.conf")

    assert "[M-046][nginx_contract][HTTP_TO_HTTPS_REDIRECT]" in nginx
    assert "listen 80;" in nginx
    assert "server_name krotpn.xyz www.krotpn.xyz;" in nginx
    assert "return 301 https://krotpn.xyz$request_uri;" in nginx


def test_nginx_keeps_https_fallback_and_tls_paths():
    nginx = _read("nginx/nginx.conf")

    assert "[M-046][edge_contract][DOMAIN_SETTINGS]" in nginx
    assert "[M-046][edge_router][HTTPS_FALLBACK]" in nginx
    assert "[M-046][edge_router][SNI_CLASSIFY]" in nginx
    assert "[M-046][edge_router][MTPROTO_ROUTE]" in nginx
    assert "listen 443 ssl;" in nginx
    assert "server_name krotpn.xyz *.krotpn.xyz;" in nginx
    assert "ssl_certificate /etc/nginx/ssl/server.crt;" in nginx
    assert "ssl_certificate_key /etc/nginx/ssl/server.key;" in nginx
    assert "proxy_set_header X-Forwarded-Proto $scheme;" in nginx
    assert "Strict-Transport-Security" in nginx


def test_env_example_declares_domain_tls_contract():
    env_example = _read(".env.example")

    assert "FRONTEND_URL=https://krotpn.xyz" in env_example
    assert "EMAIL_VERIFICATION_URL_BASE=https://krotpn.xyz/verify-email" in env_example
    assert "MTPROTO_BASE_DOMAIN=krotpn.xyz" in env_example
    assert "MTPROTO_PROXY_PORT=443" in env_example
    assert "EDGE_PUBLIC_DOMAIN=krotpn.xyz" in env_example
    assert "EDGE_CANONICAL_HOST=krotpn.xyz" in env_example
    assert "EDGE_TLS_CERTIFICATE_MODE=operator-wildcard" in env_example
    assert "EDGE_SHARED_443_ENABLED=false" in env_example


def test_compose_keeps_nginx_as_only_public_edge_owner():
    compose = _read("docker-compose.yml")

    assert "container_name: krotpn-nginx" in compose
    assert "./nginx/nginx.conf:/etc/nginx/nginx.conf:ro" in compose
    assert "./ssl:/etc/nginx/ssl:ro" in compose
    assert "network_mode: host" in compose
    assert compose.count("container_name: krotpn-nginx") == 1


def test_deploy_install_scripts_are_not_modified():
    protected_changes = [
        path for path in _changed_files()
        if path == "install.sh" or path.startswith("deploy/")
    ]

    assert protected_changes == []


def test_cutover_runbook_contains_live_smoke_and_rollback_gates():
    runbook = _read("docs/edge/PHASE-32-CUTOVER.xml")

    assert "[M-046][edge_contract][ROLLBACK_READY]" in runbook
    assert "krotpn.xyz" in runbook
    assert "*.krotpn.xyz" in runbook
    assert "HTTP_TO_HTTPS_REDIRECT" in runbook
    assert "MTPROTO_ROUTE" in runbook
    assert "operator-live" in runbook
# END_BLOCK_PHASE32_EDGE_STATIC_TESTS
