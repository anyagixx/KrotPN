#!/usr/bin/env python3
"""
Host-level RU IP range updater for KrotVPN.
Runs on the host (not inside Docker container) via cron.

Updates the ru_ips ipset from multiple sources with fallback,
validation, and atomic swap.

Usage:
    python3 /opt/KrotVPN/scripts/update_ru_ips.py [--dry-run] [--stats]

Cron (every 6 hours):
    0 */6 * * * /usr/bin/python3 /opt/KrotVPN/scripts/update_ru_ips.py >> /var/log/krotvpn-ru-ip-update.log 2>&1
"""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import sys
import subprocess
from datetime import UTC, datetime
from pathlib import Path

SNAPSHOT_DIR = Path("/var/lib/krotvpn")
SNAPSHOT_FILE = SNAPSHOT_DIR / "ru_ips_snapshot.json"
IPSET_NAME = "ru_ips"
MIN_ENTRIES = 1000
CHANGE_WARN_THRESHOLD = 0.20
SOURCE_TIMEOUT = 30

SOURCES = [
    {
        "name": "ipverse",
        "url": "https://ipverse.net/russia/ips.json",
        "format": "json",
        "key": "ip_list",
    },
    {
        "name": "antizapret",
        "url": "https://raw.githubusercontent.com/antizapret/proxy-blocker/master/ips/country-only-ru.txt",
        "format": "text",
    },
    {
        "name": "ipgeobase",
        "url": "https://ipgeobase.ru/files/db/ipv4/RU.txt",
        "format": "text",
    },
]


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess."""
    result = subprocess.run(
        args, capture_output=True, text=True, timeout=60
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"{' '.join(args)} failed (rc={result.returncode}): {result.stderr.strip()}"
        )
    return result


def fetch_url(url: str, timeout: int = SOURCE_TIMEOUT) -> str:
    """Fetch URL content using curl."""
    result = run("curl", "-sL", "--max-time", str(timeout), url)
    return result.stdout


def parse_cidrs(text: str) -> set[str]:
    """Parse and validate CIDR strings from text."""
    cidrs: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            network = ipaddress.ip_network(line, strict=False)
            cidrs.add(str(network))
        except ValueError:
            continue
    return cidrs


def fetch_all_sources() -> tuple[set[str], list[str]]:
    """Fetch from all sources with fallback."""
    all_cidrs: set[str] = set()
    sources_used: list[str] = []

    for source in SOURCES:
        try:
            content = fetch_url(source["url"])
            if source.get("format") == "json":
                data = json.loads(content)
                key = source.get("key", "ip_list")
                raw = data.get(key, data) if isinstance(data, dict) else data
                if isinstance(raw, list):
                    cidrs = parse_cidrs("\n".join(str(c) for c in raw))
                else:
                    cidrs = parse_cidrs(content)
            else:
                cidrs = parse_cidrs(content)

            if cidrs:
                all_cidrs.update(cidrs)
                sources_used.append(source["name"])
                print(f"[SOURCE_OK] {source['name']} → {len(cidrs)} CIDRs")
            else:
                print(f"[SOURCE_EMPTY] {source['name']}")
        except Exception as e:
            print(f"[SOURCE_FAIL] {source['name']} → {e}")

    return all_cidrs, sources_used


def get_current_entries() -> set[str]:
    """Read current ipset members."""
    try:
        result = run("ipset", "list", IPSET_NAME)
        entries: set[str] = set()
        in_members = False
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped == "Members:":
                in_members = True
                continue
            if not in_members or not stripped:
                continue
            try:
                network = ipaddress.ip_network(stripped, strict=False)
                entries.add(str(network))
            except ValueError:
                continue
        return entries
    except Exception:
        return set()


def compute_diff(current: set[str], desired: set[str]) -> tuple[set[str], set[str]]:
    """Compute incremental diff."""
    to_add = desired - current
    to_remove = current - desired
    return to_add, to_remove


def apply_incremental(to_add: set[str], to_remove: set[str]) -> bool:
    """Apply incremental ipset changes using atomic swap."""
    parallel_name = f"{IPSET_NAME}_new"

    try:
        # Create parallel ipset
        run("ipset", "create", parallel_name, "hash:net")

        # Copy current entries minus removals
        current = get_current_entries()
        for cidr in (current - to_remove):
            run("ipset", "add", parallel_name, cidr, check=False)

        # Add new entries
        for cidr in to_add:
            run("ipset", "add", parallel_name, cidr, check=False)

        # Atomic swap
        run("ipset", "swap", IPSET_NAME, parallel_name)

        # Destroy old ipset
        run("ipset", "destroy", parallel_name, check=False)

        print(f"[IPSET_SWAP_OK] added={len(to_add)} removed={len(to_remove)}")
        return True

    except Exception as e:
        print(f"[IPSET_SWAP_FAIL] {e}")
        # Cleanup parallel ipset
        run("ipset", "destroy", parallel_name, check=False)
        raise


def persist_snapshot(cidrs: set[str], sources_used: list[str]) -> None:
    """Save snapshot."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "timestamp": datetime.now(UTC).isoformat(),
        "sources": sources_used,
        "entries": sorted(cidrs),
        "count": len(cidrs),
    }
    SNAPSHOT_FILE.write_text(json.dumps(snapshot, indent=2))
    print(f"[SNAPSHOT_SAVED] {SNAPSHOT_FILE} ({len(cidrs)} entries)")


