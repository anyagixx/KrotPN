"""Phase-38 deploy surface static verification.

# FILE: backend/tests/test_deploy_phase38_static.py
# VERSION: 1.2.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify Phase-38 deploy files define a DE-backed MTProto runtime and RU SNI router safely.
#   SCOPE: HAProxy SNI map, docker compose port ownership, deploy env wiring, DE runtime compose, private policy bind, and redaction guards.
#   DEPENDS: M-012, M-046, M-048, M-049, M-050
#   LINKS: V-M-012, V-M-046, V-M-048, V-M-050, docs/plans/Phase-38.xml
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   test_haproxy_routes_web_and_mtproto_sni - Verifies public TCP 443 SNI routing contract.
#   test_compose_has_single_default_public_443_owner - Verifies sni-router owns 443 with bind permissions and local edge is profiled.
#   test_deploy_wires_de_runtime_and_private_policy_url - Verifies deploy-generated Phase-38 env and DE runtime startup.
#   test_de_runtime_compose_binds_policy_api_privately - Verifies DE runtime policy API bind and health path.
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.2.0 - Guard DE mtproto_proxy bootstrap against private POLICY_LISTEN_IP binding.
#   LAST_CHANGE: v1.1.0 - Guard low-port HAProxy bind permissions and admin/fallback port separation.
#   LAST_CHANGE: v1.0.0 - Added Phase-38 static deploy verification.
# END_CHANGE_SUMMARY
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


# START_BLOCK_PHASE38_DEPLOY_STATIC_HELPERS
def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")
# END_BLOCK_PHASE38_DEPLOY_STATIC_HELPERS


# START_BLOCK_PHASE38_DEPLOY_STATIC_TESTS
def test_haproxy_routes_web_and_mtproto_sni():
    haproxy = _read("deploy/haproxy-phase38.cfg")

    assert "bind *:443" in haproxy
    assert "[M-050][ru_sni_router][ROUTE_WEB]" in haproxy
    assert "[M-050][ru_sni_router][ROUTE_MTPROTO]" in haproxy
    assert "[M-050][ru_sni_router][ROUTE_UNKNOWN_SNI]" in haproxy
    assert "acl sni_web req.ssl_sni -i krotpn.xyz www.krotpn.xyz" in haproxy
    assert r"^u-[0-9a-f]{12}\.krotpn\.xyz$" in haproxy
    assert "server ru_nginx_9443 127.0.0.1:9443 check" in haproxy
    assert "server de_mtproto_443 127.0.0.1:19443 check" in haproxy
    assert "default_backend web_https_fallback" in haproxy


def test_compose_has_single_default_public_443_owner():
    compose = _read("docker-compose.yml")

    assert "container_name: krotpn-sni-router" in compose
    assert "haproxy:2.9-alpine" in compose
    assert 'user: "0:0"' in compose
    assert "NET_BIND_SERVICE" in compose
    assert "SNI_ROUTER_CONF_PATH" in compose
    assert "container_name: krotpn-mtproto-edge" in compose
    assert "profiles:" in compose
    assert "local-mtproto-edge" in compose
    assert "container_name: krotpn-sni-router" in compose
    assert compose.count("container_name: krotpn-sni-router") == 1


def test_deploy_wires_de_runtime_and_private_policy_url():
    deploy = _read("deploy/deploy-on-server.sh")

    assert "deploy_de_mtproto_runtime" in deploy
    assert "MTPROTO_POLICY_BIND_IP=\"${MTPROTO_POLICY_BIND_IP:-$VPN_RELAY_DE_ADDRESS}\"" in deploy
    assert (
        "MTPROTO_RUNTIME_POLICY_URL=http://${MTPROTO_POLICY_BIND_IP}:${MTPROTO_POLICY_PORT}/krotpn/mtproto/policy"
        in deploy
    )
    assert "EDGE_MTPROTO_MODE=${EDGE_MTPROTO_MODE}" in deploy
    assert "EDGE_MTPROTO_DE_TARGET_HOST=${EDGE_MTPROTO_DE_TARGET_HOST}" in deploy
    assert "EDGE_HTTPS_FALLBACK_PORT=9443" in deploy
    assert "SNI_ROUTER_CONF_PATH=./deploy/haproxy.runtime.cfg" in deploy
    assert "127\\\\.0\\\\.0\\\\.1:19443" in deploy
    assert "ufw allow proto tcp from '${RU_IP}' to any port '${EDGE_MTPROTO_DE_TARGET_PORT}'" in deploy
    assert "[M-050][de_policy_api][DENY_PUBLIC]" in deploy
    assert "generate_or_preserve_secret MTPROTO_BASE_SECRET_HEX" in deploy
    assert "generate_or_preserve_secret MTPROTO_SECRET_SALT" in deploy
    assert "cat \"$TLS_PRIVKEY_PATH\"" not in deploy


def test_de_runtime_compose_binds_policy_api_privately():
    de_compose = _read("deploy/mtproto-de-compose.yml")
    app = _read("mtproto-runtime/src/kpproton_app.erl")
    runtime = _read("mtproto-runtime/src/kpproton_web.erl")
    settings = _read("mtproto-runtime/src/kpproton_runtime.erl")

    assert "container_name: krotpn-mtproto-de-runtime" in de_compose
    assert "POLICY_LISTEN_IP: ${MTPROTO_POLICY_BIND_IP:-127.0.0.1}" in de_compose
    assert "PROXY_LISTEN_IP: 0.0.0.0" in de_compose
    assert "PORTAL_DOMAIN_FRONTING: ${DE_MTPROTO_DOMAIN_FRONTING:-127.0.0.1:9443}" in de_compose
    assert "/krotpn/mtproto/policy/health" in de_compose
    assert 'PolicyListenHost = env_string("POLICY_LISTEN_IP", "127.0.0.1")' in app
    assert 'LocalBootstrapBase = "http://" ++ PolicyListenHost' in app
    assert "POLICY_LISTEN_IP" in runtime
    assert "{ip, PolicyListenIp}" in runtime
    assert "policy_listen_ip/0" in settings
    assert "parse_ip_tuple" in settings
# END_BLOCK_PHASE38_DEPLOY_STATIC_TESTS
