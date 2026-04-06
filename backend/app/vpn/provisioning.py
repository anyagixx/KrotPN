# FILE: backend/app/vpn/provisioning.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: VPN client provisioning — new client creation, reprovisioning, internal/device client flows
#   SCOPE: ProvisioningMixin with _provision_new_client, _reprovision_client, provision_internal_client, provision_device_client
#   DEPENDS: M-001 (core security/encrypt), M-003 (vpn models), M-020 (device registry)
#   LINKS: M-003 (vpn), V-M-003
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   ProvisioningMixin - Mixin providing VPN client provisioning helpers
#   ProvisioningMixin._provision_new_client - Create a new VPNClient with WG peer
#   ProvisioningMixin._reprovision_client - Re-provision an existing client with new keys
#   ProvisioningMixin.provision_internal_client - Provision or reprovision internal user client
#   ProvisioningMixin.provision_device_client - Provision or reprovision device-bound client
#   ProvisioningMixin._get_used_ips - Get set of used IPs for a node/server
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Converted to full GRACE MODULE_CONTRACT/MAP format
# END_CHANGE_SUMMARY
#
"""VPN client provisioning helpers."""

from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_data
from app.vpn.models import VPNClient, VPNNode, VPNRoute, VPNServer


from app.vpn.models import VPNClient, VPNNode, VPNRoute, VPNServer


