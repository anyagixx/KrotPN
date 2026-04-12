# FILE: backend/app/routing/manager.py
# VERSION: 2.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Host-level split-tunneling, ipset/iptables synchronization, route health inspection, RU baseline maintenance, and automated multi-source RU IP range updates.
#   SCOPE: Russian IP set management (automated from 3 sources), custom route sync, iptables rule setup, tunnel status checks, policy-aware route resolution.
#   DEPENDS: M-001 (backend-core), M-007 (routing), M-017 (ru_ipset_updater)
#   LINKS: M-007 (routing), M-013 (route-policy-resolver), M-014 (domain-rule-store), M-015 (dns-observer), M-016 (route-decision-api), M-017 (route-sync-runtime)
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   RoutingManager - Host-level split-tunneling and route health manager with automated RU IP updates
#   routing_manager - Global singleton instance
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.5 - Integrated RuIpsetUpdater for automated multi-source RU IP updates (Phase-15)
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
"""
Routing manager for split-tunneling and custom routes.

LEGACY SOURCE: krot-prod-main/backend/routing.py
Handles iptables, ipset, and routing rules.
"""
# <!-- GRACE: module="M-007" contract="routing-manager" -->
# <!-- GRACE: legacy-source="krot-prod-main/backend/routing.py" -->

import asyncio
import ipaddress
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from app.routing.domain_rules import RuleValidationError, normalize_domain_rule_input
from app.routing.models import CidrRouteRule, DomainMatchType, DomainRouteRule, RouteTarget
from app.routing.policy import DecisionReason, RouteDecision, RoutePolicyResolver
from app.routing.ru_ipset_updater import RuIpsetUpdater, RuIpsetStats


