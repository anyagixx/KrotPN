# FILE: backend/app/routing/policy.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Resolve an effective route target from domain, DNS-bound IP, CIDR, RU baseline, and default fallback inputs.
#   SCOPE: Pure decision logic, stable decision reasons, and trace markers for later runtime and API integration.
#   DEPENDS: M-001 (backend-core), M-007 (routing)
#   LINKS: M-007 (routing), M-013 (route-policy-resolver), M-014 (domain-rule-store), M-015 (dns-observer), M-016 (route-decision-api), M-017 (route-sync-runtime)
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   DecisionReason - Stable route decision reason codes
#   RouteDecision - Resolved route target plus evidence fields for debugging and API visibility
#   DnsBoundRoute - DNS-derived route binding consumable by the resolver
#   RoutePolicyResolver - Deterministic resolver with precedence ordering and stable trace markers
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
"""Routing policy resolver for domain-aware route selection."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from loguru import logger

from app.routing.domain_rules import RuleValidationError, normalize_domain_rule_input
from app.routing.models import CidrRouteRule, DomainMatchType, DomainRouteRule, RouteTarget


class DecisionReason(str, Enum):
    """Stable reason codes for route resolution."""

    DOMAIN_EXACT = "domain_exact"
    DOMAIN_WILDCARD = "domain_wildcard"
    DNS_BOUND_IP = "dns_bound_ip"
    CIDR_RULE = "cidr_rule"
    RU_BASELINE = "ru_baseline"
    DEFAULT = "default"


_TRACE_MARKERS: dict[DecisionReason, str] = {
    DecisionReason.DOMAIN_EXACT: "ROUTE_DECISION_DOMAIN_EXACT",
    DecisionReason.DOMAIN_WILDCARD: "ROUTE_DECISION_DOMAIN_WILDCARD",
    DecisionReason.DNS_BOUND_IP: "ROUTE_DECISION_DNS_BOUND_IP",
    DecisionReason.CIDR_RULE: "ROUTE_DECISION_CIDR",
    DecisionReason.RU_BASELINE: "ROUTE_DECISION_RU_BASELINE",
    DecisionReason.DEFAULT: "ROUTE_DECISION_FALLBACK",
}


@dataclass(frozen=True)
class DnsBoundRoute:
    """DNS-derived IP binding carrying the target chosen for a known domain."""

    normalized_domain: str
    resolved_ip: str
    route_target: RouteTarget
    rule_id: int | None = None


@dataclass(frozen=True)
class RouteDecision:
    """Resolved route target and supporting metadata."""

    route_target: RouteTarget
    reason: DecisionReason
    trace_marker: str
    rule_id: int | None = None
    matched_domain: str | None = None
    normalized_domain: str | None = None
    resolved_ip: str | None = None


class RoutePolicyResolver:
    """Deterministic resolver for domain-aware route policy."""

    def __init__(
        self,
        *,
        default_target: RouteTarget = RouteTarget.DEFAULT,
        is_ru_ip: Callable[[str], bool] | None = None,
    ):
        self.default_target = default_target
        self.is_ru_ip = is_ru_ip or (lambda _: False)

    # START_BLOCK: resolve (main decision logic, ~50 lines)
    def resolve(
        self,
        *,
        domain: str | None = None,
        resolved_ip: str | None = None,
        domain_rules: list[DomainRouteRule] | None = None,
        cidr_rules: list[CidrRouteRule] | None = None,
        dns_bound_routes: list[DnsBoundRoute] | None = None,
    ) -> RouteDecision:
        """Resolve a route target using the approved precedence order."""
        normalized_domain = self._normalize_domain(domain)
        normalized_ip = self._normalize_ip(resolved_ip)

        match = self._match_domain_rule(normalized_domain, domain_rules or [])
        if match is not None:
            return self._decision_from_domain_rule(match, domain, normalized_domain, normalized_ip)

        dns_binding = self._match_dns_bound_route(normalized_ip, dns_bound_routes or [])
        if dns_binding is not None:
            decision = RouteDecision(
                route_target=dns_binding.route_target,
                reason=DecisionReason.DNS_BOUND_IP,
                trace_marker=_TRACE_MARKERS[DecisionReason.DNS_BOUND_IP],
                rule_id=dns_binding.rule_id,
                matched_domain=dns_binding.normalized_domain,
                normalized_domain=normalized_domain,
                resolved_ip=normalized_ip,
            )
            self._log_decision(decision)
            return decision

        cidr_rule = self._match_cidr_rule(normalized_ip, cidr_rules or [])
        if cidr_rule is not None:
            decision = RouteDecision(
                route_target=cidr_rule.route_target,
                reason=DecisionReason.CIDR_RULE,
                trace_marker=_TRACE_MARKERS[DecisionReason.CIDR_RULE],
                rule_id=cidr_rule.id,
                matched_domain=domain,
                normalized_domain=normalized_domain,
                resolved_ip=normalized_ip,
            )
            self._log_decision(decision)
            return decision

        if normalized_ip is not None and self.is_ru_ip(normalized_ip):
            decision = RouteDecision(
                route_target=RouteTarget.RU,
                reason=DecisionReason.RU_BASELINE,
                trace_marker=_TRACE_MARKERS[DecisionReason.RU_BASELINE],
                matched_domain=domain,
                normalized_domain=normalized_domain,
                resolved_ip=normalized_ip,
            )
            self._log_decision(decision)
            return decision

        decision = RouteDecision(
            route_target=self.default_target,
            reason=DecisionReason.DEFAULT,
            trace_marker=_TRACE_MARKERS[DecisionReason.DEFAULT],
            matched_domain=domain,
            normalized_domain=normalized_domain,
            resolved_ip=normalized_ip,
        )
        self._log_decision(decision)
        return decision
    # END_BLOCK: resolve

    def _normalize_domain(self, domain: str | None) -> str | None:
        """Normalize runtime domain input when present."""
        if domain is None:
            return None

        try:
            normalized = normalize_domain_rule_input(domain)
        except RuleValidationError:
            return None

        return normalized.normalized_domain

    def _normalize_ip(self, resolved_ip: str | None) -> str | None:
        """Normalize runtime IP input when present."""
        if resolved_ip is None:
            return None

        try:
            return str(ipaddress.ip_address(resolved_ip.strip()))
        except ValueError:
            return None

    # START_BLOCK: _match_domain_rule (domain matching, ~30 lines)
    def _match_domain_rule(
        self,
        normalized_domain: str | None,
        rules: list[DomainRouteRule],
    ) -> DomainRouteRule | None:
        """Find the highest-precedence exact or wildcard domain rule."""
        if normalized_domain is None:
            return None

        exact_rules = sorted(
            (
                rule for rule in rules
                if rule.is_active and rule.match_type == DomainMatchType.EXACT
            ),
            key=lambda rule: (
                rule.priority,
                -len(rule.normalized_domain),
                rule.normalized_domain,
            ),
        )
        for rule in exact_rules:
            if normalized_domain == rule.normalized_domain:
                return rule

        wildcard_rules = sorted(
            (
                rule for rule in rules
                if rule.is_active and rule.match_type == DomainMatchType.WILDCARD
            ),
            key=lambda rule: (
                rule.priority,
                -len(rule.normalized_domain),
                rule.normalized_domain,
            ),
        )
        for rule in wildcard_rules:
            if normalized_domain.endswith(f".{rule.normalized_domain}"):
                return rule

        return None
    # END_BLOCK: _match_domain_rule

    # START_BLOCK: _decision_from_domain_rule (rule-to-decision, ~18 lines)
    def _decision_from_domain_rule(
        self,
        rule: DomainRouteRule,
        raw_domain: str | None,
        normalized_domain: str | None,
        normalized_ip: str | None,
    ) -> RouteDecision:
        """Convert a matched domain rule into a route decision."""
        reason = (
            DecisionReason.DOMAIN_EXACT
            if rule.match_type == DomainMatchType.EXACT
            else DecisionReason.DOMAIN_WILDCARD
        )
        decision = RouteDecision(
            route_target=rule.route_target,
            reason=reason,
            trace_marker=_TRACE_MARKERS[reason],
            rule_id=rule.id,
            matched_domain=raw_domain,
            normalized_domain=normalized_domain,
            resolved_ip=normalized_ip,
        )
        self._log_decision(decision)
        return decision
    # END_BLOCK: _decision_from_domain_rule

    def _match_dns_bound_route(
        self,
        normalized_ip: str | None,
        bindings: list[DnsBoundRoute],
    ) -> DnsBoundRoute | None:
        """Find a DNS-derived binding for the resolved IP."""
        if normalized_ip is None:
            return None

        for binding in bindings:
            if binding.resolved_ip == normalized_ip:
                return binding
        return None

    # START_BLOCK: _match_cidr_rule (CIDR matching, ~15 lines)
    def _match_cidr_rule(
        self,
        normalized_ip: str | None,
        rules: list[CidrRouteRule],
    ) -> CidrRouteRule | None:
        """Find the first active CIDR rule that contains the resolved IP."""
        if normalized_ip is None:
            return None

        ip = ipaddress.ip_address(normalized_ip)
        sorted_rules = sorted(
            (rule for rule in rules if rule.is_active),
            key=lambda rule: (rule.priority, rule.normalized_cidr),
        )
        for rule in sorted_rules:
            network = ipaddress.ip_network(rule.normalized_cidr, strict=False)
            if ip in network:
                return rule
        return None
    # END_BLOCK: _match_cidr_rule

    # START_BLOCK: _log_decision (logging, ~12 lines)
    def _log_decision(self, decision: RouteDecision) -> None:
        """Emit a stable resolver log line for verification and debugging."""
        logger.info(
            "[Routing][resolver][{trace_marker}] decision_reason={decision_reason} "
            "route_target={route_target} rule_id={rule_id} domain={domain} "
            "normalized_domain={normalized_domain} resolved_ip={resolved_ip}",
            trace_marker=decision.trace_marker,
            decision_reason=decision.reason.value,
            route_target=decision.route_target.value,
            rule_id=decision.rule_id,
            domain=decision.matched_domain,
            normalized_domain=decision.normalized_domain,
            resolved_ip=decision.resolved_ip,
        )
    # END_BLOCK: _log_decision
