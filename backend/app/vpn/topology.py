# FILE: backend/app/vpn/topology.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: VPN topology management — node/route CRUD, status helpers, legacy server sync
#   SCOPE: TopologyMixin with create/update/delete node/route, status checks, legacy sync, role normalization
#   DEPENDS: M-001 (core security/encrypt), M-003 (vpn models), M-007 (routing)
#   LINKS: M-003 (vpn), V-M-003
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   TopologyMixin - Mixin providing VPN topology management helpers
#   TopologyMixin.list_nodes - List all VPNNode records
#   TopologyMixin.list_routes - List all VPNRoute records
#   TopologyMixin.get_node_statuses - Return node status with load percentage
#   TopologyMixin.get_route_statuses - Return route status with tunnel health
#   TopologyMixin.create_node - Create a new VPNNode
#   TopologyMixin.update_node - Update an existing VPNNode
#   TopologyMixin.delete_node - Delete a VPNNode (with client/route checks)
#   TopologyMixin.create_route - Create a new VPNRoute
#   TopologyMixin.update_route - Update an existing VPNRoute
#   TopologyMixin.delete_route - Delete a VPNRoute (with client check)
#   TopologyMixin.list_legacy_servers - List legacy VPNServer records
#   TopologyMixin._normalize_node_role - Convert role string to normalized tuple
#   TopologyMixin._route_capacity - Calculate route capacity from node limits
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Converted to full GRACE MODULE_CONTRACT/MAP format, removed duplicate contract blocks
# END_CHANGE_SUMMARY
#
"""VPN topology (node/route) management helpers."""

from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_data
from app.routing.manager import routing_manager
from app.vpn.models import VPNClient, VPNNode, VPNRoute, VPNServer


