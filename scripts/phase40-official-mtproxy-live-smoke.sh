#!/usr/bin/env bash
#
# FILE: scripts/phase40-official-mtproxy-live-smoke.sh
# VERSION: 1.0.0
# ROLE: SCRIPT
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Run redacted Phase-40 operator live checks for the official MTProxy edge.
#   SCOPE: Redacted-mode enforcement, HTTPS reachability check, TCP 443 reachability check, and explicit req_pq proof gate.
#   DEPENDS: M-051, M-052, M-053
#   LINKS: docs/modules/M-051.xml, docs/modules/M-052.xml, docs/modules/M-053.xml, docs/verification/V-M-052.xml
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   usage - Shows safe invocation without secrets.
#   check_https - Verifies browser HTTPS remains reachable.
#   check_tcp_443 - Verifies public TCP 443 accepts connections.
#   check_req_pq_proof - Requires operator-provided redacted req_pq proof for live closure.
#   BLOCK_PHASE40_LIVE_SMOKE - Redacted live official MTProxy smoke flow.
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-40 redacted live smoke gate scaffold.
# END_CHANGE_SUMMARY

set -euo pipefail

PUBLIC_HOST="${PUBLIC_HOST:-${KROTPN_PUBLIC_HOST:-krotpn.xyz}}"
PUBLIC_PORT="${PUBLIC_PORT:-443}"
REDACTED=0
REQUIRE_REQ_PQ=0
REQ_PQ_CONFIRMED="${PHASE40_REQ_PQ_CONFIRMED:-0}"
REQ_PQ_PROOF_FILE="${PHASE40_REQ_PQ_PROOF_FILE:-}"

usage() {
    printf '%s\n' "Usage: $0 --redacted [--require-req-pq]"
    printf '%s\n' "Optional env: PUBLIC_HOST, PUBLIC_PORT, PHASE40_REQ_PQ_CONFIRMED=1, PHASE40_REQ_PQ_PROOF_FILE=/path/to/redacted-proof"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --redacted)
            REDACTED=1
            shift
            ;;
        --require-req-pq)
            REQUIRE_REQ_PQ=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf '%s\n' "[Phase40Smoke][abort][UNKNOWN_ARG] arg=$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [ "$REDACTED" -ne 1 ]; then
    printf '%s\n' "[Phase40Smoke][redaction][FAIL] code=redacted_mode_required"
    exit 2
fi

# START_BLOCK_CHECK_HTTPS
check_https() {
    if curl -fsSI --max-time 10 "https://${PUBLIC_HOST}" >/dev/null; then
        printf '%s\n' "[Phase40Smoke][route][HTTPS_OK] host=${PUBLIC_HOST}"
        return 0
    fi
    printf '%s\n' "[Phase40Smoke][route][HTTPS_FAIL] host=${PUBLIC_HOST}"
    return 1
}
# END_BLOCK_CHECK_HTTPS

# START_BLOCK_CHECK_TCP_443
check_tcp_443() {
    if command -v nc >/dev/null 2>&1; then
        nc -z -w 5 "$PUBLIC_HOST" "$PUBLIC_PORT"
    else
        timeout 5 bash -c "</dev/tcp/${PUBLIC_HOST}/${PUBLIC_PORT}"
    fi
    printf '%s\n' "[Phase40Smoke][route][TCP_443_OK] host=${PUBLIC_HOST} port=${PUBLIC_PORT}"
}
# END_BLOCK_CHECK_TCP_443

# START_BLOCK_CHECK_REQ_PQ_PROOF
check_req_pq_proof() {
    if [ "$REQUIRE_REQ_PQ" -ne 1 ]; then
        printf '%s\n' "[Phase40Smoke][req_pq][SKIPPED] code=explicit_live_gate_not_requested"
        return 0
    fi
    if [ "$REQ_PQ_CONFIRMED" = "1" ]; then
        printf '%s\n' "[Phase40Smoke][req_pq][PASS_REDACTED] source=operator_confirmation"
        return 0
    fi
    if [ -n "$REQ_PQ_PROOF_FILE" ] && [ -f "$REQ_PQ_PROOF_FILE" ] && grep -q "PASS_REDACTED" "$REQ_PQ_PROOF_FILE"; then
        printf '%s\n' "[Phase40Smoke][req_pq][PASS_REDACTED] source=proof_file"
        return 0
    fi
    printf '%s\n' "[Phase40Smoke][req_pq][FAIL] code=redacted_req_pq_proof_required"
    return 1
}
# END_BLOCK_CHECK_REQ_PQ_PROOF

# START_BLOCK_PHASE40_LIVE_SMOKE
check_https
check_tcp_443
check_req_pq_proof
printf '%s\n' "[Phase40Smoke][redaction][PASS]"
# END_BLOCK_PHASE40_LIVE_SMOKE
