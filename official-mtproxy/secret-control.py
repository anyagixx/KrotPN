#!/usr/bin/env python3
"""KrotPN official MTProxy secret-control supervisor.

# FILE: official-mtproxy/secret-control.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Run official mtproto-proxy with KrotPN-managed per-user secret manifest.
#   SCOPE: Private token-protected manifest apply API, health API, manifest validation, redacted logging, Telegram config fetch, and mtproto-proxy process restart.
#   DEPENDS: M-052, M-053, official Telegram mtproto-proxy binary
#   LINKS: docs/modules/M-052.xml, docs/modules/M-053.xml, docs/plans/Phase-40.xml
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   RuntimeConfig - Environment-derived official MTProxy runtime settings
#   SecretEntry - Validated raw official MTProxy secret row
#   MTProxySupervisor - Manifest persistence and mtproto-proxy process manager
#   PolicyHandler - Private KrotPN HTTP policy API
#   main - Starts the token-protected HTTP server and supervisor
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-40 official MTProxy data-plane supervisor.
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import subprocess
import tempfile
import threading
import time
import urllib.request
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


SECRET_RE = re.compile(r"^[0-9a-f]{32}$")


# START_BLOCK_CONFIG
@dataclass(frozen=True)
class RuntimeConfig:
    data_dir: Path
    binary_path: str
    proxy_port: int
    stats_port: int
    workers: int
    policy_bind_ip: str
    policy_port: int
    policy_token: str
    manifest_path: Path
    proxy_secret_path: Path
    proxy_config_path: Path
    proxy_user: str
    proxy_tag: str | None

    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        data_dir = Path(os.getenv("MTPROXY_DATA_DIR", "/data"))
        policy_token = os.getenv("KROTPN_MTPROTO_POLICY_TOKEN", "").strip()
        if not policy_token:
            raise SystemExit("KROTPN_MTPROTO_POLICY_TOKEN is required")
        proxy_port = int(os.getenv("MTPROXY_PORT", os.getenv("MTPROTO_DE_RUNTIME_PORT", "443")))
        return cls(
            data_dir=data_dir,
            binary_path=os.getenv("MTPROXY_BINARY", "/usr/local/bin/mtproto-proxy"),
            proxy_port=proxy_port,
            stats_port=int(os.getenv("MTPROXY_STATS_PORT", "2398")),
            workers=int(os.getenv("MTPROXY_WORKERS", "1")),
            policy_bind_ip=os.getenv("MTPROTO_POLICY_BIND_IP", "127.0.0.1"),
            policy_port=int(os.getenv("MTPROTO_POLICY_PORT", "18080")),
            policy_token=policy_token,
            manifest_path=data_dir / "secrets.json",
            proxy_secret_path=data_dir / "proxy-secret",
            proxy_config_path=data_dir / "proxy-multi.conf",
            proxy_user=os.getenv("MTPROXY_USER", "mtproxy"),
            proxy_tag=os.getenv("MTPROXY_PROXY_TAG", "").strip() or None,
        )
# END_BLOCK_CONFIG


@dataclass(frozen=True)
class SecretEntry:
    assignment_id: int
    user_id: int
    sni: str
    secret_hex: str
    secret_fingerprint: str

    # START_BLOCK_SECRET_ENTRY
    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "SecretEntry":
        secret_hex = str(payload.get("secret_hex", "")).strip().lower()
        if not SECRET_RE.fullmatch(secret_hex):
            raise ValueError("secret_hex must be a 32-hex official MTProxy secret")
        fingerprint = hashlib.sha256(bytes.fromhex(secret_hex)).hexdigest()[:16]
        supplied_fingerprint = str(payload.get("secret_fingerprint", fingerprint)).strip()
        if supplied_fingerprint != fingerprint:
            raise ValueError("secret_fingerprint mismatch")
        return cls(
            assignment_id=int(payload["assignment_id"]),
            user_id=int(payload["user_id"]),
            sni=str(payload.get("sni", "")).strip().lower(),
            secret_hex=secret_hex,
            secret_fingerprint=fingerprint,
        )

    def to_runtime_dict(self) -> dict[str, Any]:
        return {
            "assignment_id": self.assignment_id,
            "user_id": self.user_id,
            "sni": self.sni,
            "secret_hex": self.secret_hex,
            "secret_fingerprint": self.secret_fingerprint,
        }
    # END_BLOCK_SECRET_ENTRY


class MTProxySupervisor:
    # START_BLOCK_SUPERVISOR_INIT
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self._lock = threading.RLock()
        self._process: subprocess.Popen[bytes] | None = None
        self._entries: list[SecretEntry] = []
        self._last_error: str | None = None
        self.config.data_dir.mkdir(parents=True, exist_ok=True)
    # END_BLOCK_SUPERVISOR_INIT

    # START_BLOCK_MANIFEST_IO
    def load_manifest(self) -> None:
        with self._lock:
            if not self.config.manifest_path.exists():
                self._entries = []
                return
            data = json.loads(self.config.manifest_path.read_text(encoding="utf-8"))
            entries = [SecretEntry.from_payload(item) for item in data.get("secrets", [])]
            self._entries = entries

    def apply_manifest(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            entries = [SecretEntry.from_payload(item) for item in payload.get("secrets", [])]
            safe_manifest = {
                "generated_at": payload.get("generated_at"),
                "active_count": len(entries),
                "manifest_fingerprint": payload.get("manifest_fingerprint"),
                "secrets": [entry.to_runtime_dict() for entry in entries],
            }
            fd, tmp_path = tempfile.mkstemp(
                prefix="secrets.",
                suffix=".json",
                dir=str(self.config.data_dir),
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(safe_manifest, handle, sort_keys=True)
                    handle.write("\n")
                os.chmod(tmp_path, 0o600)
                os.replace(tmp_path, self.config.manifest_path)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            self._entries = entries
            self.restart_proxy_locked()
            print(
                "[OfficialMTProxy][manifest][REDACTED_COUNT] "
                f"active_count={len(entries)} fingerprints="
                f"{','.join(entry.secret_fingerprint for entry in entries)}",
                flush=True,
            )
            return self.health_payload_locked()
    # END_BLOCK_MANIFEST_IO

    # START_BLOCK_TELEGRAM_CONFIG
    def ensure_telegram_config_locked(self) -> None:
        downloads = (
            ("https://core.telegram.org/getProxySecret", self.config.proxy_secret_path),
            ("https://core.telegram.org/getProxyConfig", self.config.proxy_config_path),
        )
        for url, path in downloads:
            if path.exists() and path.stat().st_size > 0:
                continue
            tmp_path = path.with_suffix(path.suffix + ".tmp")
            urllib.request.urlretrieve(url, tmp_path)
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, path)
    # END_BLOCK_TELEGRAM_CONFIG

    # START_BLOCK_PROCESS_CONTROL
    def stop_proxy_locked(self) -> None:
        if self._process is None:
            return
        if self._process.poll() is None:
            self._process.send_signal(signal.SIGTERM)
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        self._process = None

    def restart_proxy_locked(self) -> None:
        self.stop_proxy_locked()
        if not self._entries:
            self._last_error = "no active MTProxy secrets"
            return
        try:
            self.ensure_telegram_config_locked()
            command = [
                self.config.binary_path,
                "-u",
                self.config.proxy_user,
                "-p",
                str(self.config.stats_port),
                "-H",
                str(self.config.proxy_port),
            ]
            for entry in self._entries:
                command.extend(["-S", entry.secret_hex])
            if self.config.proxy_tag:
                command.extend(["-P", self.config.proxy_tag])
            command.extend(
                [
                    "--aes-pwd",
                    str(self.config.proxy_secret_path),
                    str(self.config.proxy_config_path),
                    "-M",
                    str(self.config.workers),
                ]
            )
            self._process = subprocess.Popen(command)
            self._last_error = None
            print(
                "[OfficialMTProxy][process][STARTED] "
                f"active_count={len(self._entries)} port={self.config.proxy_port}",
                flush=True,
            )
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            print("[OfficialMTProxy][process][DEGRADED] start failed", flush=True)
            self._process = None
    # END_BLOCK_PROCESS_CONTROL

    # START_BLOCK_HEALTH
    def health_payload(self) -> dict[str, Any]:
        with self._lock:
            return self.health_payload_locked()

    def health_payload_locked(self) -> dict[str, Any]:
        process_running = self._process is not None and self._process.poll() is None
        active_count = len(self._entries)
        status = "healthy" if process_running and active_count > 0 else "degraded"
        return {
            "status": status,
            "active_count": active_count,
            "process_running": process_running,
            "last_error": self._last_error,
            "checked_at": int(time.time()),
        }
    # END_BLOCK_HEALTH

    def shutdown(self) -> None:
        with self._lock:
            self.stop_proxy_locked()


class PolicyHandler(BaseHTTPRequestHandler):
    supervisor: MTProxySupervisor
    token: str

    # START_BLOCK_HTTP_HELPERS
    def _authorized(self) -> bool:
        return self.headers.get("x-krotpn-mtproto-token") == self.token

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("content-length", "0"))
        if content_length > 1024 * 1024:
            raise ValueError("request body too large")
        body = self.rfile.read(content_length)
        return json.loads(body.decode("utf-8") or "{}")

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[OfficialMTProxy][http][ACCESS] {self.address_string()} {self.requestline}", flush=True)
    # END_BLOCK_HTTP_HELPERS

    # START_BLOCK_HTTP_ROUTES
    def do_GET(self) -> None:
        if not self._authorized():
            self._send_json(HTTPStatus.UNAUTHORIZED, {"status": "unauthorized"})
            return
        if self.path == "/krotpn/mtproto/policy/health":
            self._send_json(HTTPStatus.OK, self.supervisor.health_payload())
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"status": "not_found"})

    def do_POST(self) -> None:
        if not self._authorized():
            self._send_json(HTTPStatus.UNAUTHORIZED, {"status": "unauthorized"})
            return
        if self.path != "/krotpn/mtproto/policy/secrets/apply":
            self._send_json(HTTPStatus.NOT_FOUND, {"status": "not_found"})
            return
        try:
            payload = self._read_json()
            response = self.supervisor.apply_manifest(payload)
            self._send_json(HTTPStatus.OK, response)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            print(
                "[OfficialMTProxy][manifest][REJECTED] "
                f"error_type={type(exc).__name__}",
                flush=True,
            )
            self._send_json(HTTPStatus.BAD_REQUEST, {"status": "rejected", "message": "invalid manifest"})
    # END_BLOCK_HTTP_ROUTES


# START_BLOCK_MAIN
def main() -> None:
    config = RuntimeConfig.from_env()
    supervisor = MTProxySupervisor(config)
    supervisor.load_manifest()
    with supervisor._lock:
        supervisor.restart_proxy_locked()

    PolicyHandler.supervisor = supervisor
    PolicyHandler.token = config.policy_token
    server = ThreadingHTTPServer((config.policy_bind_ip, config.policy_port), PolicyHandler)
    print(
        "[OfficialMTProxy][http][STARTED] "
        f"bind={config.policy_bind_ip}:{config.policy_port}",
        flush=True,
    )
    try:
        server.serve_forever()
    finally:
        supervisor.shutdown()


if __name__ == "__main__":
    main()
# END_BLOCK_MAIN
