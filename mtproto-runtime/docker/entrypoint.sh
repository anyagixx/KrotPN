#!/usr/bin/env bash

# FILE: docker/entrypoint.sh
# VERSION: 1.1.0
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
#   wait_for_policy_listen_ip - waits for private policy bind IP before starting Erlang release
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.1.0 - Wait for POLICY_LISTEN_IP to exist so reboot races do not crash-loop with eaddrnotavail.
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

wait_for_policy_listen_ip() {
  local bind_ip="${POLICY_LISTEN_IP:-127.0.0.1}"
  local timeout_seconds="${POLICY_LISTEN_IP_WAIT_SECONDS:-90}"
  local deadline=$((SECONDS + timeout_seconds))
  local escaped_ip

  case "${bind_ip}" in
    ""|"0.0.0.0"|"127.0.0.1"|"localhost")
      return 0
      ;;
  esac

  escaped_ip="${bind_ip//./\\.}"
  until grep -Eq "(^|[[:space:]])${escaped_ip}($|[[:space:]])" /proc/net/fib_trie 2>/dev/null; do
    if [ "${SECONDS}" -ge "${deadline}" ]; then
      log_line "WAIT_POLICY_IP" "policy bind IP ${bind_ip} is unavailable after ${timeout_seconds}s"
      return 1
    fi
    log_line "WAIT_POLICY_IP" "waiting for policy bind IP ${bind_ip}"
    sleep 2
  done

  log_line "WAIT_POLICY_IP" "policy bind IP ${bind_ip} is available"
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
    wait_for_policy_listen_ip
    exec /opt/kpproton/rel/bin/kpproton foreground
    ;;
  *)
    exec "$@"
    ;;
esac
# END_BLOCK_COMMAND_DISPATCH
