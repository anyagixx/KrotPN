#!/usr/bin/env python3
"""RU SNI-router MTProto client-IP telemetry collector.

# FILE: deploy/sni-router-telemetry.py
# VERSION: 1.0.0
# ROLE: SCRIPT
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Receive HAProxy SNI-router syslog events and forward real MTProto client IP observations to backend ingestion
#   SCOPE: UDP syslog listener, safe SNI/client-IP parsing, bounded in-memory queue, token-protected backend POST, and redacted logs
#   DEPENDS: M-050, M-055, M-061
#   LINKS: docs/modules/M-050.xml, docs/modules/M-055.xml, docs/modules/M-061.xml
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   main - Load /opt/KrotPN/.env and run the UDP collector loop
#   normalize_ip_set - Normalize trusted proxy-hop IP allowlist from environment
#   parse_observation - Extract client IP and SNI from the HAProxy log marker
#   flush_events - POST queued observations to the backend private router-observations endpoint
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added live RU SNI-router client IP telemetry handoff without persisting raw IP logs.
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import hashlib
import ipaddress
import json
import os
import re
import socket
import sys
import time
from urllib import request
from urllib.error import URLError


MARKER = "[M-055][ru_sni_router][CLIENT_IP_OBSERVATION]"
OBSERVATION_RE = re.compile(
    r"src=(?P<src>[0-9A-Fa-f:.]+):(?P<port>[0-9]{1,5})\s+sni=(?P<sni>[A-Za-z0-9.-]{3,255})"
)


@dataclass(frozen=True)
class RouterObservation:
    runtime_event_id: str
    observed_at: str
    sni: str
    client_ip: str
    connection_count: int = 1
    reason_code: str = "ru_sni_router_client_ip"


# START_BLOCK_ENV
def load_env(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as env_file:
            for line in env_file:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                key, value = stripped.split("=", 1)
                values[key.strip()] = value.strip().strip("'\"")
    except FileNotFoundError:
        pass
    return values
# END_BLOCK_ENV


# START_BLOCK_PARSE_OBSERVATION
def normalize_ip_set(raw_value: str) -> set[str]:
    values: set[str] = set()
    for item in raw_value.replace(";", ",").split(","):
        candidate = item.strip()
        if not candidate:
            continue
        try:
            values.add(str(ipaddress.ip_address(candidate)))
        except ValueError:
            continue
    return values


def parse_observation(message: str, *, base_domain: str, trusted_proxy_ips: set[str]) -> RouterObservation | None:
    if MARKER not in message:
        return None
    match = OBSERVATION_RE.search(message)
    if not match:
        return None

    raw_ip = match.group("src")
    try:
        client_ip = str(ipaddress.ip_address(raw_ip))
    except ValueError:
        return None
    if client_ip in trusted_proxy_ips:
        return None

    sni = match.group("sni").strip().lower().rstrip(".")
    expected_suffix = f".{base_domain.strip().lower().lstrip('*.').rstrip('.')}"
    if not sni.startswith("u-") or not sni.endswith(expected_suffix):
        return None

    digest = hashlib.sha256(message.encode("utf-8")).hexdigest()[:32]
    return RouterObservation(
        runtime_event_id=f"ru-sni-{digest}",
        observed_at=datetime.now(timezone.utc).isoformat(),
        sni=sni,
        client_ip=client_ip,
    )
# END_BLOCK_PARSE_OBSERVATION


# START_BLOCK_FLUSH
def flush_events(endpoint: str, token: str, events: deque[RouterObservation]) -> bool:
    if not events:
        return True
    batch = [event.__dict__ for event in list(events)[:500]]
    payload = json.dumps({"events": batch}).encode("utf-8")
    http_request = request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "content-type": "application/json",
            "x-krotpn-mtproto-token": token,
        },
    )
    try:
        with request.urlopen(http_request, timeout=5) as response:
            if response.status >= 300:
                return False
    except (OSError, URLError):
        return False
    for _ in batch:
        events.popleft()
    print(
        f"[M-055][sni_router_telemetry][FORWARD_SUMMARY] forwarded={len(batch)} queued={len(events)}",
        flush=True,
    )
    return True
# END_BLOCK_FLUSH


# START_BLOCK_MAIN
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="/opt/KrotPN/.env")
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=1514)
    args = parser.parse_args()

    env = {**load_env(args.env), **os.environ}
    token = env.get("MTPROTO_RUNTIME_TOKEN", "")
    endpoint = env.get("MTPROTO_ROUTER_OBSERVER_ENDPOINT", "http://127.0.0.1:8000/api/v1/mtproto/router-observations")
    base_domain = env.get("MTPROTO_BASE_DOMAIN") or env.get("DOMAIN") or "krotpn.xyz"
    trusted_proxy_ips = normalize_ip_set(env.get("MTPROTO_ROUTER_TRUSTED_PROXY_IPS", ""))
    if not token:
        print("[M-055][sni_router_telemetry][STARTUP_FAILED] missing_runtime_token", flush=True)
        return 1

    queue: deque[RouterObservation] = deque(maxlen=2000)
    seen: deque[str] = deque(maxlen=4000)
    seen_set: set[str] = set()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.listen_host, args.listen_port))
    sock.settimeout(2.0)
    print(
        f"[M-055][sni_router_telemetry][LISTEN] host={args.listen_host} port={args.listen_port}",
        flush=True,
    )

    last_flush = time.monotonic()
    while True:
        try:
            data, _addr = sock.recvfrom(8192)
        except TimeoutError:
            data = b""
        except KeyboardInterrupt:
            return 0

        if data:
            message = data.decode("utf-8", errors="replace")
            observation = parse_observation(
                message,
                base_domain=base_domain,
                trusted_proxy_ips=trusted_proxy_ips,
            )
            if observation and observation.runtime_event_id not in seen_set:
                if len(seen) == seen.maxlen:
                    old_event_id = seen.popleft()
                    seen_set.discard(old_event_id)
                queue.append(observation)
                seen.append(observation.runtime_event_id)
                seen_set.add(observation.runtime_event_id)

        if queue and (len(queue) >= 25 or time.monotonic() - last_flush >= 5):
            flush_events(endpoint, token, queue)
            last_flush = time.monotonic()


if __name__ == "__main__":
    sys.exit(main())
# END_BLOCK_MAIN
