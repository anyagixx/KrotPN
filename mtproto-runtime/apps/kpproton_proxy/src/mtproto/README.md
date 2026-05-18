<!-- FILE: apps/kpproton_proxy/src/mtproto/README.md -->
<!-- VERSION: 1.0.0 -->
<!-- START_MODULE_CONTRACT -->
<!--   PURPOSE: Document the MTProto edge routing and rollout rules that keep HTTPS and issued fake-TLS links aligned. -->
<!--   SCOPE: Shared 443 routing, policy reload model, and per-SNI secret rollout or rotation guidance. -->
<!--   DEPENDS: M-CONFIG -->
<!--   LINKS: M-PROXY-BRIDGE, M-CERTS, M-PROXY-ISSUE -->
<!-- END_MODULE_CONTRACT -->
<!-- -->
<!-- START_MODULE_MAP -->
<!--   Shared 443 Contract - edge behavior for HTTPS and MTProto -->
<!--   Policy Reload Model - how new SNI domains become active -->
<!--   Per-SNI Rollout - reissue requirements after hardening or rotation -->
<!-- END_MODULE_MAP -->
<!-- -->
<!-- START_CHANGE_SUMMARY -->
<!--   LAST_CHANGE: v1.0.0 - Added MyGRACE source contract metadata for the MTProto edge README. -->
<!-- END_CHANGE_SUMMARY -->
<!-- -->
<!-- START_BLOCK_EDGE_GUIDE -->
# KPprotoN MTProto Edge Routing

## Shared 443 Contract
- External listener port is `443`.
- TLS files are read from `/certs/live/<BASE_DOMAIN>/fullchain.pem` and `/certs/live/<BASE_DOMAIN>/privkey.pem`.
- Standard HTTPS requests fall through to Cowboy on `127.0.0.1:8080`.
- Domain-fronted MTProto requests are matched by SNI and resolved through the policy store.

## Policy Reload Model
- New user SNI domains are added through `apply_domain_policy`.
- Policy reload must be observable and reversible.
- If policy update fails, issuance must not be reported as successful.

## Per-SNI Rollout
- `per_sni_secrets` is enabled for the public listener.
- Changing `PROXY_SECRET_HEX` or `PROXY_SECRET_SALT` invalidates all previously issued `tg://proxy` links.
- After access-hardening rollout or any later secret rotation, every user must request a fresh email or reopen `/verify` to receive a reissued link for the same SNI.
<!-- END_BLOCK_EDGE_GUIDE -->
