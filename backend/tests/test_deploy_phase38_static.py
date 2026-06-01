"""Phase-41 deploy surface static verification.

# FILE: backend/tests/test_deploy_phase38_static.py
# VERSION: 2.5.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify Phase-41 deploy files define a DE-backed KPprotoN fake-TLS runtime and RU SNI router safely.
#   SCOPE: HAProxy SNI classifier, docker compose port ownership, deploy env wiring, DE KPprotoN runtime compose, private policy bind, wildcard TLS mount, and redaction guards.
#   DEPENDS: M-012, M-046, M-048, M-049, M-050, M-052, M-053, M-065
#   LINKS: V-M-012, V-M-046, V-M-048, V-M-049, V-M-050, V-M-052, V-M-053, V-M-065, docs/plans/Phase-41.xml, docs/plans/Phase-47.xml
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   test_haproxy_routes_web_and_mtproto_sni - Verifies public TCP 443 SNI routing contract.
#   test_compose_has_single_default_public_443_owner - Verifies sni-router owns 443 with bind permissions and local edge is profiled.
#   test_deploy_wires_de_runtime_and_private_policy_url - Verifies deploy-generated Phase-40 env and DE official runtime startup.
#   test_de_runtime_compose_binds_policy_api_privately - Verifies DE KPprotoN runtime policy API bind, health path, and TLS mount.
#   test_de_reboot_recovery_keeps_policy_bind_ip_available - Verifies DE awg0, runtime reboot guards, and idempotent SNI apply.
#   test_official_mtproxy_remains_reference_only - Verifies official MTProxy artifacts are no longer production deploy wiring.
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.5.0 - Guard 4-hex CTA suffix routing while preserving existing 7-hex CTA issued hostnames.
#   LAST_CHANGE: v2.4.0 - Guard Phase-47 CTA-prefixed MTProto hostnames in the RU SNI router ACL.
#   LAST_CHANGE: v2.3.0 - Added static guards for DE awg0 boot persistence and runtime policy-bind wait.
#   LAST_CHANGE: v2.2.0 - Restored deploy static checks for KPprotoN fake-TLS production runtime.
#   LAST_CHANGE: v2.1.0 - Added static guards for stable official MTProxy runtime flags and idempotent manifests.
#   LAST_CHANGE: v2.0.0 - Updated deploy static checks for Phase-40 official MTProxy data-plane.
#   LAST_CHANGE: v1.2.0 - Guard DE mtproto_proxy bootstrap against private POLICY_LISTEN_IP binding.
#   LAST_CHANGE: v1.1.0 - Guard low-port HAProxy bind permissions and admin/fallback port separation.
#   LAST_CHANGE: v1.0.0 - Added Phase-38 static deploy verification.
# END_CHANGE_SUMMARY
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


# START_BLOCK_PHASE40_DEPLOY_STATIC_HELPERS
def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")
# END_BLOCK_PHASE40_DEPLOY_STATIC_HELPERS


# START_BLOCK_PHASE40_DEPLOY_STATIC_TESTS
def test_haproxy_routes_web_and_mtproto_sni():
    haproxy = _read("deploy/haproxy-phase38.cfg")

    assert "bind *:443" in haproxy
    assert "[M-050][ru_sni_router][ROUTE_WEB]" in haproxy
    assert "[M-050][ru_sni_router][ROUTE_MTPROTO]" in haproxy
    assert "[M-050][ru_sni_router][ROUTE_UNKNOWN_SNI]" in haproxy
    assert "acl sni_web req.ssl_sni -i krotpn.xyz www.krotpn.xyz" in haproxy
    assert (
        r"^(u-[0-9a-f]{12}|(kupi-vpn|vpn-tut|beri-vpn|bez-blokirovok|hochu-bystree|krot-vpn)-[0-9a-f]{4}([0-9a-f]{3})?)\.krotpn\.xyz$"
        in haproxy
    )
    assert "hochu-bystree" in haproxy
    assert "krot-vpn" in haproxy
    assert "use_backend mtproto_de_runtime if sni_mtproto" in haproxy
    assert "default_backend mtproto_de_runtime" not in haproxy
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
    assert "haproxy-phase38.cfg" in compose
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
    assert "mtproto-runtime" in deploy
    assert "krotpn-mtproto-runtime.tgz" in deploy
    assert "/opt/KrotPN/ssl/server.crt" in deploy
    assert "/opt/KrotPN/ssl/server.key" in deploy
    assert "DE_MTPROTO_DOMAIN_FRONTING=${domain_fronting_target}" in deploy
    assert "[M-050][de_policy_api][DENY_PUBLIC]" in deploy
    assert "generate_or_preserve_secret MTPROTO_BASE_SECRET_HEX" in deploy
    assert "generate_or_preserve_secret MTPROTO_SECRET_SALT" in deploy
    assert "generate_or_preserve_secret MTPROTO_AD_TAG" in deploy
    assert "cat \"$TLS_PRIVKEY_PATH\"" not in deploy


def test_de_runtime_compose_binds_policy_api_privately():
    de_compose = _read("deploy/mtproto-de-compose.yml")

    assert "container_name: krotpn-mtproto-de-runtime" in de_compose
    assert "context: ./mtproto-runtime" in de_compose
    assert "POLICY_LISTEN_IP: ${MTPROTO_POLICY_BIND_IP:-127.0.0.1}" in de_compose
    assert "PROXY_PORT: ${MTPROTO_DE_RUNTIME_PORT:-443}" in de_compose
    assert "PROXY_SECRET_HEX: ${MTPROTO_BASE_SECRET_HEX:?MTPROTO_BASE_SECRET_HEX must be set}" in de_compose
    assert "PROXY_SECRET_SALT: ${MTPROTO_SECRET_SALT:?MTPROTO_SECRET_SALT must be set}" in de_compose
    assert "PROXY_AD_TAG: ${MTPROTO_AD_TAG:-00000000000000000000000000000000}" in de_compose
    assert "PORTAL_DOMAIN_FRONTING: ${DE_MTPROTO_DOMAIN_FRONTING:-127.0.0.1:18443}" in de_compose
    assert "TLS_CERT_PATH: /certs/krotpn/server.crt" in de_compose
    assert "TLS_KEY_PATH: /certs/krotpn/server.key" in de_compose
    assert "./ssl:/certs/krotpn:ro" in de_compose
    assert "KROTPN_MTPROTO_POLICY_TOKEN" in de_compose
    assert "/krotpn/mtproto/policy/health" in de_compose


def test_de_reboot_recovery_keeps_policy_bind_ip_available():
    deploy = _read("deploy/deploy-on-server.sh")
    deploy_all = _read("deploy/deploy-all.sh")
    entrypoint = _read("mtproto-runtime/docker/entrypoint.sh")
    proxy_bridge = _read("mtproto-runtime/apps/kpproton_proxy/src/mtproto/kpproton_proxy_bridge.erl")

    assert "systemctl enable awg-quick@awg0" in deploy
    assert "[M-050][de_awg0_boot_persistence][ENABLE_AWG_SERVICE]" in deploy
    assert "systemctl enable awg-quick@awg0" in deploy_all
    assert "wait_for_policy_listen_ip" in entrypoint
    assert "POLICY_LISTEN_IP_WAIT_SECONDS" in entrypoint
    assert "WAIT_POLICY_IP" in entrypoint
    assert "/proc/net/fib_trie" in entrypoint
    assert "mtp_policy_table:del(personal_domains, tls_domain, SniDomain)" in proxy_bridge


def test_official_mtproxy_remains_reference_only():
    supervisor = _read("official-mtproxy/secret-control.py")
    deploy = _read("deploy/deploy-on-server.sh")
    de_compose = _read("deploy/mtproto-de-compose.yml")

    assert "[OfficialMTProxy][manifest][UNCHANGED]" in supervisor
    assert "official-mtproxy" not in de_compose
    assert "krotpn-official-mtproxy.tgz" not in deploy
    assert "MTPROXY_NAT_INFO" not in deploy
    assert "/krotpn/mtproto/policy/secrets/apply" not in de_compose
# END_BLOCK_PHASE40_DEPLOY_STATIC_TESTS
