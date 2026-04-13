# FILE: backend/app/routing/manager.py
# VERSION: 3.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Simplified routing manager for Full Tunnel architecture.
#            Just tracks tunnel health and provides simple status.
#   SCOPE: Tunnel status checks, basic initialization. No ipset, no split-tunneling.
#   DEPENDS: M-001 (backend-core)
#   LINKS: M-003 (vpn), M-006 (admin-api)
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   RoutingManager - Simple tunnel health manager
#   routing_manager - Global singleton instance
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.10.0 - Phase-17: Simplified to Full Tunnel. Removed split-tunneling logic.
#   LAST_CHANGE: v2.9.0  - Phase-15: Added automated RU IP range updates (REMOVED in v2.10.0)
# END_CHANGE_SUMMARY
"""
Simplified Routing Manager for Full Tunnel.

In this architecture, all traffic goes through the DE server via the RU entry node.
We only track tunnel health here; routing is handled by the host's default FORWARD/NAT rules.
"""

import asyncio
from dataclasses import dataclass
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger


@dataclass
class TunnelStatus:
    interface: str
    status: str  # "up", "down", "degraded"
    last_check: str | None = None


class RoutingManager:
    """
    Simplified manager for Full Tunnel.
    No ipset, no split-tunneling. Just health checks.
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._initialized = False
        self._status = TunnelStatus(interface="awg0", status="unknown")

    async def initialize(self) -> None:
        """Initialize routing manager and start health checks."""
        if self._initialized:
            return

        # Schedule health check every 60 seconds
        self.scheduler.add_job(
            self._check_tunnel_health,
            'interval',
            seconds=60,
            id='tunnel_health_check',
        )
        self.scheduler.start()

        # Initial check
        await self._check_tunnel_health()

        self._initialized = True
        logger.info("[ROUTING] Simplified RoutingManager initialized (Full Tunnel mode)")

    async def _check_tunnel_health(self) -> None:
        """Check if the tunnel interface is up and has at least one peer with handshake."""
        try:
            # Use 'awg show' to check tunnel health because with network_mode: host
            # we can see host interfaces. We check both interface existence AND peer status.
            proc = await asyncio.create_subprocess_exec(
                "awg", "show", self._status.interface,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            output = stdout.decode() + stderr.decode()

            if proc.returncode == 0 and "interface:" in output and "peer:" in output:
                self._status.status = "up"
                logger.debug(f"[ROUTING] Tunnel {self._status.interface} is UP")
            elif proc.returncode == 0 and "interface:" in output:
                self._status.status = "degraded"
                logger.warning(f"[ROUTING] Tunnel {self._status.interface} is UP but has no peers")
            else:
                self._status.status = "down"
                logger.warning(f"[ROUTING] Tunnel {self._status.interface} is DOWN")

        except Exception as e:
            self._status.status = "error"
            logger.error(f"[ROUTING] Error checking tunnel health: {e}")

    async def get_status(self) -> TunnelStatus:
        """Get current tunnel status."""
        return self._status


# Global singleton
routing_manager = RoutingManager()
