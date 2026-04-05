"""
VPN service for business logic.

GRACE-lite module contract:
- Owns VPN client provisioning, topology selection and config generation.
- New topology model is `VPNNode` + `VPNRoute`; `VPNServer` remains a legacy compatibility mirror.
- Invariant: one `VPNClient` per user, with topology fields preferred over legacy `server_id`.
- This module is host-coupled through AmneziaWG tools and should be treated as infrastructure-sensitive code.

CHANGE_SUMMARY
- 2026-03-26: Added internal-client provisioning helper and stable provisioning/config-render trace markers for manual CLI parity.
- 2026-03-27: Added device-scoped client lookup helpers so revoke or block policy can target peer state through the existing VPN service.
- 2026-03-27: Relaxed user-level lookup and added optional device-bound provisioning during the multi-device migration window.
- 2026-03-27: Added explicit device reprovision helper so rotate flows can refresh one device config without changing logical ownership.
- 2026-04-05: Split large service into provisioning, config, and topology mixins to keep this file under 500 lines.
"""
# <!-- GRACE: module="M-003" contract="vpn-service" -->

from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.vpn.amneziawg import wg_manager
from app.vpn.config import ConfigMixin
from app.vpn.models import VPNClient, VPNNode, VPNRoute, VPNServer, VPNStats
from app.vpn.provisioning import ProvisioningMixin
from app.vpn.topology import TopologyMixin


