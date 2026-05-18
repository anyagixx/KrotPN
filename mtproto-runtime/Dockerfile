# FILE: Dockerfile
# VERSION: 1.0.0
# START_MODULE_CONTRACT
#   PURPOSE: Define the foundational container build contract for the future unified KPprotoN Erlang release.
#   SCOPE: Runtime base image, filesystem layout, env defaults, entrypoint wiring, and build-time dependency surface.
#   DEPENDS: deploy/.env.example, docker/entrypoint.sh
#   LINKS: M-RELEASE, M-CONFIG, M-DEPLOY
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   base stage - installs runtime dependencies for the future release
#   runtime stage - provides stable directories, labels, and entrypoint
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added foundational Docker build contract and runtime filesystem layout.
# END_CHANGE_SUMMARY

# START_BLOCK_BASE_STAGE
FROM erlang:27 AS build

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    APP_HOME=/opt/kpproton \
    APP_DATA_DIR=/var/lib/kpproton \
    APP_CERTS_DIR=/certs \
    PORTAL_HTTP_INTERNAL_PORT=8080

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates openssl curl git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/kpproton

COPY rebar.config rebar.lock* /opt/kpproton/
COPY config /opt/kpproton/config
COPY src /opt/kpproton/src
COPY apps /opt/kpproton/apps
COPY deploy /opt/kpproton/deploy

RUN rebar3 as prod release
# END_BLOCK_BASE_STAGE

# START_BLOCK_RUNTIME_STAGE
FROM erlang:27 AS runtime

LABEL org.opencontainers.image.title="KPprotoN" \
      org.opencontainers.image.description="Foundation image for a unified MTProto proxy + portal deployment" \
      org.opencontainers.image.source="local-workspace"

WORKDIR /opt/kpproton

RUN mkdir -p /opt/kpproton/releases /opt/kpproton/apps /var/lib/kpproton/dets /var/lib/kpproton/tokens /certs

COPY --from=build /opt/kpproton/_build/prod/rel/kpproton /opt/kpproton/rel
COPY --from=build /opt/kpproton/apps/kpproton_portal/priv/static /opt/kpproton/apps/kpproton_portal/priv/static
COPY --from=build /opt/kpproton/apps/kpproton_proxy/src/mtproto /opt/kpproton/apps/kpproton_proxy/src/mtproto
COPY --from=build /opt/kpproton/deploy/.env.example /opt/kpproton/deploy/.env.example
COPY docker/entrypoint.sh /usr/local/bin/kpproton-entrypoint

RUN chmod +x /usr/local/bin/kpproton-entrypoint

ENV KP_RELEASE_MODE=foundation \
    DETS_DATA_DIR=/var/lib/kpproton/dets \
    TOKEN_DATA_DIR=/var/lib/kpproton/tokens \
    TLS_CERT_PATH=/certs/live/example.com/fullchain.pem \
    TLS_KEY_PATH=/certs/live/example.com/privkey.pem \
    KP_STATIC_DIR=/opt/kpproton/apps/kpproton_portal/priv/static

EXPOSE 443 8080

ENTRYPOINT ["/usr/local/bin/kpproton-entrypoint"]
CMD ["start"]
# END_BLOCK_RUNTIME_STAGE
