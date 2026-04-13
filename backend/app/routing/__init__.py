# FILE: backend/app/routing/__init__.py
# VERSION: 2.0.0
# ROLE: BARREL
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: Simplified routing module barrel for Full Tunnel architecture.
#            Exports only the RoutingManager singleton for tunnel health checks.
#   SCOPE: Re-exports routing_manager singleton from manager.py.
#   DEPENDS: M-001 (backend-core)
#   LINKS: M-007 (routing), V-M-007
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   RoutingManager, routing_manager - Simplified tunnel health manager (Full Tunnel)
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.10.0 - Phase-17 Step-1: Removed all split-tunneling exports.
#                          Only RoutingManager and routing_manager remain.
#   LAST_CHANGE: v2.8.0  - Added full GRACE MODULE_CONTRACT and MODULE_MAP
# END_CHANGE_SUMMARY
#
"""Simplified routing module for Full Tunnel architecture.

Only exports the RoutingManager singleton for tunnel health checks.
All split-tunneling, ipset, and policy logic has been removed.
"""
from app.routing.manager import RoutingManager, routing_manager

__all__ = [
    "RoutingManager",
    "routing_manager",
]
