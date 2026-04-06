# FILE: backend/app/vpn/__init__.py
# VERSION: 1.0.0
# ROLE: BARREL
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: VPN provisioning, config generation, device-bound peer management, topology-aware client assignment
#   SCOPE: WG/AWG management, client provisioning, config rendering, topology selection, handshake monitoring
#   DEPENDS: M-001 (backend-core), M-002 (users), M-007 (routing)
#   LINKS: M-003 (vpn), V-M-003
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   VPNClient, VPNServer, VPNConfig, VPNStats - Database models for VPN topology and clients
#   AmneziaWGManager, wg_manager - AWG interface management (peer add/remove, config generation)
#   VPNService - High-level service: provision, generate config, revoke, rotate, stats
#   vpn_router, admin_vpn_router - FastAPI routers for user-facing and admin VPN operations
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""VPN module exports."""
from app.vpn.models import VPNClient, VPNConfig, VPNServer, VPNStats
from app.vpn.amneziawg import AmneziaWGManager, wg_manager
from app.vpn.service import VPNService
from app.vpn.router import router as vpn_router
from app.vpn.router import admin_router as admin_vpn_router

__all__ = [
    # Models
    "VPNClient",
    "VPNServer",
    "VPNConfig",
    "VPNStats",
    # AmneziaWG
    "AmneziaWGManager",
    "wg_manager",
    # Service
    "VPNService",
    # Routers
    "vpn_router",
    "admin_vpn_router",
]
