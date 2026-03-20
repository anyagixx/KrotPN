"""
Routing models for custom routes and split-tunneling.
"""
# <!-- GRACE: module="M-007" entity="CustomRoute" -->

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class RouteType(str, Enum):
    """Route type for custom routing."""
    DIRECT = "direct"  # Traffic goes directly (bypass VPN)
    VPN = "vpn"  # Traffic goes through VPN


class CustomRoute(SQLModel, table=True):
    """Custom routing rule."""
    
    __tablename__ = "custom_routes"
    
    id: int | None = Field(default=None, primary_key=True)
    address: str = Field(max_length=255, index=True)  # Domain, IP, or CIDR
    route_type: RouteType = Field(default=RouteType.VPN)
    description: str | None = Field(default=None, max_length=500)
    
    # Status
    is_active: bool = Field(default=True)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


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