class TopologyMixin:
    """Mixin providing VPN topology management helpers."""

    session: AsyncSession
    wg: ...

    async def get_node(self, node_id: int | None) -> VPNNode | None: ...
    async def get_route(self, route_id: int | None) -> VPNRoute | None: ...
    async def get_server(self, server_id: int | None) -> VPNServer | None: ...
    async def get_server_by_public_key(self, public_key: str) -> VPNServer | None: ...
    async def get_legacy_server_for_node(self, node: VPNNode | None, *, create: bool = True) -> VPNServer | None: ...
    async def get_active_server(self) -> VPNServer | None: ...
    async def get_active_entry_node(self) -> VPNNode | None: ...
    async def get_default_route(self) -> VPNRoute | None: ...
    async def get_active_route(self) -> VPNRoute | None: ...
    async def get_server_for_route(self, route: VPNRoute | None) -> VPNServer | None: ...
    async def get_client(self, client_id: int) -> VPNClient | None: ...
    async def get_user_client(self, user_id: int, active_only: bool = True) -> VPNClient | None: ...
    async def get_device_client(self, device_id: int, active_only: bool = True) -> VPNClient | None: ...
    async def list_device_clients(self, device_id: int, *, active_only: bool = False) -> list[VPNClient]: ...
    async def deactivate_client(self, client: VPNClient) -> None: ...
    async def activate_client(self, client: VPNClient) -> None: ...
    async def _provision_new_client(self, user_id: int, device_id: int | None, server: VPNServer, *, route: VPNRoute | None = None, entry_node: VPNNode | None = None, exit_node: VPNNode | None = None) -> VPNClient: ...
    async def _reprovision_client(self, client: VPNClient, server: VPNServer, *, route: VPNRoute | None = None, entry_node: VPNNode | None = None, exit_node: VPNNode | None = None) -> VPNClient: ...
    async def _sync_client_topology(self, client: VPNClient, *, route: VPNRoute | None, entry_node: VPNNode | None, exit_node: VPNNode | None) -> None: ...
    async def _apply_topology_client_delta(self, client: VPNClient, delta: int) -> None: ...
    async def _apply_topology_client_delta_by_ids(self, route_id: int | None, entry_node_id: int | None, exit_node_id: int | None, delta: int) -> None: ...
    async def _select_server_for_existing_client(self, client: VPNClient) -> VPNServer | None: ...
    async def _select_topology_for_existing_client(self, client: VPNClient) -> tuple[VPNRoute | None, VPNNode | None, VPNNode | None, VPNServer | None]: ...
    async def _select_topology_for_new_client(self) -> tuple[VPNRoute | None, VPNNode | None, VPNNode | None, VPNServer | None]: ...
    async def _resolve_topology_for_server(self, server: VPNServer) -> tuple[VPNRoute | None, VPNNode | None, VPNNode | None]: ...
    async def _sync_legacy_server_for_node(self, node: VPNNode) -> None: ...

    async def list_nodes(self) -> list[VPNNode]:
        result = await self.session.execute(select(VPNNode).order_by(VPNNode.created_at))
        return list(result.scalars().all())

    async def list_routes(self) -> list[VPNRoute]:
        result = await self.session.execute(select(VPNRoute).order_by(VPNRoute.priority.asc(), VPNRoute.created_at.asc()))
        return list(result.scalars().all())

    async def get_node_statuses(self) -> list[dict[str, Any]]:
        nodes = await self.list_nodes()
        statuses: list[dict[str, Any]] = []
        for node in nodes:
            load = (node.current_clients / node.max_clients * 100) if node.max_clients > 0 else 0
            statuses.append({
                "id": node.id, "name": node.name, "role": node.role,
                "country_code": node.country_code, "location": node.location,
                "endpoint": node.endpoint, "port": node.port, "public_key": node.public_key,
                "is_active": node.is_active, "is_online": node.is_online,
                "is_entry_node": node.is_entry_node, "is_exit_node": node.is_exit_node,
                "current_clients": node.current_clients, "max_clients": node.max_clients,
                "load_percent": round(load, 1),
            })
        return statuses

    async def get_route_statuses(self) -> list[dict[str, Any]]:
        routes = await self.list_routes()
        statuses: list[dict[str, Any]] = []
        tunnel_status = await routing_manager.get_status()
        for route in routes:
            entry_node = await self.get_node(route.entry_node_id)
            exit_node = await self.get_node(route.exit_node_id)
            load = (route.current_clients / route.max_clients * 100) if route.max_clients > 0 else 0
            tunnel_status_str = tunnel_status.status if exit_node is not None else "not_configured"
            statuses.append({
                "id": route.id, "name": route.name,
                "entry_node_id": route.entry_node_id,
                "entry_node_name": entry_node.name if entry_node else "Unknown",
                "entry_node_location": entry_node.location if entry_node else "Unknown",
                "exit_node_id": route.exit_node_id,
                "exit_node_name": exit_node.name if exit_node else None,
                "exit_node_location": exit_node.location if exit_node else None,
                "is_active": route.is_active, "is_default": route.is_default,
                "tunnel_interface": tunnel_status.interface if exit_node is not None else None,
                "tunnel_status": tunnel_status_str, "priority": route.priority,
                "current_clients": route.current_clients, "max_clients": route.max_clients,
                "load_percent": round(load, 1),
            })
        return statuses

    async def create_node(
        self, *, name: str, role: str, country_code: str, location: str,
        endpoint: str, port: int = 51821, public_key: str,
        private_key: str | None = None, is_active: bool = True,
        is_online: bool = True, max_clients: int = 100,
    ) -> VPNNode:
        normalized_role, is_entry_node, is_exit_node = self._normalize_node_role(role)
        existing = await self.session.execute(select(VPNNode).where(VPNNode.public_key == public_key))
        if existing.scalar_one_or_none() is not None:
            raise ValueError("Node with this public key already exists")
        private_key_enc = encrypt_data(private_key) if private_key else None
        node = VPNNode(
            name=name, role=normalized_role, country_code=country_code.upper(),
            location=location, endpoint=endpoint, port=port, public_key=public_key,
            private_key_enc=private_key_enc, is_active=is_active, is_online=is_online,
            is_entry_node=is_entry_node, is_exit_node=is_exit_node, max_clients=max_clients,
        )
        self.session.add(node)
        await self.session.flush()
        await self._sync_legacy_server_for_node(node)
        await self.session.refresh(node)
        return node

    async def update_node(self, node: VPNNode, **changes: Any) -> VPNNode:
        normalized_role = changes.get("role", node.role)
        normalized_role, is_entry_node, is_exit_node = self._normalize_node_role(normalized_role)
        public_key = changes.get("public_key", node.public_key)
        if public_key != node.public_key:
            existing = await self.session.execute(
                select(VPNNode).where(VPNNode.public_key == public_key, VPNNode.id != node.id)
            )
            if existing.scalar_one_or_none() is not None:
                raise ValueError("Node with this public key already exists")
        for field in ("name", "country_code", "location", "endpoint", "port", "public_key", "is_active", "is_online", "max_clients"):
            if field in changes:
                val = changes[field]
                setattr(node, field, val.upper() if field == "country_code" else val)
        if "private_key" in changes:
            node.private_key_enc = encrypt_data(changes["private_key"]) if changes["private_key"] else None
        node.role = normalized_role
        node.is_entry_node = is_entry_node
        node.is_exit_node = is_exit_node
        node.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self._sync_legacy_server_for_node(node)
        await self.session.refresh(node)
        return node

    async def delete_node(self, node: VPNNode) -> None:
        if await self._count_node_clients(node.id) > 0:
            raise ValueError("Cannot delete node with assigned clients")
        route_refs = await self.session.execute(
            select(func.count(VPNRoute.id)).where(
                (VPNRoute.entry_node_id == node.id) | (VPNRoute.exit_node_id == node.id)
            )
        )
        if int(route_refs.scalar() or 0) > 0:
            raise ValueError("Cannot delete node used by existing routes")
        legacy_server = await self.get_server_by_public_key(node.public_key)
        if legacy_server is not None:
            if legacy_server.current_clients > 0:
                raise ValueError("Cannot delete node while its legacy server has active clients")
            await self.session.delete(legacy_server)
        await self.session.delete(node)
        await self.session.flush()

    async def create_route(
        self, *, name: str, entry_node_id: int, exit_node_id: int | None = None,
        is_active: bool = True, is_default: bool = False, priority: int = 100,
        max_clients: int | None = None,
    ) -> VPNRoute:
        existing = await self.session.execute(select(VPNRoute).where(VPNRoute.name == name))
        if existing.scalar_one_or_none() is not None:
            raise ValueError("Route with this name already exists")
        entry_node = await self.get_node(entry_node_id)
        if entry_node is None:
            raise ValueError("Entry node not found")
        if not entry_node.is_entry_node:
            raise ValueError("Selected entry node cannot accept client connections")
        exit_node = await self.get_node(exit_node_id)
        if exit_node_id is not None and exit_node is None:
            raise ValueError("Exit node not found")
        if exit_node is not None and not exit_node.is_exit_node:
            raise ValueError("Selected exit node is not marked as an exit node")
        route = VPNRoute(
            name=name, entry_node_id=entry_node_id, exit_node_id=exit_node_id,
            is_active=is_active, is_default=is_default, priority=priority,
            max_clients=max_clients or self._route_capacity(entry_node, exit_node),
            current_clients=0,
        )
        self.session.add(route)
        await self.session.flush()
        if is_default:
            await self._set_default_route(route)
        await self.session.refresh(route)
        return route

    async def update_route(self, route: VPNRoute, **changes: Any) -> VPNRoute:
        entry_node_id = changes.get("entry_node_id", route.entry_node_id)
        exit_node_id = changes.get("exit_node_id", route.exit_node_id)
        entry_node = await self.get_node(entry_node_id)
        if entry_node is None:
            raise ValueError("Entry node not found")
        if not entry_node.is_entry_node:
            raise ValueError("Selected entry node cannot accept client connections")
        exit_node = await self.get_node(exit_node_id)
        if exit_node_id is not None and exit_node is None:
            raise ValueError("Exit node not found")
        if exit_node is not None and not exit_node.is_exit_node:
            raise ValueError("Selected exit node is not marked as an exit node")
        if "name" in changes and changes["name"] != route.name:
            existing = await self.session.execute(
                select(VPNRoute).where(VPNRoute.name == changes["name"], VPNRoute.id != route.id)
            )
            if existing.scalar_one_or_none() is not None:
                raise ValueError("Route with this name already exists")
            route.name = changes["name"]
        route.entry_node_id = entry_node_id
        route.exit_node_id = exit_node_id
        if "is_active" in changes:
            route.is_active = changes["is_active"]
        if "priority" in changes:
            route.priority = changes["priority"]
        if "max_clients" in changes:
            route.max_clients = changes["max_clients"]
        elif "entry_node_id" in changes or "exit_node_id" in changes:
            route.max_clients = self._route_capacity(entry_node, exit_node)
        route.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        if changes.get("is_default") is True:
            await self._set_default_route(route)
        elif changes.get("is_default") is False:
            route.is_default = False
            await self.session.flush()
        await self.session.refresh(route)
        return route

    async def delete_route(self, route: VPNRoute) -> None:
        result = await self.session.execute(
            select(func.count(VPNClient.id)).where(VPNClient.route_id == route.id)
        )
        if int(result.scalar() or 0) > 0:
            raise ValueError("Cannot delete route with assigned clients")
        await self.session.delete(route)
        await self.session.flush()

    async def _count_node_clients(self, node_id: int | None) -> int:
        if node_id is None:
            return 0
        result = await self.session.execute(
            select(func.count(VPNClient.id)).where(
                (VPNClient.entry_node_id == node_id) | (VPNClient.exit_node_id == node_id)
            )
        )
        return int(result.scalar() or 0)

    async def _set_default_route(self, route: VPNRoute) -> None:
        result = await self.session.execute(
            select(VPNRoute).where(VPNRoute.id != route.id, VPNRoute.is_default == True)
        )
        for other in result.scalars().all():
            other.is_default = False
        route.is_default = True
        await self.session.flush()

    async def _sync_legacy_server_for_node(self, node: VPNNode) -> None:
        legacy_server = await self.get_server_by_public_key(node.public_key)
        if not node.is_entry_node:
            if legacy_server is not None and legacy_server.current_clients == 0:
                await self.session.delete(legacy_server)
                await self.session.flush()
            return
        if legacy_server is None:
            legacy_server = VPNServer(
                name=node.name, location=node.location, endpoint=node.endpoint,
                port=node.port, public_key=node.public_key, private_key_enc=node.private_key_enc,
                is_active=node.is_active, is_online=node.is_online, is_entry_node=True,
                is_exit_node=node.is_exit_node, max_clients=node.max_clients,
                current_clients=node.current_clients,
            )
            self.session.add(legacy_server)
            await self.session.flush()
            return
        legacy_server.name = node.name
        legacy_server.location = node.location
        legacy_server.endpoint = node.endpoint
        legacy_server.port = node.port
        legacy_server.public_key = node.public_key
        legacy_server.private_key_enc = node.private_key_enc
        legacy_server.is_active = node.is_active
        legacy_server.is_online = node.is_online
        legacy_server.is_entry_node = True
        legacy_server.is_exit_node = node.is_exit_node
        legacy_server.max_clients = node.max_clients
        legacy_server.updated_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def list_legacy_servers(self) -> list[VPNServer]:
        result = await self.session.execute(select(VPNServer).order_by(VPNServer.created_at))
        return list(result.scalars().all())

    async def set_legacy_server_online(self, server_id: int, is_online: bool) -> None:
        server = await self.get_server(server_id)
        if server is not None:
            server.is_online = is_online
            server.last_ping_at = datetime.now(timezone.utc)
            await self.session.flush()

    def _normalize_node_role(self, role: str) -> tuple[str, bool, bool]:
        normalized = (role or "entry").strip().lower()
        if normalized == "combined":
            return normalized, True, True
        if normalized == "exit":
            return normalized, False, True
        return "entry", True, False

    def _route_capacity(self, entry_node: VPNNode, exit_node: VPNNode | None) -> int:
        if exit_node is None:
            return entry_node.max_clients
        return min(entry_node.max_clients, exit_node.max_clients)
