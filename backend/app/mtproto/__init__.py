"""MTProto personal proxy domain package.

# FILE: backend/app/mtproto/__init__.py
# VERSION: 1.4.0
# ROLE: BARREL
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: Package boundary for MTProto assignment, provisioning, runtime, owner API, and availability diagnostics code
#   SCOPE: Groups assignment models, repository, schemas, provisioning service, runtime bridge, health, owner router, and redacted availability helpers
#   DEPENDS: M-042, M-043, M-044, M-045, M-051
#   LINKS: docs/modules/M-042.xml, docs/modules/M-043.xml, docs/modules/M-044.xml, docs/modules/M-045.xml, docs/modules/M-051.xml
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   models - SQLModel assignment records
#   repository - Assignment persistence helpers
#   provisioning - Deterministic SNI, fake-TLS secret, and issue/reissue service
#   service - Stable public re-export path for provisioning service
#   runtime_bridge - Phase-30 runtime policy bridge boundary
#   health - Secret-free runtime health summaries
#   router - Phase-31 owner-only MTProto user-cabinet API
#   schemas - Owner-safe response contracts
#   availability - Phase-39 redacted availability diagnostics and Telegram web-link helpers
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.4.0 - Added Phase-39 availability diagnostics package boundary.
#   LAST_CHANGE: v1.3.0 - Added Phase-31 owner API package boundary
#   LAST_CHANGE: v1.2.0 - Added Phase-30 runtime bridge and health boundaries
#   LAST_CHANGE: v1.1.0 - Added service re-export path to the package map
#   LAST_CHANGE: v1.0.0 - Created Phase-29 MTProto package boundary
# END_CHANGE_SUMMARY
"""

__all__ = []
