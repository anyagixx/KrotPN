"""
VPN API router.
"""
# <!-- GRACE: module="M-003" api-group="VPN API" -->

import io
from typing import Annotated

import qrcode
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.core import CurrentAdmin, CurrentUser, DBSession
from app.vpn.models import VPNClient
from app.vpn.schemas import (
    ServerCreate,
    ServerListResponse,
    ServerStatusResponse,
    ServerUpdate,
    VPNConfigResponse,
    VPNStatsResponse,
)
from app.vpn.service import VPNService

router = APIRouter(prefix="/api/vpn", tags=["vpn"])
admin_router = APIRouter(prefix="/api/admin/servers", tags=["admin"])


def format_bytes(bytes_count: int) -> str:
    """Format bytes to human readable string."""
    if bytes_count == 0:
        return "0 B"
    
    units = ["B", "KB", "MB", "GB", "TB"]
    k = 1024
    i = 0
    
    while bytes_count >= k and i < len(units) - 1:
        bytes_count /= k
        i += 1
    
    return f"{bytes_count:.1f} {units[i]}"


async def get_or_provision_user_client(
    user_id: int,
    session: DBSession,
) -> VPNClient | None:
    """Return existing VPN client or provision one for users with active access."""
    service = VPNService(session)
    client = await service.get_user_client(user_id)
    if client is not None:
        return client

    from app.billing.service import BillingService

    billing_service = BillingService(session)
    subscription = await billing_service.get_user_subscription(user_id)
    if not subscription:
        return None

    try:
        return await service.create_client(user_id)
    except ValueError:
        return None


# ==================== User Endpoints ====================

@router.get("/config", response_model=VPNConfigResponse)
async def get_vpn_config(
    current_user: CurrentUser,
    session: DBSession,
):
    """Get VPN configuration for current user."""
    service = VPNService(session)
    
    client = await get_or_provision_user_client(current_user.id, session)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VPN client not found. Please activate your subscription first.",
        )
    
    if not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="VPN access is disabled",
        )
    
    config = await service.get_client_config(client)
    
    return VPNConfigResponse(
        config=config.config,
        server_name=config.server_name,
        server_location=config.server_location,
        address=config.address,
        created_at=config.created_at,
    )


@router.get("/config/download")
async def download_vpn_config(
    current_user: CurrentUser,
    session: DBSession,
):
    """Download VPN configuration as .conf file."""
    service = VPNService(session)
    
    client = await get_or_provision_user_client(current_user.id, session)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VPN client not found",
        )
    
    config = await service.get_client_config(client)
    
    return StreamingResponse(
        iter([config.config]),
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename=krotvpn-{current_user.id}.conf"
        },
    )


@router.get("/config/qr")
async def get_vpn_config_qr(
    current_user: CurrentUser,
    session: DBSession,
):
    """Get VPN configuration as QR code image."""
    service = VPNService(session)
    
    client = await get_or_provision_user_client(current_user.id, session)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VPN client not found",
        )
    
    config = await service.get_client_config(client)
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(config.config)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Return as PNG
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    
    return StreamingResponse(buf, media_type="image/png")


@router.get("/stats", response_model=VPNStatsResponse)
async def get_vpn_stats(
    current_user: CurrentUser,
    session: DBSession,
):
    """Get VPN usage statistics for current user."""
    service = VPNService(session)
    
    client = await get_or_provision_user_client(current_user.id, session)
    if client is None:
        return VPNStatsResponse(
            total_upload_bytes=0,
            total_download_bytes=0,
            total_upload_formatted="0 B",
            total_download_formatted="0 B",
            last_handshake_at=None,
            is_connected=False,
            server_name="None",
            server_location="None",
        )
    
    stats = await service.get_client_stats(client)
    
    return VPNStatsResponse(
        total_upload_bytes=stats.total_upload_bytes,
        total_download_bytes=stats.total_download_bytes,
        total_upload_formatted=format_bytes(stats.total_upload_bytes),
        total_download_formatted=format_bytes(stats.total_download_bytes),
        last_handshake_at=stats.last_handshake_at,
        is_connected=stats.is_connected,
        server_name=stats.server_name,
        server_location=stats.server_location,
    )


@router.get("/servers", response_model=ServerListResponse)
async def list_servers(
    current_user: CurrentUser,
    session: DBSession,
):
    """List available VPN servers."""
    service = VPNService(session)
    statuses = await service.get_server_statuses()
    
    return ServerListResponse(
        servers=[
            ServerStatusResponse(
                id=s.id,
                name=s.name,
                location=s.location,
                is_online=s.is_online,
                current_clients=s.current_clients,
                max_clients=s.max_clients,
                load_percent=s.load_percent,
            )
            for s in statuses
        ]
    )


# ==================== Admin Endpoints ====================

@admin_router.get("", response_model=ServerListResponse)
async def admin_list_servers(
    admin: CurrentAdmin,
    session: DBSession,
):
    """List all VPN servers (admin)."""
    service = VPNService(session)
    statuses = await service.get_server_statuses()
    
    return ServerListResponse(
        servers=[
            ServerStatusResponse(
                id=s.id,
                name=s.name,
                location=s.location,
                is_online=s.is_online,
                current_clients=s.current_clients,
                max_clients=s.max_clients,
                load_percent=s.load_percent,
            )
            for s in statuses
        ]
    )


@admin_router.post("", status_code=status.HTTP_201_CREATED)
async def create_server(
    data: ServerCreate,
    admin: CurrentAdmin,
    session: DBSession,
):
    """Create a new VPN server."""
    service = VPNService(session)
    
    server = await service.create_server(
        name=data.name,
        location=data.location,
        endpoint=data.endpoint,
        public_key=data.public_key,
        private_key=data.private_key,
        port=data.port,
        is_entry_node=data.is_entry_node,
        is_exit_node=data.is_exit_node,
        max_clients=data.max_clients,
    )
    
    return {"id": server.id, "status": "created"}


@admin_router.get("/{server_id}", response_model=ServerStatusResponse)
async def get_server(
    server_id: int,
    admin: CurrentAdmin,
    session: DBSession,
):
    """Get server details."""
    service = VPNService(session)
    server = await service.get_server(server_id)
    
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )
    
    load = (server.current_clients / server.max_clients * 100) if server.max_clients > 0 else 0
    
    return ServerStatusResponse(
        id=server.id,
        name=server.name,
        location=server.location,
        is_online=server.is_online,
        current_clients=server.current_clients,
        max_clients=server.max_clients,
        load_percent=round(load, 1),
    )


@admin_router.put("/{server_id}")
async def update_server(
    server_id: int,
    data: ServerUpdate,
    admin: CurrentAdmin,
    session: DBSession,
):
    """Update server configuration."""
    service = VPNService(session)
    server = await service.get_server(server_id)
    
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )
    
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(server, field, value)
    
    await session.flush()
    
    return {"status": "updated"}


@admin_router.delete("/{server_id}")
async def delete_server(
    server_id: int,
    admin: CurrentAdmin,
    session: DBSession,
):
    """Delete a VPN server."""
    service = VPNService(session)
    server = await service.get_server(server_id)
    
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )
    
    if server.current_clients > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete server with active clients",
        )
    
    await session.delete(server)
    await session.flush()
    
    return {"status": "deleted"}
