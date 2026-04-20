# FILE: backend/app/vpn/models.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: VPN data models — servers, nodes, routes, clients, configs, stats
#   SCOPE: Schema definitions, field declarations, relationship wiring; no business logic
#   DEPENDS: M-001 (core database), M-003 (vpn), M-020 (device-registry), M-032 (vpn-network-addressing-capacity)
#   LINKS: M-003 (vpn), M-020 (device-registry), M-032, V-M-003, V-M-020, V-M-032
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   ServerStatus - Enum: online, offline, maintenance
#   VPNServer - Legacy VPN server record (table: vpn_servers)
#   VPNNode - Route-aware VPN node record (table: vpn_nodes)
#   VPNRoute - Route linking entry and exit nodes (table: vpn_routes)
#   VPNClient - VPN client bound to user + device + route with nullable encrypted preshared key (table: vpn_clients)
#   VPNConfig - Response model for rendered VPN config (non-table)
#   VPNStats - Response model for VPN statistics (non-table)
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v3.2.0 - Updated fresh-deploy VPNServer subnet and capacity defaults for 1000-device pools
#   LAST_CHANGE: v3.0.0 - Added nullable encrypted preshared key storage for new AWG peers
#   LAST_CHANGE: v2.8.0 - Converted to full GRACE MODULE_CONTRACT/MAP format with START/END blocks
# END_CHANGE_SUMMARY
#
#   v2.8.0 – Stabilized multi-device model: device_id uniqueness,
#            nullable exit_node_id on routes, legacy VPNServer mirror retained.
# =============================================================================
"""
VPN models for server and client configuration.

CHANGE_SUMMARY
- 2026-03-27: Added nullable device linkage so legacy one-client-per-user records can migrate toward explicit device-bound peers.
- 2026-03-27: Moved the stable uniqueness boundary from user_id to device_id for multi-device support.
"""
# <!-- GRACE: module="M-003" entity="VPNServer, VPNNode, VPNRoute, VPNClient" -->

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.core.vpn_network import DEFAULT_VPN_CLIENT_SUBNET

if TYPE_CHECKING:
    from app.devices.models import UserDevice
    from app.users.models import User


# START_BLOCK: class VPNServer
class VPNServer(SQLModel, table=True):
    """Deprecated legacy mirror of an entry-capable node."""

    __tablename__ = "vpn_servers"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    location: str = Field(max_length=100)  # e.g., "Germany", "Netherlands"
    endpoint: str = Field(max_length=255)  # IP or hostname
    port: int = Field(default=51821)

    # Server keys (private key encrypted)
    public_key: str = Field(max_length=100, unique=True)
    private_key_enc: str | None = Field(default=None, max_length=500)  # Encrypted

    # Network configuration
    subnet: str = Field(default=DEFAULT_VPN_CLIENT_SUBNET)

    # Status
    is_active: bool = Field(default=True)
    is_entry_node: bool = Field(default=False)  # RU server = entry node
    is_exit_node: bool = Field(default=True)  # DE server = exit node

    # Capacity
    max_clients: int = Field(default=1000)
    current_clients: int = Field(default=0)

    # Monitoring
    last_ping_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    is_online: bool = Field(default=True)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))

    # Relationships
    clients: list["VPNClient"] = Relationship(back_populates="server")
# END_BLOCK: class VPNServer


# START_BLOCK: class VPNNode
class VPNNode(SQLModel, table=True):
    """Physical VPN node used as an entry, exit, or combined hop."""

    __tablename__ = "vpn_nodes"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    role: str = Field(default="entry", max_length=20)
    country_code: str = Field(default="ZZ", max_length=2)
    location: str = Field(max_length=100)
    endpoint: str = Field(max_length=255)
    port: int = Field(default=51821)

    public_key: str = Field(max_length=100, unique=True)
    private_key_enc: str | None = Field(default=None, max_length=500)

    is_active: bool = Field(default=True)
    is_online: bool = Field(default=True)
    is_entry_node: bool = Field(default=False)
    is_exit_node: bool = Field(default=False)

    max_clients: int = Field(default=1000)
    current_clients: int = Field(default=0)
    last_ping_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