class VPNService(ProvisioningMixin, ConfigMixin, TopologyMixin):
    """Service for VPN operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.wg = wg_manager

    async def get_server(self, server_id: int | None) -> VPNServer | None:
        """Get VPN server by ID."""
        if server_id is None:
            return None
        return await self.session.get(VPNServer, server_id)

    async def get_node(self, node_id: int | None) -> VPNNode | None:
        """Get VPN node by ID."""
        if node_id is None:
            return None
        return await self.session.get(VPNNode, node_id)

    async def get_route(self, route_id: int | None) -> VPNRoute | None:
        """Get VPN route by ID."""
        if route_id is None:
            return None
        return await self.session.get(VPNRoute, route_id)

    async def get_server_by_public_key(self, public_key: str) -> VPNServer | None:
        """Get legacy VPN server by public key."""
        result = await self.session.execute(
            select(VPNServer).where(VPNServer.public_key == public_key)
        )
        return result.scalar_one_or_none()

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

    async def get_active_entry_node(self) -> VPNNode | None:
        """Get an active entry node for route-less fallback."""
        result = await self.session.execute(
            select(VPNNode)
            .where(
                VPNNode.is_active == True,
                VPNNode.is_online == True,
                VPNNode.is_entry_node == True,
                VPNNode.current_clients < VPNNode.max_clients,
            )
            .order_by(VPNNode.current_clients.asc(), VPNNode.created_at.asc())
        )
        return result.scalar_one_or_none()

    async def get_default_route(self) -> VPNRoute | None:
        """Get the default active route for new clients."""
        result = await self.session.execute(
            select(VPNRoute)
            .where(
                VPNRoute.is_active == True,
                VPNRoute.is_default == True,
            )
            .order_by(VPNRoute.priority.asc(), VPNRoute.created_at.asc())
        )
        return result.scalar_one_or_none()

    async def get_active_route(self) -> VPNRoute | None:
        """Get the next active route when there is no explicit default."""
        route = await self.get_default_route()
        if route is not None:
            return route
        result = await self.session.execute(
            select(VPNRoute)
            .where(VPNRoute.is_active == True)
            .order_by(VPNRoute.priority.asc(), VPNRoute.created_at.asc())
        )
        return result.scalar_one_or_none()

    async def get_server_for_route(self, route: VPNRoute | None) -> VPNServer | None:
        """Resolve the legacy entry server used to provision a route."""
        if route is None:
            return None
        entry_node = await self.get_node(route.entry_node_id)
        return await self.get_legacy_server_for_node(entry_node, create=False)

    async def create_client(
        self,
        user_id: int,
        device_id: int | None = None,
        server_id: int | None = None,
    ) -> VPNClient:
        """Create a new VPN client for a user."""
        existing_client = (
            await self.get_device_client(device_id, active_only=False)
            if device_id is not None
            else await self.get_user_client(user_id, active_only=False)
        )
        route: VPNRoute | None = None
        entry_node: VPNNode | None = None
        exit_node: VPNNode | None = None

        if server_id:
            server = await self.get_server(server_id)
            if server is not None:
                route, entry_node, exit_node = await self._resolve_topology_for_server(server)
        elif existing_client is not None:
            route, entry_node, exit_node, server = await self._select_topology_for_existing_client(existing_client)
        else:
            route, entry_node, exit_node, server = await self._select_topology_for_new_client()

        if entry_node is None and server is not None:
            _, entry_node, exit_node = await self._resolve_topology_for_server(server)

        if entry_node is not None:
            server = await self.get_legacy_server_for_node(entry_node)

        if not server or entry_node is None:
            raise ValueError("No available VPN servers")

        if existing_client is not None:
            if existing_client.is_active:
                current_entry_node = await self.get_node(existing_client.entry_node_id)
                current_server = await self.get_server(existing_client.server_id)
                current_public_key = (
                    current_entry_node.public_key if current_entry_node is not None
                    else current_server.public_key if current_server is not None
                    else None
                )
                if server_id and current_public_key != entry_node.public_key:
                    raise ValueError("User already has an active VPN client on another server")
                await self._sync_client_topology(
                    existing_client, route=route, entry_node=entry_node, exit_node=exit_node,
                )
                await self.session.flush()
                return existing_client

            current_entry_node = await self.get_node(existing_client.entry_node_id)
            current_server = await self.get_server(existing_client.server_id)
            current_public_key = (
                current_entry_node.public_key if current_entry_node is not None
                else current_server.public_key if current_server is not None
                else None
            )

            if current_public_key == entry_node.public_key:
                await self.activate_client(existing_client)
                await self._sync_client_topology(
                    existing_client, route=route, entry_node=entry_node, exit_node=exit_node,
                )
                await self.session.refresh(existing_client)
                return existing_client

            reprovisioned = await self._reprovision_client(
                existing_client, server, route=route, entry_node=entry_node, exit_node=exit_node,
            )
            await self.session.refresh(reprovisioned)
            return reprovisioned

        client = await self._provision_new_client(
            user_id=user_id, device_id=device_id, server=server,
            route=route, entry_node=entry_node, exit_node=exit_node,
        )
        await self.session.refresh(client)
        return client

    async def get_client(self, client_id: int) -> VPNClient | None:
        """Get VPN client by ID."""
        return await self.session.get(VPNClient, client_id)

    async def get_user_client(self, user_id: int, active_only: bool = True) -> VPNClient | None:
        """Get one VPN client for a user for backward-compatible callers."""
        query = select(VPNClient).where(VPNClient.user_id == user_id)
        if active_only:
            query = query.where(VPNClient.is_active == True)
        result = await self.session.execute(query.order_by(VPNClient.created_at.asc(), VPNClient.id.asc()))
        return result.scalars().first()

    async def get_device_client(self, device_id: int, active_only: bool = True) -> VPNClient | None:
        """Get the VPN client currently bound to one logical device."""
        query = select(VPNClient).where(VPNClient.device_id == device_id)
        if active_only:
            query = query.where(VPNClient.is_active == True)
        result = await self.session.execute(query.order_by(VPNClient.created_at.asc(), VPNClient.id.asc()))
        return result.scalars().first()

    async def list_device_clients(self, device_id: int, *, active_only: bool = False) -> list[VPNClient]:
        """List VPN clients linked to one device."""
        query = select(VPNClient).where(VPNClient.device_id == device_id)
        if active_only:
            query = query.where(VPNClient.is_active == True)
        result = await self.session.execute(query.order_by(VPNClient.created_at.asc()))
        return list(result.scalars().all())

    async def deactivate_device_clients(self, device_id: int) -> int:
        """Deactivate every active VPN client bound to one device."""
        clients = await self.list_device_clients(device_id, active_only=True)
        for client in clients:
            await self.deactivate_client(client)
        return len(clients)

    async def deactivate_client(self, client: VPNClient) -> None:
        """Deactivate a VPN client."""
        client.is_active = False
        await self.wg.remove_peer(client.public_key)
        server = await self.get_server(client.server_id)
        if server and server.current_clients > 0:
            server.current_clients -= 1
        await self._apply_topology_client_delta(client, -1)
        await self.session.flush()

    async def activate_client(self, client: VPNClient) -> None:
        """Activate a VPN client."""
        client.is_active = True
        await self.wg.add_peer(client.public_key, client.address)
        server = await self.get_server(client.server_id)
        if server and server.current_clients < server.max_clients:
            server.current_clients += 1
        await self._apply_topology_client_delta(client, 1)
        await self.session.flush()

    async def update_client_stats(self, client: VPNClient) -> None:
        """Update client traffic statistics."""
        stats = await self.wg.get_peer_stats()
        if client.public_key in stats:
            peer_stats = stats[client.public_key]
            client.total_upload_bytes = peer_stats["upload"]
            client.total_download_bytes = peer_stats["download"]
            client.last_handshake_at = peer_stats["last_handshake"]
            client.updated_at = datetime.now(timezone.utc)
            await self.session.flush()

    async def get_client_stats(self, client: VPNClient) -> VPNStats:
        """Get VPN client statistics."""
        from app.vpn.models import VPNStats
        await self.update_client_stats(client)
        entry_node = await self.get_node(client.entry_node_id)
        server = await self.get_server(client.server_id)
        if entry_node is None and server is not None:
            _, entry_node, _ = await self._resolve_topology_for_server(server)
        is_connected = False
        if client.last_handshake_at:
            delta = datetime.now(timezone.utc) - client.last_handshake_at
            is_connected = delta.total_seconds() < 180
        return VPNStats(
            total_upload_bytes=client.total_upload_bytes,
            total_download_bytes=client.total_download_bytes,
            last_handshake_at=client.last_handshake_at,
            is_connected=is_connected,
            server_name=entry_node.name if entry_node else (server.name if server else "Unknown"),
            server_location=entry_node.location if entry_node else (server.location if server else "Unknown"),
        )

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

    async def _select_topology_for_existing_client(
        self, client: VPNClient,
    ) -> tuple[VPNRoute | None, VPNNode | None, VPNNode | None, VPNServer | None]:
        """Prefer the client's assigned route, then fall back to route/default/legacy server logic."""
        route = await self.get_route(client.route_id)
        entry_node = await self.get_node(client.entry_node_id)
        exit_node = await self.get_node(client.exit_node_id)
        if route is not None:
            if entry_node is None:
                entry_node = await self.get_node(route.entry_node_id)
            if exit_node is None:
                exit_node = await self.get_node(route.exit_node_id)
            server = await self.get_server_for_route(route)
            if entry_node is not None:
                return route, entry_node, exit_node, server
        server = await self._select_server_for_existing_client(client)
        if server is None:
            return None, None, None, None
        fallback_route, fallback_entry, fallback_exit = await self._resolve_topology_for_server(server)
        return fallback_route, fallback_entry, fallback_exit, server

    async def _select_topology_for_new_client(
        self,
    ) -> tuple[VPNRoute | None, VPNNode | None, VPNNode | None, VPNServer | None]:
        """Pick route-aware topology first, then fall back to the legacy entry server pool."""
        route = await self.get_active_route()
        if route is not None:
            entry_node = await self.get_node(route.entry_node_id)
            exit_node = await self.get_node(route.exit_node_id)
            server = await self.get_server_for_route(route)
            if entry_node is not None:
                return route, entry_node, exit_node, server
        entry_node = await self.get_active_entry_node()
        if entry_node is None:
            return None, None, None, None
        server = await self.get_legacy_server_for_node(entry_node)
        route, entry_node, exit_node = await self._resolve_topology_for_server(server)
        return route, entry_node, exit_node, server

    async def _resolve_topology_for_server(
        self, server: VPNServer,
    ) -> tuple[VPNRoute | None, VPNNode | None, VPNNode | None]:
        """Derive route-aware metadata from a legacy server record."""
        result = await self.session.execute(
            select(VPNNode).where(VPNNode.public_key == server.public_key)
        )
        entry_node = result.scalar_one_or_none()
        if entry_node is None:
            return None, None, None
        result = await self.session.execute(
            select(VPNRoute)
            .where(VPNRoute.entry_node_id == entry_node.id)
            .order_by(VPNRoute.is_default.desc(), VPNRoute.priority.asc(), VPNRoute.created_at.asc())
        )
        route = result.scalars().first()
        exit_node = await self.get_node(route.exit_node_id) if route is not None else None
        return route, entry_node, exit_node

    async def _sync_client_topology(
        self, client: VPNClient, *, route: VPNRoute | None, entry_node: VPNNode | None, exit_node: VPNNode | None,
    ) -> None:
        """Persist route-aware metadata on the client without breaking legacy fields."""
        client.route_id = route.id if route is not None else None
        client.entry_node_id = entry_node.id if entry_node is not None else None
        client.exit_node_id = exit_node.id if exit_node is not None else None

    async def _apply_topology_client_delta(self, client: VPNClient, delta: int) -> None:
        """Adjust node and route counters for a client assignment."""
        await self._apply_topology_client_delta_by_ids(
            client.route_id, client.entry_node_id, client.exit_node_id, delta,
        )

    async def _apply_topology_client_delta_by_ids(
        self, route_id: int | None, entry_node_id: int | None, exit_node_id: int | None, delta: int,
    ) -> None:
        """Adjust topology counters with floor-at-zero semantics."""
        route = await self.get_route(route_id)
        if route is not None:
            route.current_clients = max(0, route.current_clients + delta)
        entry_node = await self.get_node(entry_node_id)
        if entry_node is not None:
            entry_node.current_clients = max(0, entry_node.current_clients + delta)
        exit_node = await self.get_node(exit_node_id)
        if exit_node is not None:
            exit_node.current_clients = max(0, exit_node.current_clients + delta)

    async def get_legacy_server_for_node(
        self, node: VPNNode | None, *, create: bool = True,
    ) -> VPNServer | None:
        """Resolve or materialize the legacy server mirror for an entry-capable node."""
        if node is None:
            return None
        legacy_server = await self.get_server_by_public_key(node.public_key)
        if legacy_server is not None or not create:
            return legacy_server
        await self._sync_legacy_server_for_node(node)
        return await self.get_server_by_public_key(node.public_key)