def load_snapshot() -> set[str] | None:
    """Load snapshot or None."""
    if not SNAPSHOT_FILE.exists():
        return None
    try:
        data = json.loads(SNAPSHOT_FILE.read_text())
        return set(data.get("entries", []))
    except Exception:
        return None


def show_stats() -> None:
    """Display current stats."""
    entries = get_current_entries()
    print(f"\n=== RU IPset Stats ===")
    print(f"  Entries: {len(entries)}")
    if SNAPSHOT_FILE.exists():
        snap = json.loads(SNAPSHOT_FILE.read_text())
        print(f"  Last update: {snap.get('timestamp', 'unknown')}")
        print(f"  Sources: {', '.join(snap.get('sources', []))}")
    else:
        print(f"  Snapshot: not found")


async def main(dry_run: bool = False) -> int:
    """Main update orchestration."""
    print(f"=== RU IP Update {'(DRY RUN)' if dry_run else ''} ===")
    print(f"Timestamp: {datetime.now(UTC).isoformat()}")

    # Step 1: Fetch
    all_cidrs, sources_used = fetch_all_sources()

    if not sources_used:
        print("[FALLBACK] All sources failed, trying snapshot")
        snapshot_cidrs = load_snapshot()
        if snapshot_cidrs is None:
            print("[ERROR] All sources failed, no snapshot available")
            return 1
        all_cidrs = snapshot_cidrs
        sources_used = ["snapshot"]
        print(f"[SNAPSHOT_LOADED] {len(all_cidrs)} entries")

    # Step 2: Validate
    if len(all_cidrs) < MIN_ENTRIES:
        print(f"[SANITY_FAIL] entries={len(all_cidrs)} < {MIN_ENTRIES}")
        return 1

    print(f"[VALIDATE_OK] {len(all_cidrs)} entries (threshold={MIN_ENTRIES})")

    if dry_run:
        current = get_current_entries()
        to_add, to_remove = compute_diff(current, all_cidrs)
        print(f"[DRY_RUN] Would add {len(to_add)}, remove {len(to_remove)}")
        return 0

    # Step 3: Compute diff
    current = get_current_entries()
    to_add, to_remove = compute_diff(current, all_cidrs)

    # Warn if >20% changed
    if current and (len(to_add) + len(to_remove)) / len(current) > CHANGE_WARN_THRESHOLD:
        pct = (len(to_add) + len(to_remove)) / len(current) * 100
        print(f"[CHANGE_ALERT] {pct:.1f}% changed")

    # Step 4: Apply
    if to_add or to_remove:
        print(f"[DIFF] add={len(to_add)} remove={len(to_remove)}")
        apply_incremental(to_add, to_remove)
    else:
        print("[NO_CHANGES] ipset already up to date")

    # Step 5: Persist
    persist_snapshot(all_cidrs, sources_used)

    print(f"[UPDATE_COMPLETE] entries={len(all_cidrs)} sources={sources_used}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update RU IP ranges")
    parser.add_argument("--dry-run", action="store_true", help="Show diff without applying")
    parser.add_argument("--stats", action="store_true", help="Show current stats")
    args = parser.parse_args()

    if args.stats:
        show_stats()
        sys.exit(0)

    exit_code = asyncio.run(main(dry_run=args.dry_run))
    sys.exit(exit_code)