class ProvisioningMixin:
    """Mixin providing VPN client provisioning helpers."""

    session: AsyncSession
    wg: ...

    async def get_legacy_server_for_node(
        self,
        node: VPNNode | None,
        *,
        create: bool = True,
    ) -> VPNServer | None: ...

    async def _apply_topology_client_delta(self, client: VPNClient, delta: int) -> None: ...

    async def _apply_topology_client_delta_by_ids(
        self,
        route_id: int | None,
        entry_node_id: int | None,
        exit_node_id: int | None,
        delta: int,
    ) -> None: ...

    async def _get_used_ips(
        self,
        *,
        entry_node_id: int | None,
        server_id: int,
        exclude_client_id: int | None = None,
    ) -> set[str]:
        if entry_node_id is not None:
            query = select(VPNClient.address).where(
                (VPNClient.entry_node_id == entry_node_id)
                | ((VPNClient.entry_node_id == None) & (VPNClient.server_id == server_id))
            )
        else:
            query = select(VPNClient.address).where(VPNClient.server_id == server_id)
        if exclude_client_id is not None:
            query = query.where(VPNClient.id != exclude_client_id)
        result = await self.session.execute(query)
        return {row[0] for row in result.fetchall()}

    async def _provision_new_client(
        self,
        user_id: int,
        device_id: int | None,
        server: VPNServer,
        *,
        route: VPNRoute | None = None,
        entry_node: VPNNode | None = None,
        exit_node: VPNNode | None = None,
    ) -> VPNClient:
        if entry_node is None:
            raise ValueError("Entry node is required for provisioning")
        server = await self.get_legacy_server_for_node(entry_node)
        private_key, public_key = await self.wg.generate_keypair()
        used_ips = await self._get_used_ips(entry_node_id=entry_node.id, server_id=server.id)
        address = self.wg.get_next_client_ip(used_ips)
        private_key_enc = encrypt_data(private_key)

        client = VPNClient(
            user_id=user_id,
            device_id=device_id,
            server_id=server.id,
            route_id=route.id if route is not None else None,
            entry_node_id=entry_node.id if entry_node is not None else None,
            exit_node_id=exit_node.id if exit_node is not None else None,
            public_key=public_key,
            private_key_enc=private_key_enc,
            address=address,
            is_active=True,
        )
        self.session.add(client)
        await self.wg.add_peer(public_key, address)
        logger.info(
            "[VPN][peer][VPN_PEER_APPLIED] "
            f"user_id={client.user_id} client_id={client.id} address={address} "
            f"route_id={client.route_id} entry_node_id={client.entry_node_id}"
        )
        server.current_clients += 1
        await self._apply_topology_client_delta(client, 1)
        await self.session.flush()
        return client

    async def _reprovision_client(
        self,
        client: VPNClient,
        server: VPNServer,
        *,
        route: VPNRoute | None = None,
        entry_node: VPNNode | None = None,
        exit_node: VPNNode | None = None,
    ) -> VPNClient:
        if entry_node is None:
            raise ValueError("Entry node is required for reprovisioning")
        previous_entry_node_id = client.entry_node_id
        previous_exit_node_id = client.exit_node_id
        previous_route_id = client.route_id
        previous_public_key = client.public_key
        server = await self.get_legacy_server_for_node(entry_node)
        private_key, public_key = await self.wg.generate_keypair()
        used_ips = await self._get_used_ips(
            entry_node_id=entry_node.id,
            server_id=server.id,
            exclude_client_id=int(client.id) if client.id is not None else None,
        )
        address = self.wg.get_next_client_ip(used_ips)

        client.server_id = server.id
        client.route_id = route.id if route is not None else None
        client.entry_node_id = entry_node.id if entry_node is not None else None
        client.exit_node_id = exit_node.id if exit_node is not None else None
        client.public_key = public_key
        client.private_key_enc = encrypt_data(private_key)
        client.address = address
        client.is_active = True
        client.total_upload_bytes = 0
        client.total_download_bytes = 0
        client.last_handshake_at = None
        client.updated_at = datetime.now(timezone.utc)

        await self.wg.add_peer(public_key, address)
        if previous_public_key:
            await self.wg.remove_peer(previous_public_key)
            logger.info(
                f"[VPN][peer][VPN_PEER_REMOVED] "
                f"user_id={client.user_id} client_id={client.id} old_public_key={previous_public_key[:20]}... reprovision=true"
            )
        logger.info(
            "[VPN][peer][VPN_PEER_APPLIED] "
            f"user_id={client.user_id} client_id={client.id} address={address} "
            f"route_id={client.route_id} entry_node_id={client.entry_node_id} reprovision=true"
        )
        server.current_clients += 1
        await self._apply_topology_client_delta_by_ids(previous_route_id, previous_entry_node_id, previous_exit_node_id, -1)
        await self._apply_topology_client_delta(client, 1)
        await self.session.flush()
        return client

    async def provision_internal_client(
        self,
        user_id: int,
        *,
        reprovision: bool = False,
    ) -> VPNClient:
        if not reprovision:
            return await self.create_client(user_id)

        existing = await self.get_user_client(user_id, active_only=False)
        if existing is None:
            return await self.create_client(user_id)

        route, entry_node, exit_node, server = await self._select_topology_for_existing_client(existing)
        if entry_node is None and server is not None:
            _, entry_node, exit_node = await self._resolve_topology_for_server(server)
        if entry_node is not None:
            server = await self.get_legacy_server_for_node(entry_node)
        if not server or entry_node is None:
            raise ValueError("No available VPN servers")

        if existing.is_active:
            await self.deactivate_client(existing)

        reprovisioned = await self._reprovision_client(
            existing, server, route=route, entry_node=entry_node, exit_node=exit_node,
        )
        await self.session.refresh(reprovisioned)
        return reprovisioned

    async def provision_device_client(
        self,
        user_id: int,
        device_id: int,
        *,
        reprovision: bool = False,
    ) -> VPNClient:
        if not reprovision:
            return await self.create_client(user_id, device_id=device_id)

        existing = await self.get_device_client(device_id, active_only=False)
        if existing is None:
            return await self.create_client(user_id, device_id=device_id)

        route, entry_node, exit_node, server = await self._select_topology_for_existing_client(existing)
        if entry_node is None and server is not None:
            _, entry_node, exit_node = await self._resolve_topology_for_server(server)
        if entry_node is not None:
            server = await self.get_legacy_server_for_node(entry_node)
        if not server or entry_node is None:
            raise ValueError("No available VPN servers")

        if existing.is_active:
            await self.deactivate_client(existing)

        reprovisioned = await self._reprovision_client(
            existing, server, route=route, entry_node=entry_node, exit_node=exit_node,
        )
        await self.session.refresh(reprovisioned)
        return reprovisioned
