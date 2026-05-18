"""Secret-free MTProto availability diagnostics helpers.

# FILE: backend/app/mtproto/availability.py
# VERSION: 1.0.0
# ROLE: UTILITY
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Provide redacted MTProto availability diagnostics and Telegram web-link helpers.
#   SCOPE: SNI masking, safe fingerprints, proxy-link redaction, and https://t.me/proxy link assembly.
#   DEPENDS: M-043, M-045, M-051
#   LINKS: M-051, V-M-051
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   mask_sni - Hide user-specific SNI label material while preserving route context.
#   safe_fingerprint - Produce a short non-secret fingerprint for correlation.
#   redact_proxy_text - Remove MTProto secrets and full proxy links from diagnostic text.
#   build_telegram_web_link - Build the primary https://t.me/proxy user action link.
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-39 redacted availability diagnostics helpers.
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlencode


_PROXY_LINK_RE = re.compile(r"(?:tg://proxy|https://t\.me/proxy)\?[^\s\"'<>]+", re.IGNORECASE)
_SECRET_PARAM_RE = re.compile(r"([?&]secret=)[^&\s\"'<>]+", re.IGNORECASE)
_FAKE_TLS_SECRET_RE = re.compile(r"\bee[0-9a-f]{48,512}\b", re.IGNORECASE)


# START_CONTRACT: mask_sni
#   PURPOSE: Mask personal SNI labels without losing domain/route context.
#   INPUTS: sni: str | None
#   OUTPUTS: str
#   SIDE_EFFECTS: none
#   LINKS: M-051, V-M-051
# END_CONTRACT: mask_sni
# START_BLOCK_MASK_SNI
def mask_sni(sni: str | None) -> str:
    """Return a stable human-readable SNI mask suitable for logs and smoke output."""
    normalized = (sni or "").strip().lower().rstrip(".")
    if not normalized:
        return "<missing-sni>"

    label, separator, domain = normalized.partition(".")
    if len(label) <= 8:
        masked_label = f"{label[:2]}..."
    else:
        masked_label = f"{label[:4]}...{label[-4:]}"

    return f"{masked_label}{separator}{domain}" if separator else masked_label
# END_BLOCK_MASK_SNI


# START_CONTRACT: safe_fingerprint
#   PURPOSE: Create a short deterministic fingerprint for non-secret correlation.
#   INPUTS: value: str | None; length: int
#   OUTPUTS: str
#   SIDE_EFFECTS: none
#   LINKS: M-051, V-M-051
# END_CONTRACT: safe_fingerprint
# START_BLOCK_SAFE_FINGERPRINT
def safe_fingerprint(value: str | None, *, length: int = 12) -> str:
    """Return a short SHA-256 fingerprint without exposing the original value."""
    if not value:
        return "<missing>"
    bounded_length = max(6, min(length, 32))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:bounded_length]
# END_BLOCK_SAFE_FINGERPRINT


# START_CONTRACT: redact_proxy_text
#   PURPOSE: Remove secret-bearing MTProto link material from diagnostics.
#   INPUTS: text: str | None
#   OUTPUTS: str
#   SIDE_EFFECTS: none
#   LINKS: M-051, V-M-051
# END_CONTRACT: redact_proxy_text
# START_BLOCK_REDACT_PROXY_TEXT
def redact_proxy_text(text: str | None) -> str:
    """Redact full proxy links, secret query parameters, and fake-TLS hex secrets."""
    if not text:
        return ""

    redacted = _PROXY_LINK_RE.sub("<redacted-mtproto-link>", text)
    redacted = _SECRET_PARAM_RE.sub(r"\1<redacted>", redacted)
    return _FAKE_TLS_SECRET_RE.sub("<redacted-mtproto-secret>", redacted)
# END_BLOCK_REDACT_PROXY_TEXT


# START_CONTRACT: build_telegram_web_link
#   PURPOSE: Build the primary Telegram web link for opening a personal proxy.
#   INPUTS: server: str; port: int; secret: str
#   OUTPUTS: str
#   SIDE_EFFECTS: none
#   LINKS: M-045, M-051, V-M-051
# END_CONTRACT: build_telegram_web_link
# START_BLOCK_BUILD_TELEGRAM_WEB_LINK
def build_telegram_web_link(server: str, port: int, secret: str) -> str:
    """Build a https://t.me/proxy link using the same values as the owner payload."""
    normalized_server = server.strip().lower().rstrip(".")
    normalized_secret = secret.strip().lower()
    if not normalized_server or not normalized_secret:
        raise ValueError("server and secret are required")
    if not 1 <= int(port) <= 65535:
        raise ValueError("port must be in the TCP range")

    query = urlencode(
        {
            "server": normalized_server,
            "port": str(int(port)),
            "secret": normalized_secret,
        }
    )
    return f"https://t.me/proxy?{query}"
# END_BLOCK_BUILD_TELEGRAM_WEB_LINK
