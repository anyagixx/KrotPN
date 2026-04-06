# FILE: backend/app/routing/__init__.py
# VERSION: 1.0.0
# ROLE: BARREL
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: Host-level split-tunneling, domain-aware routing policy, DNS-bound IP tracking, runtime sync
#   SCOPE: Domain/CIDR rule storage, DNS resolution with TTL, route decision engine, ipset/iptables sync
#   DEPENDS: M-001 (backend-core)
#   LINKS: M-007 (routing), M-013 (route-policy-resolver), M-014 (domain-rule-store), M-015 (dns-observer), M-017 (route-sync-runtime), V-M-007
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   DomainRouteRule, CidrRouteRule, CustomRoute - Routing policy models
#   DomainRuleStore, RuleValidationError - Rule persistence and validation
#   DNSBindingRecord, DNSObserver - TTL-aware DNS resolution for routing
#   RoutePolicyResolver, RouteDecision, DecisionReason - Policy decision engine
#   RoutingManager, routing_manager - Host-level ipset/iptables sync
#   routing_router - FastAPI router for routing inspection endpoints
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""Routing module exports."""
from app.routing.models import (
    CidrRouteRule,
    CidrRouteRuleCreate,
    CidrRouteRuleResponse,
    CidrRouteRuleUpdate,
    CustomRoute,
    CustomRouteCreate,
    CustomRouteResponse,
    DomainMatchType,
    DomainRouteRule,
    DomainRouteRuleCreate,
    DomainRouteRuleResponse,
    DomainRouteRuleUpdate,
    RouteType,
    RouteTarget,
    RoutingStatus,
)
from app.routing.domain_rules import (
    DomainRuleStore,
    RuleValidationError,
    normalize_cidr_rule_input,
    normalize_domain_rule_input,
)
from app.routing.dns_resolver import DNSBindingRecord, DNSObserver
from app.routing.manager import RoutingManager, routing_manager
from app.routing.policy import (
    DecisionReason,
    DnsBoundRoute,
    RouteDecision,
    RoutePolicyResolver,
)
from app.routing.router import router as routing_router

__all__ = [
    # Models
    "CidrRouteRule",
    "CidrRouteRuleCreate",
    "CidrRouteRuleResponse",
    "CidrRouteRuleUpdate",
    "CustomRoute",
    "CustomRouteCreate",
    "CustomRouteResponse",
    "DomainMatchType",
    "DomainRouteRule",
    "DomainRouteRuleCreate",
    "DomainRouteRuleResponse",
    "DomainRouteRuleUpdate",
    "RouteType",
    "RouteTarget",
    "RoutingStatus",
    # Store
    "DomainRuleStore",
    "RuleValidationError",
    "normalize_cidr_rule_input",
    "normalize_domain_rule_input",
    # DNS observer
    "DNSBindingRecord",
    "DNSObserver",
    # Policy
    "DecisionReason",
    "DnsBoundRoute",
    "RouteDecision",
    "RoutePolicyResolver",
    # Manager
    "RoutingManager",
    "routing_manager",
    # Router
    "routing_router",
]