# END_BLOCK: class VPNNode



# START_BLOCK: class VPNRoute
class VPNRoute(SQLModel, table=True):
    """Logical path that connects an entry node to an exit node."""

    __tablename__ = "vpn_routes"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100, unique=True)
    entry_node_id: int = Field(foreign_key="vpn_nodes.id", index=True)
    # Exit node stays nullable during the migration from the legacy single-hop model.
    exit_node_id: int | None = Field(default=None, foreign_key="vpn_nodes.id", index=True)

    is_active: bool = Field(default=True)
    is_default: bool = Field(default=False)
    priority: int = Field(default=100)
    max_clients: int = Field(default=1000)
    current_clients: int = Field(default=0)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
# END_BLOCK: class VPNRoute


# START_BLOCK: class VPNClient
class VPNClient(SQLModel, table=True):
    """VPN client configuration for a user."""

    __tablename__ = "vpn_clients"

    id: int | None = Field(default=None, primary_key=True)
    # User linkage remains for compatibility queries, but uniqueness now belongs
    # to the logical device so one user can own multiple device-bound peers.
    user_id: int = Field(foreign_key="users.id", index=True)
    device_id: int | None = Field(default=None, foreign_key="user_devices.id", index=True, unique=True)
    # Legacy compatibility field. New runtime logic should prefer route/entry/exit
    # topology and treat server_id only as a mirror for rollback paths.
    server_id: int | None = Field(default=None, foreign_key="vpn_servers.id", index=True)
    route_id: int | None = Field(default=None, foreign_key="vpn_routes.id", index=True)
    entry_node_id: int | None = Field(default=None, foreign_key="vpn_nodes.id", index=True)
    exit_node_id: int | None = Field(default=None, foreign_key="vpn_nodes.id", index=True)

    # Client keys (private key encrypted)
    public_key: str = Field(max_length=100, unique=True)
    private_key_enc: str = Field(max_length=500)  # Encrypted with Fernet
    preshared_key_enc: str | None = Field(default=None, max_length=500)

    # Network configuration
    address: str = Field(max_length=20, unique=True)  # e.g., 172.29.0.2

    # Status
    is_active: bool = Field(default=True)

    # Statistics
    total_upload_bytes: int = Field(default=0)
    total_download_bytes: int = Field(default=0)
    last_handshake_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))

    # Relationships
    user: "User" = Relationship(back_populates="vpn_clients")
    device: "UserDevice" = Relationship(back_populates="vpn_clients")
    server: VPNServer | None = Relationship(back_populates="clients")
# END_BLOCK: class VPNClient


# START_BLOCK: class VPNConfig
class VPNConfig(SQLModel):
    """Generated VPN configuration for client download."""
    config: str
    server_name: str
    server_location: str
    route_name: str | None = None
    entry_server_name: str | None = None
    entry_server_location: str | None = None
    exit_server_name: str | None = None
    exit_server_location: str | None = None
    address: str
    public_key: str
    created_at: datetime
# END_BLOCK: class VPNConfig


# START_BLOCK: class VPNStats
class VPNStats(SQLModel):
    """VPN usage statistics."""
    total_upload_bytes: int
    total_download_bytes: int
    last_handshake_at: datetime | None
    is_connected: bool
    server_name: str
    server_location: str
# END_BLOCK: class VPNStats


# START_BLOCK: class ServerStatus
class ServerStatus(SQLModel):
    """Deprecated legacy server status shape kept for compatibility."""
    id: int
    name: str
    location: str
    is_online: bool
    current_clients: int
    max_clients: int
    load_percent: float
# END_BLOCK: class ServerStatus
