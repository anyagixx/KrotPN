"""VPN config generation helpers."""

from app.core.security import decrypt_data
from app.vpn.models import VPNClient, VPNConfig, VPNNode, VPNServer


class ConfigMixin:
    """Mixin providing VPN config generation helpers."""

    session: ...
    wg: ...

    async def get_route(self, route_id: int | None) -> ...: ...
    async def get_node(self, node_id: int | None) -> VPNNode | None: ...
    async def get_server(self, server_id: int | None) -> VPNServer | None: ...

    async def get_client_config(self, client: VPNClient) -> VPNConfig:
        route = await self.get_route(client.route_id)
        entry_node = await self.get_node(client.entry_node_id)
        exit_node = await self.get_node(client.exit_node_id)
        server = await self.get_server(client.server_id)

        if entry_node is None and server is not None:
            _, entry_node, exit_node = await self._resolve_topology_for_server(server)
        if entry_node is None:
            raise ValueError("Entry node not found")

        private_key = decrypt_data(client.private_key_enc)

        endpoint = entry_node.endpoint or (server.endpoint if server else None) or await self.wg.get_server_endpoint()
        if not endpoint:
            raise ValueError("Cannot determine server endpoint")

        config_content = self.wg.create_client_config(
            private_key=private_key,
            address=client.address,
            server_public_key=entry_node.public_key if entry_node.public_key else (server.public_key if server else ""),
            endpoint=endpoint,
        )
        from loguru import logger
        logger.info(
            "[VPN][config][VPN_CONFIG_RENDERED] "
            f"user_id={client.user_id} client_id={client.id} route_id={client.route_id} "
            f"entry_node_id={client.entry_node_id} resolved_endpoint={endpoint}"
        )

        return VPNConfig(
            config=config_content,
            server_name=entry_node.name,
            server_location=entry_node.location,
            route_name=route.name if route else None,
            entry_server_name=entry_node.name,
            entry_server_location=entry_node.location,
            exit_server_name=exit_node.name if exit_node else None,
            exit_server_location=exit_node.location if exit_node else None,
            address=client.address,
            public_key=client.public_key,
            created_at=client.created_at,
        )
