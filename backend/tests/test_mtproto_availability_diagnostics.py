"""Phase-39 MTProto availability diagnostics tests.

# FILE: backend/tests/test_mtproto_availability_diagnostics.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify redacted MTProto availability diagnostics and Telegram web-link helper behavior.
#   SCOPE: SNI masking, proxy-link redaction, safe fingerprints, and primary https://t.me/proxy link assembly.
#   DEPENDS: M-051, M-045, M-043
#   LINKS: V-M-051
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   test_mask_sni_preserves_domain_without_full_personal_label - SNI redaction coverage.
#   test_redact_proxy_text_removes_full_links_and_fake_tls_secrets - Secret redaction coverage.
#   test_build_telegram_web_link_uses_owner_values - Primary user action link coverage.
#   test_safe_fingerprint_is_stable_and_non_secret - Operator correlation fingerprint coverage.
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-39 diagnostics unit tests.
# END_CHANGE_SUMMARY
"""

from app.mtproto.availability import (
    build_telegram_web_link,
    mask_sni,
    redact_proxy_text,
    safe_fingerprint,
)


SECRET = "ee" + ("a" * 32) + "752d3031323334353637383961622e6b726f74706e2e78797a"
SNI = "u-0123456789ab.krotpn.xyz"


# START_BLOCK_PHASE39_AVAILABILITY_DIAGNOSTICS
def test_mask_sni_preserves_domain_without_full_personal_label():
    masked = mask_sni(SNI)

    assert masked == "u-01...89ab.krotpn.xyz"
    assert SNI not in masked
    assert masked.endswith(".krotpn.xyz")


def test_redact_proxy_text_removes_full_links_and_fake_tls_secrets():
    text = (
        f"open tg://proxy?server={SNI}&port=443&secret={SECRET} "
        f"or https://t.me/proxy?server={SNI}&port=443&secret={SECRET} "
        f"raw={SECRET}"
    )

    redacted = redact_proxy_text(text)

    assert "tg://proxy" not in redacted
    assert "https://t.me/proxy" not in redacted
    assert SECRET not in redacted
    assert "<redacted-mtproto-link>" in redacted
    assert "<redacted-mtproto-secret>" in redacted


def test_build_telegram_web_link_uses_owner_values():
    link = build_telegram_web_link(SNI.upper(), 443, SECRET.upper())

    assert link.startswith("https://t.me/proxy?")
    assert "server=u-0123456789ab.krotpn.xyz" in link
    assert "port=443" in link
    assert f"secret={SECRET}" in link


def test_safe_fingerprint_is_stable_and_non_secret():
    first = safe_fingerprint(SECRET)
    second = safe_fingerprint(SECRET)

    assert first == second
    assert len(first) == 12
    assert first != SECRET[:12]
    assert SECRET not in first
# END_BLOCK_PHASE39_AVAILABILITY_DIAGNOSTICS
