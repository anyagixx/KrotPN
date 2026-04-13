# FILE: backend/app/routing/router.py
# VERSION: 2.0.0
# ROLE: ENTRY_POINT
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: Minimal routing status endpoints for Full Tunnel architecture.
#            Provides tunnel health status and basic VPN stats for frontend/admin.
#   SCOPE: GET /api/v1/routing/status, GET /api/v1/admin/vpn-stats
#   DEPENDS: M-007 (routing manager), M-006 (admin API)
#   LINKS: M-007 (routing), M-003 (vpn)
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   get_routing_status - Returns tunnel health status
#   get_admin_vpn_stats - Returns basic VPN stats for admin dashboard
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.10.0 - Phase-17: Simplified to minimal status endpoints (Full Tunnel)
# END_CHANGE_SUMMARY
"""
Minimal routing router for Full Tunnel.
Provides only tunnel health status — no policy management.
"""

from fastapi import APIRouter

from app.routing.manager import routing_manager

router = APIRouter(prefix="/api/v1/routing", tags=["routing"])


# START_BLOCK: get_routing_status
@router.get("/status")
async def get_routing_status():
    """Get current tunnel health status (public endpoint for frontend)."""
    tunnel_status = await routing_manager.get_status()
    return {
        "tunnel_status": tunnel_status.status,
        "interface": tunnel_status.interface,
        "message": "Full Tunnel active" if tunnel_status.status == "up" else "Tunnel inactive",
    }
# END_BLOCK: get_routing_status


# START_BLOCK: get_admin_vpn_stats
@router.get("/admin/vpn-stats")
async def get_admin_vpn_stats():
    """Get basic VPN stats for admin dashboard (public for simplicity)."""
    tunnel_status = await routing_manager.get_status()
    return {
        "tunnel_status": tunnel_status.status,
        "interface": tunnel_status.interface,
        "mode": "full_tunnel",
        "message": "All traffic routed via DE server",
    }
# END_BLOCK: get_admin_vpn_stats
