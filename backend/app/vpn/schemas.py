"""
VPN schemas for API requests and responses.
"""
# <!-- GRACE: module="M-003" contract="vpn-schemas" -->

from datetime import datetime

from pydantic import Field

from sqlmodel import SQLModel


class VPNConfigResponse(SQLModel):
    """VPN configuration response."""
    config: str
    server_name: str
    server_location: str
    address: str
    created_at: datetime


class VPNStatsResponse(SQLModel):
    """VPN statistics response."""
    total_upload_bytes: int = 0
    total_download_bytes: int = 0
    total_upload_formatted: str = "0 B"
    total_download_formatted: str = "0 B"
    last_handshake_at: datetime | None = None
    is_connected: bool = False
    server_name: str
    server_location: str


class ServerStatusResponse(SQLModel):
    """Server status response."""
    id: int
    name: str
    location: str
    is_online: bool
    current_clients: int
    max_clients: int
    load_percent: float


class ServerListResponse(SQLModel):
    """List of servers."""
    servers: list[ServerStatusResponse]


class ServerCreate(SQLModel):
    """Schema for creating a server."""
    name: str = Field(..., min_length=1, max_length=100)
    location: str = Field(..., min_length=1, max_length=100)
    endpoint: str = Field(..., min_length=1, max_length=255)
    public_key: str = Field(..., min_length=1, max_length=100)
    private_key: str | None = None
    port: int = Field(default=51821, ge=1, le=65535)
    is_entry_node: bool = True
    is_exit_node: bool = False
    max_clients: int = Field(default=100, ge=1)


class ServerUpdate(SQLModel):
    """Schema for updating a server."""
    name: str | None = None
    location: str | None = None
    endpoint: str | None = None
    is_active: bool | None = None
    max_clients: int | None = None
