"""MTProto personal proxy domain package.

# FILE: backend/app/mtproto/__init__.py
# VERSION: 1.0.0
# ROLE: BARREL
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: Package boundary for Phase-29 MTProto assignment and provisioning code
#   SCOPE: Groups assignment models, repository, schemas, and provisioning service
#   DEPENDS: M-042, M-043
#   LINKS: docs/modules/M-042.xml, docs/modules/M-043.xml
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   models - SQLModel assignment records
#   repository - Assignment persistence helpers
#   provisioning - Deterministic SNI, fake-TLS secret, and issue/reissue service
#   service - Stable public re-export path for provisioning service
#   schemas - Owner-safe response contracts
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.1.0 - Added service re-export path to the package map
#   LAST_CHANGE: v1.0.0 - Created Phase-29 MTProto package boundary
# END_CHANGE_SUMMARY
"""

__all__ = []
