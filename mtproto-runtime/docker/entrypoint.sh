#!/usr/bin/env bash

# FILE: docker/entrypoint.sh
# VERSION: 1.0.0
# START_MODULE_CONTRACT
#   PURPOSE: Provide a stable container entrypoint for the foundational KPprotoN image until the unified Erlang release is wired in.
#   SCOPE: Minimal runtime validation, directory bootstrap, and placeholder boot command dispatch.
#   DEPENDS: deploy/.env.example
#   LINKS: M-RELEASE, V-M-RELEASE
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   log_line - emits structured startup messages
#   ensure_dir - creates required runtime directories
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added foundational runtime entrypoint and directory bootstrap logic.
# END_CHANGE_SUMMARY

set -euo pipefail

log_line() {
  local block="$1"
  shift
  echo "[M-RELEASE][boot][${block}] $*"
}

ensure_dir() {
  local path="$1"
  mkdir -p "${path}"
}

# START_BLOCK_VALIDATE_ENV
: "${DETS_DATA_DIR:=/var/lib/kpproton/dets}"
: "${TOKEN_DATA_DIR:=/var/lib/kpproton/tokens}"
# END_BLOCK_VALIDATE_ENV

# START_BLOCK_BOOTSTRAP_DIRS
ensure_dir "${DETS_DATA_DIR}"
ensure_dir "${TOKEN_DATA_DIR}"
log_line "START_RUNTIME" "runtime directories prepared"
# END_BLOCK_BOOTSTRAP_DIRS

# START_BLOCK_COMMAND_DISPATCH
case "${1:-foundation-ready}" in
  foundation-ready)
    log_line "START_RUNTIME" "foundation image is ready for later release wiring"
    ;;
  start)
    log_line "START_RUNTIME" "starting relx release"
    exec /opt/kpproton/rel/bin/kpproton foreground
    ;;
  *)
    exec "$@"
    ;;
esac
# END_BLOCK_COMMAND_DISPATCH
