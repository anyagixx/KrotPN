#!/bin/sh
# FILE: official-mtproxy/entrypoint.sh
# VERSION: 1.0.0
# ROLE: SCRIPT
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Start the KrotPN official MTProxy secret-control supervisor.
#   SCOPE: Runtime directory preparation, permissions, and supervisor exec.
#   DEPENDS: M-052, M-053, official-mtproxy/secret-control.py
#   LINKS: docs/modules/M-052.xml, docs/modules/M-053.xml, docs/plans/Phase-40.xml
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   main - Prepares data dir and launches Python supervisor.
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-40 official MTProxy supervisor entrypoint.
# END_CHANGE_SUMMARY

set -eu

# START_BLOCK_PREPARE_RUNTIME
DATA_DIR="${MTPROXY_DATA_DIR:-/data}"
mkdir -p "$DATA_DIR"
chown mtproxy:mtproxy "$DATA_DIR" 2>/dev/null || true
chmod 700 "$DATA_DIR" 2>/dev/null || true
# END_BLOCK_PREPARE_RUNTIME

# START_BLOCK_EXEC_SUPERVISOR
exec python3 /opt/krotpn/official-mtproxy/secret-control.py
# END_BLOCK_EXEC_SUPERVISOR
