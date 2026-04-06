# FILE: backend/app/routing/dns_resolver.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Refresh and expire DNS-derived route bindings for policy-managed domains under a bounded TTL cache.
#   SCOPE: Domain resolution hooks, TTL expiry, conflict tracking, and conversion into resolver-consumable DNS bindings.
#   DEPENDS: M-001 (backend-core), M-007 (routing)
#   LINKS: M-007 (routing), M-013 (route-policy-resolver), M-014 (domain-rule-store), M-015 (dns-observer), M-016 (route-decision-api), M-017 (route-sync-runtime)
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   DNSBindingRecord - In-memory TTL-tracked DNS binding
#   DNSObserver - Refreshes DNS bindings and exposes active resolver bindings
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
"""DNS binding observer for policy-managed domains."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Awaitable, Callable

from loguru import logger

from app.routing.models import DomainRouteRule, RouteTarget
from app.routing.policy import DnsBoundRoute


@dataclass(frozen=True)
class DNSBindingRecord:
    normalized_domain: str
    resolved_ip: str
    route_target: RouteTarget
    rule_id: int | None
    expires_at: datetime
    ttl_seconds: int


class DNSObserver:
    """TTL-aware DNS binding cache for policy-managed domains."""

    def __init__(
        self,
        resolver: Callable[[str], Awaitable[list[str]]],
        *,
        now_func: Callable[[], datetime] | None = None,
        default_ttl_seconds: int = 300,
        max_bindings_per_domain: int = 20,
    ):
        self.resolver = resolver
        self.now_func = now_func or (lambda: datetime.now(UTC))
        self.default_ttl_seconds = default_ttl_seconds
        self.max_bindings_per_domain = max_bindings_per_domain
        self._bindings: dict[str, list[DNSBindingRecord]] = {}

    # START_BLOCK: refresh_domain_bindings (DNS refresh, ~30 lines)
    async def refresh_domain_bindings(
        self,
        rule: DomainRouteRule,
        *,
        ttl_seconds: int | None = None,
    ) -> list[DNSBindingRecord]:
        """Refresh DNS bindings for one rule and replace its active cache entries."""
        ttl = ttl_seconds or self.default_ttl_seconds
        now = self.now_func()
        resolved_ips = await self.resolver(rule.normalized_domain)
        unique_ips = sorted(dict.fromkeys(resolved_ips))[: self.max_bindings_per_domain]

        existing_ips = {
            binding.resolved_ip
            for binding in self._bindings.get(rule.normalized_domain, [])
            if binding.expires_at > now
        }
        refreshed = [
            DNSBindingRecord(
                normalized_domain=rule.normalized_domain,
                resolved_ip=ip,
                route_target=rule.route_target,
                rule_id=rule.id,
                expires_at=now + timedelta(seconds=ttl),
                ttl_seconds=ttl,
            )
            for ip in unique_ips
        ]
        self._bindings[rule.normalized_domain] = refreshed

        conflict_ips = sorted(existing_ips - set(unique_ips))
        if conflict_ips:
            logger.info(
                "[Routing][dns][DNS_BINDING_CONFLICT] "
                f"domain={rule.normalized_domain} stale={','.join(conflict_ips)}"
            )
        logger.info(
            "[Routing][dns][DNS_BINDING_UPDATED] "
            f"domain={rule.normalized_domain} count={len(refreshed)} ttl_seconds={ttl}"
        )
        return refreshed
    # END_BLOCK: refresh_domain_bindings

    # START_BLOCK: expire_stale_bindings (TTL cleanup, ~18 lines)
    def expire_stale_bindings(self) -> list[DNSBindingRecord]:
        """Expire bindings whose TTL has elapsed and return the removed records."""
        now = self.now_func()
        expired: list[DNSBindingRecord] = []

        for domain, bindings in list(self._bindings.items()):
            active = [binding for binding in bindings if binding.expires_at > now]
            expired.extend(binding for binding in bindings if binding.expires_at <= now)
            if active:
                self._bindings[domain] = active
            else:
                self._bindings.pop(domain, None)

        for binding in expired:
            logger.info(
                "[Routing][dns][DNS_BINDING_EXPIRED] "
                f"domain={binding.normalized_domain} resolved_ip={binding.resolved_ip}"
            )
        return expired
    # END_BLOCK: expire_stale_bindings

    def clear_domain_bindings(self, normalized_domain: str) -> list[DNSBindingRecord]:
        """Remove all bindings for one domain and return removed records."""
        removed = self._bindings.pop(normalized_domain, [])
        for binding in removed:
            logger.info(
                "[Routing][dns][DNS_BINDING_EXPIRED] "
                f"domain={binding.normalized_domain} resolved_ip={binding.resolved_ip}"
            )
        return removed

    # START_BLOCK: get_active_bindings (binding query, ~14 lines)
    def get_active_bindings(self) -> list[DnsBoundRoute]:
        """Expose active bindings in the resolver-facing shape."""
        now = self.now_func()
        bindings: list[DnsBoundRoute] = []
        for domain_bindings in self._bindings.values():
            for binding in domain_bindings:
                if binding.expires_at <= now:
                    continue
                bindings.append(
                    DnsBoundRoute(
                        normalized_domain=binding.normalized_domain,
                        resolved_ip=binding.resolved_ip,
                        route_target=binding.route_target,
                        rule_id=binding.rule_id,
                    )
                )
        return bindings
    # END_BLOCK: get_active_bindings
