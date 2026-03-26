"""
Handshake anomaly detector for device-bound peers.

MODULE_CONTRACT
- PURPOSE: Observe live peer handshakes, update device presence metadata and record suspicious endpoint-churn or concurrency signals without auto-blocking by default.
- SCOPE: Active device-bound VPN peers only; detection is observe-first and writes durable audit events for later admin enforcement.
- DEPENDS: M-001 DB session lifecycle, M-003 vpn client state, M-020 device-registry, M-023 handshake-anomaly-detector, M-025 device-audit-log.
- LINKS: V-M-023, V-M-025.

MODULE_MAP
- HandshakeAnomalyMonitor: Coordinates peer-stat polling and anomaly-event recording.
- scan_active_peers: Pulls runtime peer stats and applies observe-first anomaly rules.
- observe_peer_stats: Updates per-device handshake metadata and records suspicious events when endpoints churn too quickly.

CHANGE_SUMMARY
- 2026-03-27: Added first-pass observe-only detector for endpoint churn and concurrent-handshake suspicion on device-bound peers.
- 2026-03-27: Normalized observed handshake timestamps before persisting device metadata so live Postgres writes do not fail on timezone-aware values.
"""
# <!-- GRACE: module="M-023" contract="handshake-anomaly-detector" -->

from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.devices.models import (
    DeviceEventSeverity,
    DeviceSecurityEvent,
    DeviceSecurityEventType,
    UserDevice,
)
from app.vpn.amneziawg import wg_manager
from app.vpn.models import VPNClient


class HandshakeAnomalyMonitor:
    """Observe handshake metadata and record soft fraud signals for one session."""

    ENDPOINT_CHURN_WINDOW_SECONDS = 600
    CONCURRENCY_SUSPECT_WINDOW_SECONDS = 120

    def __init__(self, session: AsyncSession):
        self.session = session
        self.wg = wg_manager

    async def scan_active_peers(self) -> int:
        """Poll live peer stats and apply observe-first anomaly detection."""
        stats = await self.wg.get_peer_stats()
        return await self.observe_peer_stats(stats)

    async def observe_peer_stats(self, peer_stats: dict[str, dict]) -> int:
        """Update device metadata from one peer-stats snapshot and write anomaly signals."""
        if not peer_stats:
            return 0

        result = await self.session.execute(
            select(VPNClient)
            .where(
                VPNClient.is_active == True,
                VPNClient.device_id != None,
            )
            .order_by(VPNClient.id.asc())
        )
        clients = list(result.scalars().all())
        processed = 0

        for client in clients:
            stat = peer_stats.get(client.public_key)
            if stat is None or client.device_id is None:
                continue

            device = await self.session.get(UserDevice, int(client.device_id))
            if device is None:
                continue

            processed += 1
            await self._apply_observation(device, client, stat)

        if processed:
            await self.session.flush()
        return processed

    async def _apply_observation(
        self,
        device: UserDevice,
        client: VPNClient,
        stat: dict,
    ) -> None:
        """Update one device from a peer-stat snapshot and record suspicious changes."""
        observed_at = self._coerce_datetime(stat.get("last_handshake")) or datetime.now(timezone.utc)
        stored_observed_at = self._to_naive_utc(observed_at)
        endpoint = stat.get("endpoint")
        previous_endpoint = device.last_endpoint
        previous_handshake = self._coerce_datetime(device.last_handshake_at)

        logger.info(
            "[VPN][handshake][VPN_HANDSHAKE_OBSERVED] "
            f"user_id={client.user_id} device_id={device.id} client_id={client.id} "
            f"endpoint={endpoint or 'unknown'} handshake_at={observed_at.isoformat()}"
        )

        if endpoint and previous_endpoint and previous_endpoint != endpoint:
            logger.warning(
                "[VPN][handshake][VPN_HANDSHAKE_ENDPOINT_CHANGED] "
                f"user_id={client.user_id} device_id={device.id} client_id={client.id} "
                f"previous_endpoint={previous_endpoint} new_endpoint={endpoint}"
            )

            delta_seconds = None
            if previous_handshake is not None:
                delta_seconds = abs((observed_at - previous_handshake).total_seconds())

            if delta_seconds is not None and delta_seconds <= self.ENDPOINT_CHURN_WINDOW_SECONDS:
                await self._record_event(
                    user_id=int(client.user_id),
                    device_id=int(device.id),
                    event_type=DeviceSecurityEventType.SUSPICIOUS_ENDPOINT_CHURN,
                    severity=DeviceEventSeverity.WARNING,
                    details_json=(
                        f'{{"previous_endpoint":"{previous_endpoint}","new_endpoint":"{endpoint}",'
                        f'"delta_seconds":{int(delta_seconds)}}}'
                    ),
                )
                logger.warning(
                    "[VPN][handshake][VPN_DEVICE_SUSPICION_ESCALATED] "
                    f"user_id={client.user_id} device_id={device.id} signal=suspicious_endpoint_churn "
                    f"delta_seconds={int(delta_seconds)}"
                )

            if delta_seconds is not None and delta_seconds <= self.CONCURRENCY_SUSPECT_WINDOW_SECONDS:
                await self._record_event(
                    user_id=int(client.user_id),
                    device_id=int(device.id),
                    event_type=DeviceSecurityEventType.CONCURRENT_HANDSHAKE_SUSPECTED,
                    severity=DeviceEventSeverity.WARNING,
                    details_json=(
                        f'{{"previous_endpoint":"{previous_endpoint}","new_endpoint":"{endpoint}",'
                        f'"delta_seconds":{int(delta_seconds)}}}'
                    ),
                )
                logger.warning(
                    "[VPN][handshake][VPN_HANDSHAKE_CONCURRENCY_SUSPECTED] "
                    f"user_id={client.user_id} device_id={device.id} delta_seconds={int(delta_seconds)} "
                    f"previous_endpoint={previous_endpoint} new_endpoint={endpoint}"
                )

        device.last_seen_at = stored_observed_at
        device.last_handshake_at = stored_observed_at
        if endpoint:
            device.last_endpoint = endpoint
        device.updated_at = datetime.utcnow()

    async def _record_event(
        self,
        *,
        user_id: int,
        device_id: int,
        event_type: DeviceSecurityEventType,
        severity: DeviceEventSeverity,
        details_json: str,
    ) -> DeviceSecurityEvent:
        """Write one durable anomaly event."""
        event = DeviceSecurityEvent(
            user_id=user_id,
            device_id=device_id,
            event_type=event_type,
            severity=severity,
            details_json=details_json,
        )
        self.session.add(event)
        await self.session.flush()
        logger.info(
            "[VPN][device][VPN_DEVICE_AUDIT_RECORDED] "
            f"user_id={user_id} device_id={device_id} event_type={event_type.value} severity={severity.value}"
        )
        return event

    @staticmethod
    def _coerce_datetime(value: datetime | None) -> datetime | None:
        """Normalize naive datetimes to UTC-aware values for delta calculations."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _to_naive_utc(value: datetime) -> datetime:
        """Convert one observation timestamp into naive UTC for persisted columns."""
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)
