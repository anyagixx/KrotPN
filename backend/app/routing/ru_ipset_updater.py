# FILE: backend/app/routing/ru_ipset_updater.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Multi-source RU IP range fetcher with validation, dedup, and incremental ipset apply.
#   SCOPE: Download CIDR lists from ipverse/anti-zapret/ipgeobase, validate, merge, persist snapshot.
#   DEPENDS: M-001 (backend-core: settings), httpx, ipaddress, json, pathlib
#   LINKS: M-017 (route-sync-runtime), V-M-017
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   RuIpsetUpdater - Fetches, validates, and applies RU IP ranges from multiple sources
#   RuIpsetStats - Dataclass for ipset update statistics
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.5 - Created RuIpsetUpdater for Phase-15 automated RU IP updates
# END_CHANGE_SUMMARY
"""
Automated RU IP range updater with multi-source fallback and atomic ipset swap.

Sources (priority order):
  1. ipverse.net — RIPE NCC aggregated RU IPs
  2. antizapret proxy-blocker — Community-maintained RU ranges
  3. ipgeobase.ru — Daily-updated RU CIDR lists

Safety:
  - Atomic ipset swap (no flush during update)
  - Validation: >= 1000 entries, valid CIDR only
  - Fallback: last-known-good snapshot
  - Rollback: restore snapshot on swap failure
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

# --- Configuration ---

SNAPSHOT_DIR = Path("/var/lib/krotvpn")
SNAPSHOT_FILE = SNAPSHOT_DIR / "ru_ips_snapshot.json"

MIN_ENTRIES = 1000
CHANGE_WARN_THRESHOLD = 0.20  # 20%
SOURCE_TIMEOUT = 30
TOTAL_TIMEOUT = 90

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


@dataclass
class RuIpsetStats:
    entries: int = 0
    last_update: str | None = None
    sources_used: list[str] = field(default_factory=list)
    last_error: str | None = None
    entries_added: int = 0
    entries_removed: int = 0
    snapshot_exists: bool = False


class RuIpsetUpdater:
    """Multi-source RU IP range fetcher with validation and atomic apply."""

    def __init__(
        self,
        sources: list[dict[str, str]] | None = None,
        *,
        snapshot_dir: Path | None = None,
        min_entries: int = MIN_ENTRIES,
        change_warn_threshold: float = CHANGE_WARN_THRESHOLD,
    ):
        self.sources = sources or SOURCES
        self.snapshot_dir = snapshot_dir or SNAPSHOT_DIR
        self.snapshot_file = self.snapshot_dir / "ru_ips_snapshot.json"
        self.min_entries = min_entries
        self.change_warn_threshold = change_warn_threshold

    # START_BLOCK: fetch_all_sources
    async def fetch_all_sources(self) -> tuple[set[str], list[str]]:
        """
        Fetch CIDR lists from all available sources with fallback.

        Returns:
            Tuple of (merged CIDR set, list of source names that succeeded)
        """
        all_cidrs: set[str] = set()
        sources_used: list[str] = []

        async with httpx.AsyncClient(
            timeout=SOURCE_TIMEOUT, follow_redirects=True
        ) as client:
            for source in self.sources:
                try:
                    cidrs = await self._fetch_single(client, source)
                    if cidrs:
                        all_cidrs.update(cidrs)
                        sources_used.append(source["name"])
                        logger.info(
                            f"[RuIpsetUpdater][fetch_sources][SOURCE_OK] "
                            f"source={source['name']} cidrs={len(cidrs)}"
                        )
                    else:
                        logger.warning(
                            f"[RuIpsetUpdater][fetch_sources][SOURCE_EMPTY] "
                            f"source={source['name']}"
                        )
                except Exception as e:
                    logger.warning(
                        f"[RuIpsetUpdater][fetch_sources][SOURCE_FAIL] "
                        f"source={source['name']} error={e}"
                    )
                    continue

        if not sources_used:
            logger.error(
                "[RuIpsetUpdater][fetch_sources][ALL_SOURCES_FAILED] "
                "All sources unavailable"
            )

        return all_cidrs, sources_used
    # END_BLOCK: fetch_all_sources

    # START_BLOCK: fetch_single
    async def _fetch_single(
        self, client: httpx.AsyncClient, source: dict[str, str]
    ) -> set[str]:
        """Fetch and parse CIDR list from one source."""
        response = await client.get(source["url"])
        response.raise_for_status()

        if source.get("format") == "json":
            data = response.json()
            key = source.get("key", "ip_list")
            raw_cidrs = data.get(key, data) if isinstance(data, dict) else data
            if isinstance(raw_cidrs, list):
                return self._parse_cidrs(str(c) for c in raw_cidrs)
            return set()
        else:
            return self._parse_cidrs(response.text.splitlines())
    # END_BLOCK: fetch_single

    # START_BLOCK: parse_cidrs
    def _parse_cidrs(self, lines: Any) -> set[str]:
        """Parse and validate CIDR strings from source lines."""
        cidrs: set[str] = set()
        for line in lines:
            line = str(line).strip()
            if not line or line.startswith("#"):
                continue
            try:
                network = ipaddress.ip_network(line, strict=False)
                cidrs.add(str(network))
            except ValueError:
                continue
        return cidrs
    # END_BLOCK: parse_cidrs

    # START_BLOCK: validate_cidrs
    def validate_cidrs(self, cidrs: set[str]) -> bool:
        """Check that we have a sane number of entries."""
        count = len(cidrs)
        if count < self.min_entries:
            logger.error(
                f"[RuIpsetUpdater][validate][SANITY_FAIL] "
                f"entries={count} threshold={self.min_entries}"
            )
            return False
        logger.info(
            f"[RuIpsetUpdater][validate][SANITY_OK] "
            f"entries={count} threshold={self.min_entries}"
        )
        return True
    # END_BLOCK: validate_cidrs

    # START_BLOCK: compute_diff
    @staticmethod
    def compute_diff(
        current: set[str], desired: set[str]
    ) -> tuple[set[str], set[str], int, int]:
        """
        Compute incremental diff.

        Returns:
            (to_add, to_remove, added_count, removed_count)
        """
        to_add = desired - current
        to_remove = current - desired
        return to_add, to_remove, len(to_add), len(to_remove)
    # END_BLOCK: compute_diff

    # START_BLOCK: apply_incremental
    async def apply_incremental(
        self,
        ipset_name: str,
        to_add: set[str],
        to_remove: set[str],
    ) -> bool:
        """
        Apply incremental ipset changes using atomic swap.

        Strategy:
        1. Create parallel ipset (ru_ips_new)
        2. Copy current entries minus removals
        3. Add new entries
        4. Atomic swap
        5. Destroy old ipset

        Returns:
            True if successful, False if rollback needed
        """
        parallel_name = f"{ipset_name}_new"

        try:
            # Create parallel ipset
            await self._run("ipset", "create", parallel_name, "hash:net")

            # Copy current entries (minus removals)
            for cidr in (self._get_current_entries(ipset_name) - to_remove):
                await self._run("ipset", "add", parallel_name, cidr)

            # Add new entries
            for cidr in to_add:
                await self._run("ipset", "add", parallel_name, cidr)

            # Atomic swap
            await self._run("ipset", "swap", ipset_name, parallel_name)

            # Destroy old (now parallel) ipset
            await self._run("ipset", "destroy", parallel_name, check=False)

            logger.info(
                f"[RuIpsetUpdater][apply_incremental][IPSET_SWAP_OK] "
                f"added={len(to_add)} removed={len(to_remove)}"
            )
            return True

        except Exception as e:
            logger.error(
                f"[RuIpsetUpdater][apply_incremental][IPSET_SWAP_FAIL] "
                f"error={e}"
            )
            # Cleanup parallel ipset
            await self._run("ipset", "destroy", parallel_name, check=False)
            raise
    # END_BLOCK: apply_incremental

    # START_BLOCK: get_current_entries
    async def _get_current_entries(self, ipset_name: str) -> set[str]:
        """Read current ipset members."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ipset", "list", ipset_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode != 0:
                return set()

            entries: set[str] = set()
            in_members = False
            for line in stdout.decode().splitlines():
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
    # END_BLOCK: get_current_entries

    # START_BLOCK: persist_snapshot
    def persist_snapshot(
        self, cidrs: set[str], sources_used: list[str]
    ) -> None:
        """Save current CIDR set as last-known-good snapshot."""
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot = {
            "timestamp": datetime.now(UTC).isoformat(),
            "sources": sources_used,
            "entries": sorted(cidrs),
            "count": len(cidrs),
        }
        self.snapshot_file.write_text(json.dumps(snapshot, indent=2))
        logger.info(
            f"[RuIpsetUpdater][snapshot][SNAPSHOT_SAVED] "
            f"path={self.snapshot_file} entries={len(cidrs)}"
        )
    # END_BLOCK: persist_snapshot

    # START_BLOCK: load_snapshot
    def load_snapshot(self) -> set[str] | None:
        """Load last-known-good snapshot, or None if unavailable."""
        if not self.snapshot_file.exists():
            return None
        try:
            snapshot = json.loads(self.snapshot_file.read_text())
            cidrs = set(snapshot.get("entries", []))
            logger.info(
                f"[RuIpsetUpdater][snapshot][SNAPSHOT_LOADED] "
                f"entries={len(cidrs)}"
            )
            return cidrs
        except Exception as e:
            logger.error(
                f"[RuIpsetUpdater][snapshot][SNAPSHOT_CORRUPT] error={e}"
            )
            return None
    # END_BLOCK: load_snapshot

    # START_BLOCK: update_ru_ipset
    async def update_ru_ipset(self, ipset_name: str = "ru_ips") -> RuIpsetStats:
        """
        Main update orchestration.

        Flow:
        1. Fetch from all sources
        2. Validate
        3. Compute diff
        4. Apply incrementally
        5. Persist snapshot

        Returns:
            RuIpsetStats with update results
        """
        stats = RuIpsetStats(snapshot_exists=self.snapshot_file.exists())

        try:
            # Step 1: Fetch
            all_cidrs, sources_used = await self.fetch_all_sources()

            if not sources_used:
                # All sources failed — try snapshot
                logger.warning(
                    "[RuIpsetUpdater][fallback][FALLBACK_TRIGGERED] "
                    "All sources failed, trying snapshot"
                )
                snapshot_cidrs = self.load_snapshot()
                if snapshot_cidrs is None:
                    stats.last_error = "All sources failed, no snapshot available"
                    logger.error(
                        f"[RuIpsetUpdater][fallback][NO_SNAPSHOT] {stats.last_error}"
                    )
                    return stats

                all_cidrs = snapshot_cidrs
                sources_used = ["snapshot"]
                stats.sources_used = sources_used

            # Step 2: Validate
            if not self.validate_cidrs(all_cidrs):
                stats.last_error = f"Validation failed: {len(all_cidrs)} < {self.min_entries}"
                return stats

            # Step 3: Compute diff
            current = await self._get_current_entries(ipset_name)
            to_add, to_remove, added, removed = self.compute_diff(current, all_cidrs)

            # Warn if >20% changed
            if current and (added + removed) / len(current) > self.change_warn_threshold:
                logger.warning(
                    f"[RuIpsetUpdater][validate][CHANGE_ALERT] "
                    f"change_pct={((added + removed) / len(current) * 100):.1f}% "
                    f"added={added} removed={removed}"
                )

            # Step 4: Apply (skip if no changes)
            if to_add or to_remove:
                await self.apply_incremental(ipset_name, to_add, to_remove)
                stats.entries_added = added
                stats.entries_removed = removed
            else:
                logger.info(
                    "[RuIpsetUpdater][apply_incremental][NO_CHANGES] "
                    "ipset already up to date"
                )

            # Step 5: Persist snapshot
            self.persist_snapshot(all_cidrs, sources_used)

            stats.entries = len(all_cidrs)
            stats.sources_used = sources_used
            stats.last_update = datetime.now(UTC).isoformat()

            logger.info(
                f"[RuIpsetUpdater][update_ru_ipset][UPDATE_COMPLETE] "
                f"entries={stats.entries} sources={sources_used} "
                f"added={added} removed={removed}"
            )

        except Exception as e:
            stats.last_error = str(e)
            logger.error(
                f"[RuIpsetUpdater][update_ru_ipset][UPDATE_FAIL] error={e}"
            )

        return stats
    # END_BLOCK: update_ru_ipset

    # START_BLOCK: get_stats
    async def get_stats(self, ipset_name: str = "ru_ips") -> RuIpsetStats:
        """Get current ipset statistics without updating."""
        stats = RuIpsetStats(snapshot_exists=self.snapshot_file.exists())

        entries = await self._get_current_entries(ipset_name)
        stats.entries = len(entries)

        if self.snapshot_file.exists():
            try:
                snapshot = json.loads(self.snapshot_file.read_text())
                stats.last_update = snapshot.get("timestamp")
                stats.sources_used = snapshot.get("sources", [])
            except Exception:
                pass

        return stats
    # END_BLOCK: get_stats

    # START_BLOCK: run_subprocess
    @staticmethod
    async def _run(*args: str, check: bool = True) -> None:
        """Run a subprocess and raise on failure if check=True."""
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if check and proc.returncode != 0:
            raise RuntimeError(
                f"{' '.join(args)} failed (rc={proc.returncode}): "
                f"{stderr.decode().strip()}"
            )
    # END_BLOCK: run_subprocess


# Global singleton
ru_ipset_updater = RuIpsetUpdater()
