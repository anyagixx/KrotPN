# FILE: backend/app/routing/models.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Define persisted routing rules, API schemas, and policy-facing enums for host-level routing decisions.
#   SCOPE: Custom routes, exact-domain rules, wildcard-domain rules, explicit CIDR rules, and routing status response shapes.
#   DEPENDS: M-001 (backend-core), M-007 (routing)
#   LINKS: M-007 (routing), M-013 (route-policy-resolver), M-014 (domain-rule-store), M-015 (dns-observer), M-016 (route-decision-api), M-017 (route-sync-runtime)
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   RouteType - Legacy custom-route destination enum
#   RouteTarget - Policy route target enum (RU, DE, DIRECT, DEFAULT)
#   DomainMatchType - Policy rule classifier (exact, wildcard)
#   CustomRoute - Persisted custom route model
#   DomainRouteRule - Persisted exact/wildcard domain rule model
#   CidrRouteRule - Persisted explicit IP/CIDR rule model
#   RoutingStatus - Routing runtime status response
#   CustomRouteCreate - Request schema for custom route creation
#   CustomRouteResponse - Response schema for custom route reads
#   DomainRouteRuleCreate - Request schema for domain rule creation
#   DomainRouteRuleUpdate - Partial-update schema for domain rules
#   DomainRouteRuleResponse - Response schema for domain rules
#   CidrRouteRuleCreate - Request schema for CIDR rule creation
#   CidrRouteRuleUpdate - Partial-update schema for CIDR rules
#   CidrRouteRuleResponse - Response schema for CIDR rules
#   RouteDecisionExplainRequest - Request schema for route decision inspection
#   RouteDecisionExplainResponse - Response schema for effective route decisions
#   ActiveDNSBindingResponse - Response schema for active DNS-derived bindings
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
"""Routing models for split-tunneling and policy-driven routing."""

from __future__ import annotations

from datetime import datetime, timezone, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel


class RouteType(str, Enum):
    """Route type for legacy custom routing."""

    DIRECT = "direct"
    VPN = "vpn"


class RouteTarget(str, Enum):
    """Policy route target for routing decisions."""

    RU = "ru"
    DE = "de"
    DIRECT = "direct"
    DEFAULT = "default"


class DomainMatchType(str, Enum):
    """Supported domain policy rule classes."""

    EXACT = "exact"
    WILDCARD = "wildcard"


# START_BLOCK: CustomRoute (table model, ~12 lines)
class CustomRoute(SQLModel, table=True):
    """Custom routing rule."""

    __tablename__ = "custom_routes"

    id: int | None = Field(default=None, primary_key=True)
    address: str = Field(max_length=255, index=True)
    route_type: RouteType = Field(default=RouteType.VPN)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
# END_BLOCK: CustomRoute


# START_BLOCK: DomainRouteRule (table model, ~17 lines)
class DomainRouteRule(SQLModel, table=True):
    """Persisted exact or wildcard domain routing rule."""

    __tablename__ = "domain_route_rules"
    __table_args__ = (
        UniqueConstraint(
            "normalized_domain",
            "match_type",
            name="uq_domain_route_rules_normalized_domain_match_type",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    domain: str = Field(max_length=255, index=True)
    normalized_domain: str = Field(max_length=253, index=True)
    match_type: DomainMatchType = Field(default=DomainMatchType.EXACT)
    route_target: RouteTarget = Field(default=RouteTarget.DEFAULT)
    priority: int = Field(default=100, index=True)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
# END_BLOCK: DomainRouteRule


# START_BLOCK: CidrRouteRule (table model, ~15 lines)
class CidrRouteRule(SQLModel, table=True):
    """Persisted explicit IP or CIDR routing rule."""

    __tablename__ = "cidr_route_rules"
    __table_args__ = (
        UniqueConstraint(
            "normalized_cidr",
            name="uq_cidr_route_rules_normalized_cidr",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    cidr: str = Field(max_length=64, index=True)
    normalized_cidr: str = Field(max_length=64, index=True)
    route_target: RouteTarget = Field(default=RouteTarget.DEFAULT)
    priority: int = Field(default=100, index=True)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
# END_BLOCK: CidrRouteRule


class RoutingStatus(SQLModel):
    """Routing system status."""

    ru_ipset_entries: int
    ru_ipset_status: str
    tunnel_status: str
    custom_routes_count: int
    last_ru_update: datetime | None


class CustomRouteCreate(SQLModel):
    """Schema for creating a custom route."""

    address: str = Field(..., min_length=1, max_length=255)
    route_type: RouteType
    description: str | None = None


class CustomRouteResponse(SQLModel):
    """Custom route response."""

    id: int
    address: str
    route_type: RouteType
    description: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class DomainRouteRuleCreate(SQLModel):
    """Schema for creating an exact or wildcard domain rule."""

    domain: str = Field(..., min_length=1, max_length=255)
    route_target: RouteTarget
    priority: int = Field(default=100, ge=0, le=10000)
    description: str | None = Field(default=None, max_length=500)


class DomainRouteRuleUpdate(SQLModel):
    """Partial update schema for domain rules."""

    route_target: RouteTarget | None = None
    priority: int | None = Field(default=None, ge=0, le=10000)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class DomainRouteRuleResponse(SQLModel):
    """Response schema for a domain route rule."""

    id: int
    domain: str
    normalized_domain: str
    match_type: DomainMatchType
    route_target: RouteTarget
    priority: int
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CidrRouteRuleCreate(SQLModel):
    """Schema for creating an explicit CIDR or single-IP rule."""

    cidr: str = Field(..., min_length=1, max_length=64)
    route_target: RouteTarget
    priority: int = Field(default=100, ge=0, le=10000)
    description: str | None = Field(default=None, max_length=500)


class CidrRouteRuleUpdate(SQLModel):
    """Partial update schema for CIDR rules."""

    route_target: RouteTarget | None = None
    priority: int | None = Field(default=None, ge=0, le=10000)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class CidrRouteRuleResponse(SQLModel):
    """Response schema for an explicit CIDR rule."""

    id: int
    cidr: str
    normalized_cidr: str
    route_target: RouteTarget
    priority: int
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RouteDecisionExplainRequest(SQLModel):
    """Request schema for route decision inspection."""

    address: str = Field(..., min_length=1, max_length=255)


class RouteDecisionExplainResponse(SQLModel):
    """Response schema for an explainable route decision."""

    address: str
    route_target: RouteTarget
    decision_reason: str
    trace_marker: str
    rule_id: int | None = None
    normalized_domain: str | None = None
    resolved_ip: str | None = None


class ActiveDNSBindingResponse(SQLModel):
    """Response schema for an active DNS-derived route binding."""

    normalized_domain: str
    resolved_ip: str
    route_target: RouteTarget
    rule_id: int | None = None
