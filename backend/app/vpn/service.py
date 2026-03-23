"""
VPN service for business logic.
"""
# <!-- GRACE: module="M-003" contract="vpn-service" -->

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decrypt_data, encrypt_data
from app.vpn.amneziawg import wg_manager
from app.vpn.models import VPNClient, VPNConfig, VPNServer, VPNStats, ServerStatus


class VPNService:
    """Service for VPN operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.wg = wg_manager

    async def get_server(self, server_id: int) -> VPNServer | None:
        """Get VPN server by ID."""
        return await self.session.get(VPNServer, server_id)

    async def get_active_server(self) -> VPNServer | None:
        """Get an active server for new clients."""
        result = await self.session.execute(
            select(VPNServer)
            .where(
                VPNServer.is_active == True,
                VPNServer.is_online == True,
                VPNServer.is_entry_node == True,
                VPNServer.current_clients < VPNServer.max_clients,
            )
            .order_by(VPNServer.current_clients.asc())
        )
        return result.scalar_one_or_none()

    async def create_client(
        self,
        user_id: int,
        server_id: int | None = None,
    ) -> VPNClient:
        """
        Create a new VPN client for a user.
        
        Args:
            user_id: User ID
            server_id: Optional specific server ID
            
        Returns:
            Created VPNClient
        """
        existing_client = await self.get_user_client(user_id, active_only=False)

        # Get server
        if server_id:
            server = await self.get_server(server_id)
        elif existing_client is not None:
            server = await self._select_server_for_existing_client(existing_client)
        else:
            server = await self.get_active_server()

        if not server:
            raise ValueError("No available VPN servers")

        if existing_client is not None:
            if existing_client.is_active:
                if server_id and existing_client.server_id != server.id:
                    raise ValueError("User already has an active VPN client on another server")
                return existing_client

            if existing_client.server_id == server.id:
                await self.activate_client(existing_client)
                await self.session.refresh(existing_client)
                return existing_client

            reprovisioned = await self._reprovision_client(existing_client, server)
            await self.session.refresh(reprovisioned)
            return reprovisioned

        client = await self._provision_new_client(user_id=user_id, server=server)
        await self.session.refresh(client)
        return client

    async def get_client(self, client_id: int) -> VPNClient | None:
        """Get VPN client by ID."""
        return await self.session.get(VPNClient, client_id)

    async def get_user_client(self, user_id: int, active_only: bool = True) -> VPNClient | None:
        """Get VPN client for user."""
        query = select(VPNClient).where(VPNClient.user_id == user_id)
        if active_only:
            query = query.where(VPNClient.is_active == True)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_client_config(self, client: VPNClient) -> VPNConfig:
        """
        Generate VPN configuration for client.
        
        Args:
            client: VPNClient instance
            
        Returns:
            VPNConfig with configuration content
        """
        server = await self.get_server(client.server_id)
        if not server:
            raise ValueError("Server not found")
        
        # Decrypt private key
        private_key = decrypt_data(client.private_key_enc)
        
        # Get server endpoint
        endpoint = server.endpoint or await self.wg.get_server_endpoint()
        if not endpoint:
            raise ValueError("Cannot determine server endpoint")
        
        # Generate config
        config_content = self.wg.create_client_config(
            private_key=private_key,
            address=client.address,
            server_public_key=server.public_key,
            endpoint=endpoint,
        )
        
        return VPNConfig(
            config=config_content,
            server_name=server.name,
            server_location=server.location,
            address=client.address,
            public_key=client.public_key,
            created_at=client.created_at,
        )

    async def deactivate_client(self, client: VPNClient) -> None:
        """Deactivate a VPN client."""
        client.is_active = False
        await self.wg.remove_peer(client.public_key)
        
        # Update server client count
        server = await self.get_server(client.server_id)
        if server and server.current_clients > 0:
            server.current_clients -= 1
        
        await self.session.flush()

    async def activate_client(self, client: VPNClient) -> None:
        """Activate a VPN client."""
        client.is_active = True
        await self.wg.add_peer(client.public_key, client.address)
        
        # Update server client count
        server = await self.get_server(client.server_id)
        if server:
            server.current_clients += 1
        
        await self.session.flush()

    async def update_client_stats(self, client: VPNClient) -> None:
        """Update client traffic statistics."""
        stats = await self.wg.get_peer_stats()
        
        if client.public_key in stats:
            peer_stats = stats[client.public_key]
            client.total_upload_bytes = peer_stats["upload"]
            client.total_download_bytes = peer_stats["download"]
            client.last_handshake_at = peer_stats["last_handshake"]
            client.updated_at = datetime.utcnow()
            await self.session.flush()

    async def get_client_stats(self, client: VPNClient) -> VPNStats:
        """Get VPN client statistics."""
        await self.update_client_stats(client)
        
        server = await self.get_server(client.server_id)
        
        # Check if connected (handshake within last 3 minutes)
        is_connected = False
        if client.last_handshake_at:
            delta = datetime.utcnow() - client.last_handshake_at
            is_connected = delta.total_seconds() < 180
        
        return VPNStats(
            total_upload_bytes=client.total_upload_bytes,
            total_download_bytes=client.total_download_bytes,
            last_handshake_at=client.last_handshake_at,
            is_connected=is_connected,
            server_name=server.name if server else "Unknown",
            server_location=server.location if server else "Unknown",
        )

    async def list_servers(self) -> list[VPNServer]:
        """List all VPN servers."""
        result = await self.session.execute(
            select(VPNServer).order_by(VPNServer.created_at)
        )
        return list(result.scalars().all())

    async def get_server_statuses(self) -> list[ServerStatus]:
        """Get status of all servers."""
        servers = await self.list_servers()
        
        statuses = []
        for server in servers:
            load = (server.current_clients / server.max_clients * 100) if server.max_clients > 0 else 0
            statuses.append(ServerStatus(
                id=server.id,
                name=server.name,
                location=server.location,
                is_online=server.is_online,
                current_clients=server.current_clients,
                max_clients=server.max_clients,
                load_percent=round(load, 1),
            ))
        
        return statuses

    async def create_server(
        self,
        name: str,
        location: str,
        endpoint: str,
        public_key: str,
        private_key: str | None = None,
        port: int = 51821,
        is_entry_node: bool = True,
        is_exit_node: bool = False,
        max_clients: int = 100,
    ) -> VPNServer:
        """Create a new VPN server."""
        private_key_enc = encrypt_data(private_key) if private_key else None
        
        server = VPNServer(
            name=name,
            location=location,
            endpoint=endpoint,
            port=port,
            public_key=public_key,
            private_key_enc=private_key_enc,
            is_entry_node=is_entry_node,
            is_exit_node=is_exit_node,
            max_clients=max_clients,
        )
        
        self.session.add(server)
        await self.session.flush()
        await self.session.refresh(server)
        
        return server

    async def update_server_status(
        self,
        server_id: int,
        is_online: bool,
    ) -> None:
        """Update server online status."""
        server = await self.get_server(server_id)
        if server:
            server.is_online = is_online
            server.last_ping_at = datetime.utcnow()
            await self.session.flush()

    async def _select_server_for_existing_client(self, client: VPNClient) -> VPNServer | None:
        """Reuse the existing server when it is still suitable, otherwise pick a new active one."""
        current_server = await self.get_server(client.server_id)
        if (
            current_server
            and current_server.is_active
            and current_server.is_online
            and current_server.is_entry_node
            and (
                client.is_active
                or current_server.current_clients < current_server.max_clients
            )
        ):
            return current_server

        return await self.get_active_server()

    async def _get_used_ips(self, server_id: int, exclude_user_id: int | None = None) -> set[str]:
        """Collect already allocated client IPs for a server."""
        query = select(VPNClient.address).where(VPNClient.server_id == server_id)
        if exclude_user_id is not None:
            query = query.where(VPNClient.user_id != exclude_user_id)

        result = await self.session.execute(query)
        return {row[0] for row in result.fetchall()}

    async def _provision_new_client(self, user_id: int, server: VPNServer) -> VPNClient:
        """Provision a fresh VPN client record."""
        private_key, public_key = await self.wg.generate_keypair()
        used_ips = await self._get_used_ips(server.id)
        address = self.wg.get_next_client_ip(used_ips)
        private_key_enc = encrypt_data(private_key)

        client = VPNClient(
            user_id=user_id,
            server_id=server.id,
            public_key=public_key,
            private_key_enc=private_key_enc,
            address=address,
            is_active=True,
        )
        self.session.add(client)

        await self.wg.add_peer(public_key, address)
        server.current_clients += 1
        await self.session.flush()
        return client

    async def _reprovision_client(self, client: VPNClient, server: VPNServer) -> VPNClient:
        """Reassign an inactive client record to a new server with fresh keys."""
        private_key, public_key = await self.wg.generate_keypair()
        used_ips = await self._get_used_ips(server.id, exclude_user_id=client.user_id)
        address = self.wg.get_next_client_ip(used_ips)

        client.server_id = server.id
        client.public_key = public_key
        client.private_key_enc = encrypt_data(private_key)
        client.address = address
        client.is_active = True
        client.total_upload_bytes = 0
        client.total_download_bytes = 0
        client.last_handshake_at = None
        client.updated_at = datetime.utcnow()

        await self.wg.add_peer(public_key, address)
        server.current_clients += 1
        await self.session.flush()
        return client