class RoutingManager:
    """
    Manager for split-tunneling and routing rules.
    
    Handles:
    - Russian IP set for direct routing
    - Custom routes (direct or VPN)
    - iptables rules
    - Routing tables
    """
    
    IPSET_RU = "ru_ips"
    IPSET_CUSTOM_DIRECT = "custom_direct"
    IPSET_CUSTOM_VPN = "custom_vpn"
    ROUTING_TABLE = 100
    FWMARK = 255
    
    def __init__(self):
        self.update_script = Path("/usr/local/bin/update_ru_ips.sh")
        self.scheduler = AsyncIOScheduler()
        self._initialized = False
        self.ipset_updater = RuIpsetUpdater()
        self._last_stats: RuIpsetStats | None = None
    
    # START_BLOCK: initialize (scheduler setup, ~15 lines)
    async def initialize(self) -> None:
        """Initialize routing manager and start scheduler."""
        if self._initialized:
            return

        # Schedule RU IPset update every 6 hours (Phase-15)
        self.scheduler.add_job(
            self.update_ru_ipset,
            'interval',
            hours=6,
            id='update_ru_ipset',
        )
        self.scheduler.start()

        # Initial update
        await self.update_ru_ipset()

        self._initialized = True
        logger.info("[ROUTING] RoutingManager initialized")
    # END_BLOCK: initialize

    # START_BLOCK: update_ru_ipset (automated multi-source update, ~20 lines)
    async def update_ru_ipset(self) -> bool:
        """
        Update Russian IP set using automated multi-source fetcher.

        Returns:
            True if successful, False otherwise
        """
        try:
            stats = await self.ipset_updater.update_ru_ipset(self.IPSET_RU)
            self._last_stats = stats
            return stats.last_error is None
        except Exception as e:
            logger.error(f"[ROUTING] Error updating RU IPset: {e}")
            return False
    # END_BLOCK: update_ru_ipset

    # START_BLOCK: get_ru_ipset_stats (stats endpoint, ~15 lines)
    async def get_ru_ipset_stats(self) -> RuIpsetStats:
        """Get RU ipset statistics without triggering update."""
        stats = await self.ipset_updater.get_stats(self.IPSET_RU)
        self._last_stats = stats
        return stats
    # END_BLOCK: get_ru_ipset_stats
    
    # START_BLOCK: _create_update_script (script generation, ~30 lines)
    async def _create_update_script(self) -> None:
        """Create the RU IPset update script."""
        script_content = '''#!/bin/bash
# Update Russian IP set for split-tunneling

ipset create ru_ips hash:net 2>/dev/null || true
ipset flush ru_ips

# Add private networks
ipset add ru_ips 10.0.0.0/8 2>/dev/null || true
ipset add ru_ips 192.168.0.0/16 2>/dev/null || true
ipset add ru_ips 172.16.0.0/12 2>/dev/null || true

# Download and add Russian IPs
curl -sL https://raw.githubusercontent.com/ipverse/rir-ip/master/country/ru/ipv4-aggregated.txt | \\
    grep -v '^#' | grep -E '^[0-9]' | \\
    while read line; do
        ipset add ru_ips $line 2>/dev/null || true
    done

echo "RU IPset updated: $(ipset list ru_ips | grep 'Number of entries' | cut -d: -f2) entries"
'''

        # Create directory if needed
        self.update_script.parent.mkdir(parents=True, exist_ok=True)
        self.update_script.write_text(script_content)
        self.update_script.chmod(0o755)

        logger.info("[ROUTING] Created update script")
    # END_BLOCK: _create_update_script
    
    # START_BLOCK: get_ipset_stats (ipset statistics, ~25 lines)
    async def get_ipset_stats(self) -> dict[str, Any]:
        """Get statistics for IP sets."""
        stats = {}

        for ipset_name in [self.IPSET_RU, self.IPSET_CUSTOM_DIRECT, self.IPSET_CUSTOM_VPN]:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "ipset", "list", ipset_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()

                if proc.returncode == 0:
                    lines = stdout.decode().split('\n')
                    for line in lines:
                        if line.startswith("Number of entries:"):
                            count = int(line.split(':')[1].strip())
                            stats[ipset_name] = {"entries": count, "status": "active"}
                            break
                else:
                    stats[ipset_name] = {"entries": 0, "status": "inactive"}

            except Exception as e:
                logger.error(f"[ROUTING] Error getting ipset stats: {e}")
                stats[ipset_name] = {"entries": 0, "status": "error"}

        return stats
    # END_BLOCK: get_ipset_stats
    
    # START_BLOCK: check_tunnel_status (tunnel health check, ~40 lines)
    async def check_tunnel_status(self, tunnel_interface: str = "awg0") -> dict[str, str]:
        """
        Check VPN tunnel status.

        Args:
            tunnel_interface: Tunnel interface name

        Returns:
            Dict with interface and status
        """
        config_path = Path(f"/etc/amnezia/amneziawg/{tunnel_interface}.conf")

        def _config_is_host_managed() -> bool:
            try:
                return config_path.exists()
            except PermissionError:
                return True

        try:
            # Check if interface exists and is up
            proc = await asyncio.create_subprocess_exec(
                "ip", "link", "show", tunnel_interface,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            if proc.returncode != 0:
                if _config_is_host_managed():
                    return {"interface": tunnel_interface, "status": "host_managed"}
                return {"interface": tunnel_interface, "status": "down"}

            if "UP" not in stdout.decode():
                return {"interface": tunnel_interface, "status": "down"}

            # Try to ping through tunnel
            proc = await asyncio.create_subprocess_exec(
                "ping", "-c", "1", "-W", "2", "-I", tunnel_interface, "8.8.8.8",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()

            if proc.returncode == 0:
                return {"interface": tunnel_interface, "status": "up"}
            else:
                return {"interface": tunnel_interface, "status": "no_connectivity"}

        except FileNotFoundError:
            if _config_is_host_managed():
                return {"interface": tunnel_interface, "status": "host_managed"}
            return {"interface": tunnel_interface, "status": "down"}
        except Exception as e:
            logger.error(f"[ROUTING] Error checking tunnel status: {e}")
            if _config_is_host_managed():
                return {"interface": tunnel_interface, "status": "host_managed"}
            return {"interface": tunnel_interface, "status": "error"}
    # END_BLOCK: check_tunnel_status

    # START_BLOCK: is_ip_in_ru_ipset (RU baseline check, ~18 lines)
    async def is_ip_in_ru_ipset(self, ip: str) -> bool:
        """Check whether an IP belongs to the current RU ipset baseline."""
        try:
            normalized_ip = str(ipaddress.ip_address(ip))
        except ValueError:
            return False

        try:
            proc = await asyncio.create_subprocess_exec(
                "ipset", "test", self.IPSET_RU, normalized_ip,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return proc.returncode == 0
        except FileNotFoundError:
            logger.warning("[ROUTING] ipset is not available; RU baseline check skipped")
            return False
        except Exception as e:
            logger.warning(f"[ROUTING] RU baseline ipset lookup failed for {ip}: {e}")
            return False
    # END_BLOCK: is_ip_in_ru_ipset

    # START_BLOCK: resolve_effective_target (policy resolution, ~35 lines)
    async def resolve_effective_target(
        self,
        address: str,
        *,
        domain_rules: list[DomainRouteRule] | None = None,
        cidr_rules: list[CidrRouteRule] | None = None,
        dns_bound_routes: list[Any] | None = None,
        custom_routes: list[dict[str, Any]] | None = None,
    ) -> RouteDecision:
        """Resolve the effective route target while preserving the legacy RU baseline."""
        stripped = address.strip()
        if not stripped:
            return RouteDecision(
                route_target=RouteTarget.DE,
                reason=DecisionReason.DEFAULT,
                trace_marker="ROUTE_DECISION_FALLBACK",
            )

        resolved_ip: str | None = None
        domain: str | None = None
        if self._is_ip_or_cidr(stripped):
            if "/" not in stripped:
                resolved_ip = stripped
        else:
            domain = stripped
            resolved_ip = await self._resolve_domain_to_ipv4(stripped)

        legacy_domain_rules, legacy_cidr_rules = self._build_legacy_policy_rules(custom_routes or [])
        resolver = RoutePolicyResolver(default_target=RouteTarget.DE)
        decision = resolver.resolve(
            domain=domain,
            resolved_ip=resolved_ip,
            domain_rules=[*(domain_rules or []), *legacy_domain_rules],
            cidr_rules=[*(cidr_rules or []), *legacy_cidr_rules],
            dns_bound_routes=dns_bound_routes,
        )
        if decision.reason is not DecisionReason.DEFAULT:
            return decision

        if resolved_ip is not None and await self.is_ip_in_ru_ipset(resolved_ip):
            return RouteDecision(
                route_target=RouteTarget.RU,
                reason=DecisionReason.RU_BASELINE,
                trace_marker="ROUTE_DECISION_RU_BASELINE",
                matched_domain=domain,
                normalized_domain=decision.normalized_domain,
                resolved_ip=resolved_ip,
            )

        return decision
    # END_BLOCK: resolve_effective_target

    # START_BLOCK: _resolve_domain_to_ipv4 (DNS lookup, ~12 lines)
    async def _resolve_domain_to_ipv4(self, domain: str) -> str | None:
        """Resolve a domain to one IPv4 address for policy compatibility checks."""
        try:
            results = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: socket.getaddrinfo(domain, None, socket.AF_INET),
            )
        except Exception:
            return None

        for result in results:
            ip = result[4][0]
            if ip:
                return ip
        return None
    # END_BLOCK: _resolve_domain_to_ipv4

    # START_BLOCK: _build_legacy_policy_rules (legacy translation, ~35 lines)
    def _build_legacy_policy_rules(
        self,
        routes: list[dict[str, Any]],
    ) -> tuple[list[DomainRouteRule], list[CidrRouteRule]]:
        """Translate legacy custom routes into policy-rule equivalents."""
        domain_rules: list[DomainRouteRule] = []
        cidr_rules: list[CidrRouteRule] = []

        for index, route in enumerate(routes, start=1):
            address = str(route.get("address", "")).strip()
            if not address:
                continue

            route_target = self._legacy_route_target(str(route.get("route_type", "vpn")))
            priority = int(route.get("priority", 500))
            if self._is_ip_or_cidr(address):
                normalized_cidr = self._normalize_legacy_cidr(address)
                if normalized_cidr is None:
                    continue
                cidr_rules.append(
                    CidrRouteRule(
                        id=-index,
                        cidr=address,
                        normalized_cidr=normalized_cidr,
                        route_target=route_target,
                        priority=priority,
                    )
                )
                continue

            try:
                normalized = normalize_domain_rule_input(address)
            except RuleValidationError:
                continue

            domain_rules.append(
                DomainRouteRule(
                    id=-index,
                    domain=normalized.raw_domain,
                    normalized_domain=normalized.normalized_domain,
                    match_type=normalized.match_type,
                    route_target=route_target,
                    priority=priority,
                )
            )

        return domain_rules, cidr_rules
    # END_BLOCK: _build_legacy_policy_rules

    def _legacy_route_target(self, route_type: str) -> RouteTarget:
        """Map legacy direct/vpn routes to policy route targets."""
        return RouteTarget.DIRECT if route_type == "direct" else RouteTarget.DE

    def _is_ip_or_cidr(self, value: str) -> bool:
        """Return True when a string is parseable as an IP or CIDR."""
        try:
            if "/" in value:
                ipaddress.ip_network(value, strict=False)
            else:
                ipaddress.ip_address(value)
            return True
        except ValueError:
            return False

    def _normalize_legacy_cidr(self, value: str) -> str | None:
        """Normalize a legacy IP or CIDR route for policy matching."""
        try:
            if "/" in value:
                return str(ipaddress.ip_network(value, strict=False))
            return f"{ipaddress.ip_address(value)}/32"
        except ValueError:
            return None
    
    # START_BLOCK: setup_split_tunnel (iptables setup, ~80 lines)
    async def setup_split_tunnel(
        self,
        client_interface: str = "awg-client",
        tunnel_interface: str = "awg0",
        bypass_ru: bool = True,
    ) -> bool:
        """
        Setup split-tunneling rules.

        Args:
            client_interface: Interface for VPN clients
            tunnel_interface: Interface for exit tunnel
            bypass_ru: Whether to bypass VPN for Russian IPs

        Returns:
            True if successful
        """
        try:
            # Create ipsets if not exist
            for ipset_name in [self.IPSET_RU, self.IPSET_CUSTOM_DIRECT, self.IPSET_CUSTOM_VPN]:
                proc = await asyncio.create_subprocess_exec(
                    "ipset", "create", ipset_name, "hash:net",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.wait()

            # Add private networks to RU ipset
            for network in ["10.0.0.0/8", "192.168.0.0/16", "172.16.0.0/12"]:
                proc = await asyncio.create_subprocess_exec(
                    "ipset", "add", self.IPSET_RU, network,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.wait()

            # Setup routing table
            proc = await asyncio.create_subprocess_exec(
                "ip", "rule", "add", "fwmark", str(self.FWMARK),
                "lookup", str(self.ROUTING_TABLE),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()

            proc = await asyncio.create_subprocess_exec(
                "ip", "route", "add", "default", "dev", tunnel_interface,
                "table", str(self.ROUTING_TABLE),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()

            # Setup NAT
            proc = await asyncio.create_subprocess_exec(
                "iptables", "-t", "nat", "-A", "POSTROUTING",
                "-o", tunnel_interface, "-j", "MASQUERADE",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()

            # Create custom mangle chain
            proc = await asyncio.create_subprocess_exec(
                "iptables", "-t", "mangle", "-N", "AMNEZIA_PREROUTING",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()

            # Link chain to PREROUTING
            proc = await asyncio.create_subprocess_exec(
                "iptables", "-t", "mangle", "-C", "PREROUTING",
                "-i", client_interface, "-j", "AMNEZIA_PREROUTING",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            result = await proc.wait()

            if result != 0:
                proc = await asyncio.create_subprocess_exec(
                    "iptables", "-t", "mangle", "-A", "PREROUTING",
                    "-i", client_interface, "-j", "AMNEZIA_PREROUTING",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.wait()

            # Flush and rebuild rules
            proc = await asyncio.create_subprocess_exec(
                "iptables", "-t", "mangle", "-F", "AMNEZIA_PREROUTING",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()

            # Custom VPN routes (mark for VPN)
            proc = await asyncio.create_subprocess_exec(
                "iptables", "-t", "mangle", "-A", "AMNEZIA_PREROUTING",
                "-m", "set", "--match-set", self.IPSET_CUSTOM_VPN, "dst",
                "-j", "MARK", "--set-mark", str(self.FWMARK),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()

            proc = await asyncio.create_subprocess_exec(
                "iptables", "-t", "mangle", "-A", "AMNEZIA_PREROUTING",
                "-m", "set", "--match-set", self.IPSET_CUSTOM_VPN, "dst",
                "-j", "RETURN",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()

            # Custom direct routes (bypass VPN)
            proc = await asyncio.create_subprocess_exec(
                "iptables", "-t", "mangle", "-A", "AMNEZIA_PREROUTING",
                "-m", "set", "--match-set", self.IPSET_CUSTOM_DIRECT, "dst",
                "-j", "RETURN",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()

            # RU bypass
            if bypass_ru:
                proc = await asyncio.create_subprocess_exec(
                    "iptables", "-t", "mangle", "-A", "AMNEZIA_PREROUTING",
                    "-m", "set", "--match-set", self.IPSET_RU, "dst",
                    "-j", "RETURN",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.wait()

            # Default: mark for VPN
            proc = await asyncio.create_subprocess_exec(
                "iptables", "-t", "mangle", "-A", "AMNEZIA_PREROUTING",
                "-j", "MARK", "--set-mark", str(self.FWMARK),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()

            logger.info("[ROUTING] Split-tunneling configured successfully")
            return True

        except Exception as e:
            logger.error(f"[ROUTING] Error setting up split-tunnel: {e}")
            return False
    # END_BLOCK: setup_split_tunnel

    @dataclass(frozen=True)
    class RouteSyncPlan:
        add_direct: set[str] = field(default_factory=set)
        remove_direct: set[str] = field(default_factory=set)
        add_vpn: set[str] = field(default_factory=set)
        remove_vpn: set[str] = field(default_factory=set)

    def _build_route_sync_plan(
        self,
        current_direct: set[str],
        current_vpn: set[str],
        desired_direct: set[str],
        desired_vpn: set[str],
    ) -> RouteSyncPlan:
        """Compute the incremental route-set diff between current and desired ipset entries."""
        return self.RouteSyncPlan(
            add_direct=desired_direct - current_direct,
            remove_direct=current_direct - desired_direct,
            add_vpn=desired_vpn - current_vpn,
            remove_vpn=current_vpn - desired_vpn,
        )

    # START_BLOCK: _collect_desired_route_sets (route resolution, ~25 lines)
    async def _collect_desired_route_sets(
        self,
        routes: list[dict[str, Any]],
    ) -> tuple[set[str], set[str]]:
        """Resolve routes into desired direct and VPN ipset members."""
        desired_direct: set[str] = set()
        desired_vpn: set[str] = set()

        for route in routes:
            address = route.get("address", "").strip()
            route_type = route.get("route_type", "vpn")
            if not address:
                continue

            target_set = desired_direct if route_type == "direct" else desired_vpn
            if self._is_ip_or_cidr(address):
                normalized = self._normalize_legacy_cidr(address)
                if normalized is not None:
                    target_set.add(normalized)
                continue

            resolved_ip = await self._resolve_domain_to_ipv4(address)
            if resolved_ip is None:
                logger.warning(f"[ROUTING] Could not resolve {address}")
                continue
            normalized = self._normalize_legacy_cidr(resolved_ip)
            if normalized is not None:
                target_set.add(normalized)

        return desired_direct, desired_vpn
    # END_BLOCK: _collect_desired_route_sets

    # START_BLOCK: _get_ipset_entries (ipset read, ~20 lines)
    async def _get_ipset_entries(self, ipset_name: str) -> set[str]:
        """Read current ipset members into canonical strings."""
        proc = await asyncio.create_subprocess_exec(
            "ipset", "list", ipset_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return set()

        members: set[str] = set()
        in_members = False
        for line in stdout.decode().splitlines():
            stripped = line.strip()
            if stripped == "Members:":
                in_members = True
                continue
            if not in_members or not stripped:
                continue

            normalized = self._normalize_legacy_cidr(stripped)
            if normalized is not None:
                members.add(normalized)
        return members
    # END_BLOCK: _get_ipset_entries

    # START_BLOCK: _apply_route_sync_plan (incremental sync, ~15 lines)
    async def _apply_route_sync_plan(self, plan: RouteSyncPlan) -> None:
        """Apply an incremental route-set diff to ipset."""
        operations = [
            (self.IPSET_CUSTOM_DIRECT, "del", plan.remove_direct),
            (self.IPSET_CUSTOM_VPN, "del", plan.remove_vpn),
            (self.IPSET_CUSTOM_DIRECT, "add", plan.add_direct),
            (self.IPSET_CUSTOM_VPN, "add", plan.add_vpn),
        ]
        for ipset_name, action, entries in operations:
            for entry in sorted(entries):
                proc = await asyncio.create_subprocess_exec(
                    "ipset", action, ipset_name, entry,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
    # END_BLOCK: _apply_route_sync_plan

    # START_BLOCK: _apply_full_route_sync (full rebuild, ~25 lines)
    async def _apply_full_route_sync(
        self,
        desired_direct: set[str],
        desired_vpn: set[str],
    ) -> None:
        """Rebuild route ipsets from scratch when incremental sync is unavailable."""
        for ipset_name in [self.IPSET_CUSTOM_DIRECT, self.IPSET_CUSTOM_VPN]:
            proc = await asyncio.create_subprocess_exec(
                "ipset", "flush", ipset_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()

        for ipset_name, entries in [
            (self.IPSET_CUSTOM_DIRECT, desired_direct),
            (self.IPSET_CUSTOM_VPN, desired_vpn),
        ]:
            for entry in sorted(entries):
                proc = await asyncio.create_subprocess_exec(
                    "ipset", "add", ipset_name, entry,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.wait()
    # END_BLOCK: _apply_full_route_sync
    
    # START_BLOCK: sync_custom_routes (route sync, ~30 lines)
    async def sync_custom_routes(self, routes: list[dict[str, Any]]) -> None:
        """
        Sync custom routes from database to ipset.

        Args:
            routes: List of route dicts with 'address' and 'route_type'
        """
        desired_direct, desired_vpn = await self._collect_desired_route_sets(routes)

        try:
            current_direct = await self._get_ipset_entries(self.IPSET_CUSTOM_DIRECT)
            current_vpn = await self._get_ipset_entries(self.IPSET_CUSTOM_VPN)
            plan = self._build_route_sync_plan(
                current_direct=current_direct,
                current_vpn=current_vpn,
                desired_direct=desired_direct,
                desired_vpn=desired_vpn,
            )
            await self._apply_route_sync_plan(plan)
            logger.info(
                "[Routing][sync][RUNTIME_ROUTESET_INCREMENTAL] "
                f"add_direct={len(plan.add_direct)} remove_direct={len(plan.remove_direct)} "
                f"add_vpn={len(plan.add_vpn)} remove_vpn={len(plan.remove_vpn)}"
            )
        except Exception as e:
            logger.warning(f"[ROUTING] Incremental sync unavailable, falling back to full refresh: {e}")
            await self._apply_full_route_sync(desired_direct, desired_vpn)
            logger.info(
                "[Routing][sync][RUNTIME_ROUTESET_FULL_REFRESH] "
                f"direct_entries={len(desired_direct)} vpn_entries={len(desired_vpn)}"
            )

        logger.info(f"[ROUTING] Synced {len(routes)} custom routes")
    # END_BLOCK: sync_custom_routes


# Global instance
routing_manager = RoutingManager()
