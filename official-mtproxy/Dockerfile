# FILE: official-mtproxy/Dockerfile
# VERSION: 1.0.0
# ROLE: CONFIG
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: Build the DE official Telegram MTProxy runtime with a small KrotPN secret-control supervisor.
#   SCOPE: Compile official MTProxy from TelegramMessenger/MTProxy, install Python supervisor, expose MTProxy 443 and private policy API.
#   DEPENDS: M-052, M-053, deploy/mtproto-de-compose.yml
#   LINKS: docs/modules/M-052.xml, docs/modules/M-053.xml, docs/plans/Phase-40.xml
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   builder - Compiles official mtproto-proxy from Telegram's source tree.
#   runtime - Runs secret-control.py, which manages official mtproto-proxy -S secret flags.
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-40 official MTProxy runtime image.
# END_CHANGE_SUMMARY

# START_BLOCK_BUILD_OFFICIAL_MTPROXY
FROM debian:bookworm-slim AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        build-essential \
        libssl-dev \
        zlib1g-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git clone --depth 1 https://github.com/TelegramMessenger/MTProxy.git /src/MTProxy
RUN make -C /src/MTProxy
# END_BLOCK_BUILD_OFFICIAL_MTPROXY

# START_BLOCK_RUNTIME_IMAGE
FROM debian:bookworm-slim AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl python3 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --home /nonexistent --shell /usr/sbin/nologin mtproxy \
    && mkdir -p /data /opt/krotpn/official-mtproxy \
    && chown mtproxy:mtproxy /data

COPY --from=builder /src/MTProxy/objs/bin/mtproto-proxy /usr/local/bin/mtproto-proxy
COPY secret-control.py /opt/krotpn/official-mtproxy/secret-control.py
COPY entrypoint.sh /opt/krotpn/official-mtproxy/entrypoint.sh

RUN chmod +x /usr/local/bin/mtproto-proxy /opt/krotpn/official-mtproxy/entrypoint.sh

ENV MTPROXY_DATA_DIR=/data \
    MTPROXY_BINARY=/usr/local/bin/mtproto-proxy \
    MTPROXY_PORT=443 \
    MTPROXY_STATS_PORT=2398 \
    MTPROXY_WORKERS=1 \
    MTPROTO_POLICY_BIND_IP=127.0.0.1 \
    MTPROTO_POLICY_PORT=18080

EXPOSE 443 18080

ENTRYPOINT ["/opt/krotpn/official-mtproxy/entrypoint.sh"]
# END_BLOCK_RUNTIME_IMAGE
