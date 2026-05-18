"""Phase-32 domain TLS edge static verification.

# FILE: backend/tests/test_domain_tls_edge_static.py
# VERSION: 1.4.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify krotpn.xyz domain/TLS/shared-443 edge contract without touching live DNS
#   SCOPE: Settings defaults, nginx redirect/fallback config, tracked env template, Phase-35/37/38 scoped deploy/install guard, rollback runbook
#   DEPENDS: M-046, M-001, M-012, M-044, M-048, M-050
#   LINKS: V-M-046, V-M-048, V-M-050, docs/modules/M-046.xml, docs/modules/M-048.xml, docs/modules/M-050.xml, docs/plans/Phase-32.xml, docs/plans/Phase-35.xml, docs/plans/Phase-38.xml
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   test_settings_defaults_are_canonical_krotpn_xyz - M-001 edge settings contract
#   test_nginx_forces_canonical_domain_http_to_https - M-046 redirect contract
#   test_nginx_keeps_private_https_fallback_and_tls_paths - M-046 private HTTPS fallback and TLS path contract
#   test_nginx_exposes_admin_panel_on_public_8443 - M-046 public admin panel port contract
#   test_env_example_declares_domain_tls_contract - Operator env template contract
#   test_compose_routes_public_443_to_sni_router - M-012 shared 443 owner guard with Phase-38 RU SNI router
#   test_deploy_install_changes_are_phase35_scoped - Protected deploy/install guard with approved M-048 exception
#   test_cutover_runbook_contains_live_smoke_and_rollback_gates - Live-required handoff guard
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.4.0 - Guard public admin 8443 separately from private SNI-router fallback 9443.
#   LAST_CHANGE: v1.3.0 - Updated static edge guards for Phase-38 RU SNI router public 443 ownership.
#   LAST_CHANGE: v1.2.0 - Updated static edge guards for Phase-37 MTProto runtime owning public 443.
#   LAST_CHANGE: v1.1.0 - Allowed approved Phase-35 installer wildcard TLS surface changes while preserving edge guards
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
    assert settings.edge_mtproto_mode == "de-backed"


def test_nginx_forces_canonical_domain_http_to_https():
    nginx = _read("nginx/nginx.conf")

    assert "[M-046][nginx_contract][HTTP_TO_HTTPS_REDIRECT]" in nginx
    assert "listen 80;" in nginx
    assert "server_name krotpn.xyz www.krotpn.xyz;" in nginx
    assert "return 301 https://krotpn.xyz$request_uri;" in nginx


def test_nginx_keeps_private_https_fallback_and_tls_paths():
    nginx = _read("nginx/nginx.conf")

    assert "[M-046][edge_contract][DOMAIN_SETTINGS]" in nginx
    assert "[M-046][edge_router][HTTPS_FALLBACK]" in nginx
    assert "[M-046][edge_router][SNI_CLASSIFY]" in nginx
    assert "[M-046][edge_router][MTPROTO_ROUTE]" in nginx
    assert "listen 127.0.0.1:9443 ssl;" in nginx
    assert "listen 443 ssl;" not in nginx
    assert "server_name krotpn.xyz *.krotpn.xyz;" in nginx
    assert "ssl_certificate /etc/nginx/ssl/server.crt;" in nginx
    assert "ssl_certificate_key /etc/nginx/ssl/server.key;" in nginx
    assert "proxy_set_header X-Forwarded-Proto $scheme;" in nginx
    assert "Strict-Transport-Security" in nginx


def test_nginx_exposes_admin_panel_on_public_8443():
    nginx = _read("nginx/nginx.conf")
    admin_block = nginx.split("# START_BLOCK_ADMIN_PUBLIC_HTTPS", 1)[1].split(
        "# END_BLOCK_ADMIN_PUBLIC_HTTPS", 1
    )[0]

    assert "[M-046][edge_router][ADMIN_PUBLIC_HTTPS]" in nginx
    assert "listen 8443 ssl default_server;" in admin_block
    assert "server_name krotpn.xyz www.krotpn.xyz _;" in admin_block
    assert "location /api/" in admin_block
    assert "proxy_pass http://backend;" in admin_block
    assert "location / {" in admin_block
    assert "proxy_pass http://frontend-admin;" in admin_block


def test_env_example_declares_domain_tls_contract():
    env_example = _read(".env.example")

    assert "FRONTEND_URL=https://krotpn.xyz" in env_example
    assert "EMAIL_VERIFICATION_URL_BASE=https://krotpn.xyz/verify-email" in env_example
    assert "MTPROTO_BASE_DOMAIN=krotpn.xyz" in env_example
    assert "MTPROTO_PROXY_PORT=443" in env_example
    assert "EDGE_PUBLIC_DOMAIN=krotpn.xyz" in env_example
    assert "EDGE_CANONICAL_HOST=krotpn.xyz" in env_example
    assert "EDGE_TLS_CERTIFICATE_MODE=operator-wildcard" in env_example
    assert "EDGE_SHARED_443_ENABLED=true" in env_example
    assert "EDGE_HTTPS_FALLBACK_PORT=9443" in env_example
    assert "MTPROTO_RUNTIME_POLICY_URL=http://172.29.255.1:18080/krotpn/mtproto/policy" in env_example
    assert "MTPROTO_RUNTIME_TOKEN=" in env_example
    assert "MTPROTO_POLICY_BIND_IP=172.29.255.1" in env_example
    assert "EDGE_MTPROTO_MODE=de-backed" in env_example
    assert "SNI_ROUTER_CONF_PATH=./deploy/haproxy-phase38.cfg" in env_example


def test_compose_routes_public_443_to_sni_router():
    compose = _read("docker-compose.yml")

    assert "container_name: krotpn-nginx" in compose
    assert "container_name: krotpn-sni-router" in compose
    assert "haproxy:2.9-alpine" in compose
    assert "SNI_ROUTER_CONF_PATH" in compose
    assert "container_name: krotpn-mtproto-edge" in compose
    assert "context: ./mtproto-runtime" in compose
    assert "profiles:" in compose
    assert "local-mtproto-edge" in compose
    assert "PROXY_PORT: ${MTPROTO_PROXY_PORT:-443}" in compose
    assert "PORTAL_DOMAIN_FRONTING: 127.0.0.1:${EDGE_HTTPS_FALLBACK_PORT:-9443}" in compose
    assert "KROTPN_MTPROTO_POLICY_TOKEN" in compose
    assert 'user: "0:0"' in compose
    assert "NET_BIND_SERVICE" in compose
    assert "NGINX_CONF_PATH" in compose
    assert "${NGINX_CONF_PATH:-./nginx/nginx.conf}:/etc/nginx/nginx.conf:ro" in compose
    assert "./ssl:/etc/nginx/ssl:ro" in compose
    assert "network_mode: host" in compose
    assert compose.count("container_name: krotpn-nginx") == 1
    assert compose.count("container_name: krotpn-sni-router") == 1
    assert compose.count("container_name: krotpn-mtproto-edge") == 1


def test_deploy_install_changes_are_phase35_scoped():
    approved_phase35_surface = {
        ".env.example",
        "docker-compose.yml",
        "install.sh",
        "deploy/deploy-on-server.sh",
        "deploy/haproxy-phase38.cfg",
        "deploy/mtproto-de-compose.yml",
        "nginx/nginx.conf",
        "backend/app/core/config.py",
        "backend/app/mtproto/runtime_bridge.py",
        "backend/tests/test_domain_tls_edge_static.py",
        "backend/tests/test_deploy_phase38_static.py",
        "backend/tests/test_mtproto_de_edge_contract.py",
        "mtproto-runtime/src/kpproton_runtime.erl",
        "mtproto-runtime/src/kpproton_policy_handler.erl",
        "mtproto-runtime/src/kpproton_web.erl",
        "mtproto-runtime/apps/kpproton_proxy/src/mtproto/kpproton_proxy_bridge.erl",
        "scripts/phase32-edge-contract-smoke.mjs",
        "scripts/phase34-mtproto-stabilization-smoke.mjs",
        "scripts/phase35-installer-wildcard-tls-smoke.mjs",
        "scripts/phase37-mtproto-runtime-smoke.mjs",
        "scripts/phase38-de-mtproto-edge-smoke.mjs",
    }
    protected_changes = [
        path for path in _changed_files()
        if (
            path == "install.sh"
            or path == "docker-compose.yml"
            or path == ".env.example"
            or path.startswith("deploy/")
            or path.startswith("nginx/")
            or path.startswith("mtproto-runtime/")
            or path.startswith("scripts/phase")
        )
    ]
    unexpected = [path for path in protected_changes if path not in approved_phase35_surface]

    assert unexpected == []
    if protected_changes:
        assert "M-048" in _read("docs/graph-index.xml")
        assert "Phase-38" in _read("docs/plan-index.xml")


def test_cutover_runbook_contains_live_smoke_and_rollback_gates():
    runbook = _read("docs/edge/PHASE-32-CUTOVER.xml")

    assert "[M-046][edge_contract][ROLLBACK_READY]" in runbook
    assert "krotpn.xyz" in runbook
    assert "*.krotpn.xyz" in runbook
    assert "HTTP_TO_HTTPS_REDIRECT" in runbook
    assert "MTPROTO_ROUTE" in runbook
    assert "operator-live" in runbook
# END_BLOCK_PHASE32_EDGE_STATIC_TESTS
