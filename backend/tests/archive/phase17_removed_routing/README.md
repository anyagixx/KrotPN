# FILE: backend/tests/archive/phase17_removed_routing/README.md
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: Preserve obsolete routing-policy test sources removed from active pytest collection after the Full Tunnel migration.
#   SCOPE: Historical test archive only; files in this directory must not be collected as active tests.
#   DEPENDS: M-033 (mygrace-integrity-cleanup), M-017 (route-sync-runtime)
#   LINKS: docs/plans/Phase-21.xml, V-M-033
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   archived_*.py - Historical tests for deleted split-tunnel, DNS observer, route-policy, and ipset modules
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Phase-21 step-4 archived obsolete routing-policy tests so backend pytest collection matches Full Tunnel runtime.
# END_CHANGE_SUMMARY

These files are intentionally renamed away from `test_*.py`.

They document removed Phase-17 routing-policy/ipset behavior and must not be
treated as active verification for the current Full Tunnel architecture.
