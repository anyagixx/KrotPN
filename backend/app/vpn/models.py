"""
VPN models for server and client configuration.
"""
# <!-- GRACE: module="M-003" entity="VPNServer, VPNClient" -->

from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.users.models import User


class VPNServer(SQLModel, table=True):
    """VPN server configuration."""
    
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
    subnet: str = Field(default="10.10.0.0/24")
    
    # Status
    is_active: bool = Field(default=True)
    is_entry_node: bool = Field(default=False)  # RU server = entry node
    is_exit_node: bool = Field(default=True)  # DE server = exit node
    
    # Capacity
    max_clients: int = Field(default=100)
    current_clients: int = Field(default=0)
    
    # Monitoring
    last_ping_at: datetime | None = Field(default=None)
    is_online: bool = Field(default=True)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    clients: list["VPNClient"] = Relationship(back_populates="server")


class VPNClient(SQLModel, table=True):
    """VPN client configuration for a user."""
    
    __tablename__ = "vpn_clients"
    
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    server_id: int = Field(foreign_key="vpn_servers.id", index=True)
    
    # Client keys (private key encrypted)
    public_key: str = Field(max_length=100, unique=True)
    private_key_enc: str = Field(max_length=500)  # Encrypted with Fernet
    
    # Network configuration
    address: str = Field(max_length=20, unique=True)  # e.g., 10.10.0.2
    
    # Status
    is_active: bool = Field(default=True)
    
    # Statistics
    total_upload_bytes: int = Field(default=0)
    total_download_bytes: int = Field(default=0)
    last_handshake_at: datetime | None = Field(default=None)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: "User" = Relationship(back_populates="vpn_clients")
    server: VPNServer = Relationship(back_populates="clients")


class VPNConfig(SQLModel):
    """Generated VPN configuration for client download."""
    config: str
    server_name: str
    server_location: str
    address: str
    public_key: str
    created_at: datetime


class VPNStats(SQLModel):
    """VPN usage statistics."""
    total_upload_bytes: int
    total_download_bytes: int
    last_handshake_at: datetime | None
    is_connected: bool
    server_name: str
    server_location: str


class ServerStatus(SQLModel):
    """VPN server status."""
    id: int
    name: str
    location: str
    is_online: bool
    current_clients: int
    max_clients: int
    load_percent: float
