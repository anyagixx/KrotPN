from app.routing.models import (
    CidrRouteRule,
    DomainMatchType,
    DomainRouteRule,
    RouteTarget,
)
from app.routing.policy import DecisionReason, DnsBoundRoute, RoutePolicyResolver


def test_exact_domain_rule_wins_over_wildcard_and_cidr():
    resolver = RoutePolicyResolver()
    decision = resolver.resolve(
        domain="api.example.com",
        resolved_ip="8.8.8.8",
        domain_rules=[
            DomainRouteRule(
                id=1,
                domain="*.example.com",
                normalized_domain="example.com",
                match_type=DomainMatchType.WILDCARD,
                route_target=RouteTarget.RU,
                priority=20,
            ),
            DomainRouteRule(
                id=2,
                domain="api.example.com",
                normalized_domain="api.example.com",
                match_type=DomainMatchType.EXACT,
                route_target=RouteTarget.DE,
                priority=50,
            ),
        ],
        cidr_rules=[
            CidrRouteRule(
                id=3,
                cidr="8.8.8.0/24",
                normalized_cidr="8.8.8.0/24",
                route_target=RouteTarget.RU,
                priority=5,
            )
        ],
    )

    assert decision.route_target is RouteTarget.DE
    assert decision.reason is DecisionReason.DOMAIN_EXACT
    assert decision.trace_marker == "ROUTE_DECISION_DOMAIN_EXACT"


def test_wildcard_domain_rule_wins_when_exact_is_absent():
    resolver = RoutePolicyResolver()
    decision = resolver.resolve(
        domain="cdn.example.com",
        resolved_ip="8.8.8.8",
        domain_rules=[
            DomainRouteRule(
                id=1,
                domain="*.example.com",
                normalized_domain="example.com",
                match_type=DomainMatchType.WILDCARD,
                route_target=RouteTarget.DE,
                priority=10,
            )
        ],
        cidr_rules=[
            CidrRouteRule(
                id=2,
                cidr="8.8.8.0/24",
                normalized_cidr="8.8.8.0/24",
                route_target=RouteTarget.RU,
                priority=1,
            )
        ],
    )

    assert decision.route_target is RouteTarget.DE
    assert decision.reason is DecisionReason.DOMAIN_WILDCARD
    assert decision.trace_marker == "ROUTE_DECISION_DOMAIN_WILDCARD"


def test_dns_bound_ip_wins_over_cidr_rule():
    resolver = RoutePolicyResolver()
    decision = resolver.resolve(
        resolved_ip="5.5.5.5",
        dns_bound_routes=[
            DnsBoundRoute(
                normalized_domain="video.example.com",
                resolved_ip="5.5.5.5",
                route_target=RouteTarget.DE,
                rule_id=9,
            )
        ],
        cidr_rules=[
            CidrRouteRule(
                id=3,
                cidr="5.5.5.0/24",
                normalized_cidr="5.5.5.0/24",
                route_target=RouteTarget.RU,
                priority=1,
            )
        ],
    )

    assert decision.route_target is RouteTarget.DE
    assert decision.reason is DecisionReason.DNS_BOUND_IP
    assert decision.trace_marker == "ROUTE_DECISION_DNS_BOUND_IP"


def test_cidr_rule_wins_over_ru_baseline():
    resolver = RoutePolicyResolver(
        is_ru_ip=lambda ip: ip.startswith("1.1.1."),
    )
    decision = resolver.resolve(
        resolved_ip="1.1.1.25",
        cidr_rules=[
            CidrRouteRule(
                id=7,
                cidr="1.1.1.0/24",
                normalized_cidr="1.1.1.0/24",
                route_target=RouteTarget.DE,
                priority=3,
            )
        ],
    )

    assert decision.route_target is RouteTarget.DE
    assert decision.reason is DecisionReason.CIDR_RULE
    assert decision.trace_marker == "ROUTE_DECISION_CIDR"


def test_ru_baseline_applies_when_no_policy_rule_matches():
    resolver = RoutePolicyResolver(
        default_target=RouteTarget.DE,
        is_ru_ip=lambda ip: ip == "77.88.8.8",
    )
    decision = resolver.resolve(resolved_ip="77.88.8.8")

    assert decision.route_target is RouteTarget.RU
    assert decision.reason is DecisionReason.RU_BASELINE
    assert decision.trace_marker == "ROUTE_DECISION_RU_BASELINE"


def test_default_branch_applies_when_no_input_matches():
    resolver = RoutePolicyResolver(default_target=RouteTarget.DE)
    decision = resolver.resolve(domain="unknown.example.net", resolved_ip="203.0.113.7")

    assert decision.route_target is RouteTarget.DE
    assert decision.reason is DecisionReason.DEFAULT
    assert decision.trace_marker == "ROUTE_DECISION_FALLBACK"
