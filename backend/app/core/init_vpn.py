"""
Bootstrap VPN server records from environment configuration.
"""

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.vpn.models import VPNServer


async def ensure_default_vpn_server(session: AsyncSession) -> VPNServer | None:
    """Ensure RU entry node exists in application database if env provides it."""
    if not settings.vpn_server_public_key or not settings.vpn_server_endpoint:
        logger.info("[VPN] Default VPN server bootstrap skipped: env is incomplete")
        return None

    result = await session.execute(
        select(VPNServer).where(VPNServer.public_key == settings.vpn_server_public_key)
    )
    server = result.scalar_one_or_none()

    if server:
        server.name = settings.vpn_server_name
        server.location = settings.vpn_server_location
        server.endpoint = settings.vpn_server_endpoint
        server.port = settings.vpn_port
        server.max_clients = settings.vpn_server_max_clients
        server.is_active = True
        server.is_online = True
        server.is_entry_node = True
        server.is_exit_node = False
        await session.flush()
        await session.refresh(server)
        logger.info(f"[VPN] Default VPN server synced: {server.name} ({server.endpoint})")
        return server

    server = VPNServer(
        name=settings.vpn_server_name,
        location=settings.vpn_server_location,
        endpoint=settings.vpn_server_endpoint,
        port=settings.vpn_port,
        public_key=settings.vpn_server_public_key,
        is_active=True,
        is_online=True,
        is_entry_node=True,
        is_exit_node=False,
        max_clients=settings.vpn_server_max_clients,
    )

    session.add(server)
    await session.flush()
    await session.refresh(server)
    logger.info(f"[VPN] Default VPN server created: {server.name} ({server.endpoint})")
    return server
