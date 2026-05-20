"""MTProto admin-only IP observability.

# FILE: backend/app/mtproto/ip_observability.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Store and expose encrypted MTProto client IP observations for explicit admin investigations
#   SCOPE: IP normalization, HMAC hash/prefix derivation, Fernet encryption, observation upsert,
#          current/last IP summaries, admin-only decryption, and 90-day retention
#   DEPENDS: M-001 (security/config), M-042 (assignments), M-054 (usage telemetry)
#   LINKS: M-061, V-M-061
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   record_ip_observation - Upsert encrypted raw IP evidence from trusted runtime telemetry
#   list_user_ip_observations - Admin-only decrypted 90-day IP history list
#   current_ip_summary - Admin-only current/last IP derivation without guessing missing source IPs
#   decrypt_ip_observation - Explicit admin-only raw IP decrypt helper
#   apply_ip_retention - Prune exact encrypted IP observations after retention window
#   ip_observation_count - Count retained exact IP rows for storage-budget reporting
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-43 encrypted MTProto IP observability service
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import ipaddress

from loguru import logger
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decrypt_data, encrypt_data
from app.mtproto.usage_models import MTProtoIPObservation


IP_OBSERVATION_RETENTION_DAYS = 90


# START_BLOCK_IP_HELPERS
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_aware(value: datetime | None) -> datetime:
    if value is None:
        return _utcnow()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _normalize_ip(client_ip: str | None) -> str | None:
    if not client_ip:
        return None
    try:
        return str(ipaddress.ip_address(client_ip.strip()))
    except ValueError:
        return None


def _hash_client_ip(client_ip: str) -> str:
    key = settings.secret_key.encode("utf-8")
    digest = hmac.new(key, client_ip.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:40]


def _coarse_ip_prefix(client_ip: str) -> str:
    address = ipaddress.ip_address(client_ip)
    if address.version == 4:
        return str(ipaddress.ip_network(f"{address}/24", strict=False))
    return str(ipaddress.ip_network(f"{address}/48", strict=False))


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _event_type_value(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _observation_age_cutoff(now: datetime | None = None, *, retention_days: int = IP_OBSERVATION_RETENTION_DAYS) -> datetime:
    return _coerce_aware(now) - timedelta(days=max(retention_days, 1))
# END_BLOCK_IP_HELPERS


# START_CONTRACT: record_ip_observation
#   PURPOSE: Upsert encrypted exact client IP evidence for one trusted assignment telemetry event
#   INPUTS: session; assignment_id; user_id; client_ip; observed_at; event_type; connection_count
#   OUTPUTS: MTProtoIPObservation | None
#   SIDE_EFFECTS: Inserts/updates encrypted IP row and emits redacted log marker
#   LINKS: M-061, M-054, V-M-061
# END_CONTRACT: record_ip_observation
# START_BLOCK_RECORD_OBSERVATION
async def record_ip_observation(
    session: AsyncSession,
    *,
    assignment_id: int,
    user_id: int,
    client_ip: str | None,
    observed_at: datetime | None = None,
    event_type: str = "handshake",
    connection_count: int = 0,
) -> MTProtoIPObservation | None:
    """Persist one exact client IP observation encrypted at rest."""
    normalized_ip = _normalize_ip(client_ip)
    if normalized_ip is None:
        return None

    ip_hash = _hash_client_ip(normalized_ip)
    ip_prefix = _coarse_ip_prefix(normalized_ip)
    observed = _coerce_aware(observed_at)
    event_name = _event_type_value(event_type)
    active_count = max(int(connection_count or 0), 0)

    result = await session.execute(
        select(MTProtoIPObservation).where(
            MTProtoIPObservation.assignment_id == assignment_id,
            MTProtoIPObservation.ip_hash == ip_hash,
        )
    )
    row = result.scalar_one_or_none()
    now = _utcnow()
    if row is None:
        row = MTProtoIPObservation(
            assignment_id=assignment_id,
            user_id=user_id,
            ip_hash=ip_hash,
            ip_prefix=ip_prefix,
            encrypted_ip=encrypt_data(normalized_ip),
            first_seen_at=observed,
            last_seen_at=observed,
        )
        session.add(row)

    row.user_id = user_id
    row.ip_prefix = ip_prefix
    previous_last_seen = _coerce_aware(row.last_seen_at) if row.last_seen_at else observed
    row.last_seen_at = max(previous_last_seen, observed)
    row.last_event_type = event_name[:50]
    row.updated_at = now

    if event_name == "handshake":
        row.current_active = True
        row.active_connections = max(active_count, 1)
        row.connection_count += max(active_count, 1)
        row.last_active_at = observed
    elif event_name == "active_connection":
        row.active_connections = active_count
        row.current_active = active_count > 0
        if active_count > 0:
            row.last_active_at = observed
    elif event_name == "close":
        close_count = max(active_count, 1)
        row.active_connections = max(row.active_connections - close_count, 0)
        row.current_active = row.active_connections > 0
    elif event_name == "error" and row.current_active:
        row.last_active_at = observed

    await session.flush()
    logger.info(
        "[M-061][record_ip_observation][OBSERVATION_UPSERT] "
        f"assignment_id={assignment_id} user_id={user_id} ip_hash_prefix={ip_hash[:12]} event_type={event_name}"
    )
    return row
# END_BLOCK_RECORD_OBSERVATION


# START_CONTRACT: decrypt_ip_observation
#   PURPOSE: Decrypt exact IP only inside explicit admin investigation code paths
#   INPUTS: observation; admin_id
#   OUTPUTS: str
#   SIDE_EFFECTS: emits admin-only redacted log marker without plaintext IP
#   LINKS: M-061, V-M-061
# END_CONTRACT: decrypt_ip_observation
# START_BLOCK_DECRYPT_ADMIN_ONLY
def decrypt_ip_observation(
    observation: MTProtoIPObservation,
    *,
    admin_id: int | None = None,
) -> str:
    """Decrypt one observation for an explicit admin investigation response."""
    logger.info(
        "[M-061][decrypt_ip_observation][ADMIN_ONLY] "
        f"observation_id={observation.id} admin_id={admin_id or 'unknown'}"
    )
    return decrypt_data(observation.encrypted_ip)
# END_BLOCK_DECRYPT_ADMIN_ONLY


# START_BLOCK_SERIALIZE_OBSERVATION
def _serialize_observation(
    observation: MTProtoIPObservation,
    *,
    admin_id: int | None = None,
    include_decrypted: bool = True,
) -> dict[str, object]:
    return {
        "id": observation.id,
        "assignment_id": observation.assignment_id,
        "user_id": observation.user_id,
        "ip_address": decrypt_ip_observation(observation, admin_id=admin_id) if include_decrypted else None,
        "ip_hash_prefix": observation.ip_hash[:12],
        "ip_prefix": observation.ip_prefix,
        "source_status": observation.source_status,
        "first_seen_at": _iso(observation.first_seen_at),
        "last_seen_at": _iso(observation.last_seen_at),
        "last_active_at": _iso(observation.last_active_at),
        "current_active": observation.current_active,
        "active_connections": observation.active_connections,
        "connection_count": observation.connection_count,
        "last_event_type": observation.last_event_type,
    }
# END_BLOCK_SERIALIZE_OBSERVATION


# START_CONTRACT: list_user_ip_observations
#   PURPOSE: Return decrypted 90-day IP history for an explicit admin investigation scope
#   INPUTS: session; user_id or assignment_id; offset; limit; admin_id
#   OUTPUTS: paginated dict with decrypted IP rows
#   SIDE_EFFECTS: database reads and admin-only decryption markers
#   LINKS: M-061, V-M-057, V-M-058
# END_CONTRACT: list_user_ip_observations
# START_BLOCK_LIST_OBSERVATIONS
async def list_user_ip_observations(
    session: AsyncSession,
    *,
    user_id: int | None = None,
    assignment_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    admin_id: int | None = None,
    include_decrypted: bool = True,
    now: datetime | None = None,
) -> dict[str, object]:
    """Return one user's retained exact IP history for admin investigation."""
    cutoff = _observation_age_cutoff(now)
    conditions = [MTProtoIPObservation.last_seen_at >= cutoff]
    if user_id is not None:
        conditions.append(MTProtoIPObservation.user_id == user_id)
    if assignment_id is not None:
        conditions.append(MTProtoIPObservation.assignment_id == assignment_id)

    safe_offset = max(offset, 0)
    safe_limit = min(max(limit, 1), 500)
    total = int((await session.execute(select(func.count(MTProtoIPObservation.id)).where(*conditions))).scalar() or 0)
    result = await session.execute(
        select(MTProtoIPObservation)
        .where(*conditions)
        .order_by(MTProtoIPObservation.last_seen_at.desc(), MTProtoIPObservation.id.desc())
        .offset(safe_offset)
        .limit(safe_limit)
    )
    items = [
        _serialize_observation(row, admin_id=admin_id, include_decrypted=include_decrypted)
        for row in result.scalars().all()
    ]
    logger.info(
        "[M-061][list_user_ip_observations][ADMIN_SCOPE] "
        f"user_id={user_id or 'any'} assignment_id={assignment_id or 'any'} returned={len(items)}"
    )
    return {"items": items, "total": total, "offset": safe_offset, "limit": safe_limit}
# END_BLOCK_LIST_OBSERVATIONS


# START_CONTRACT: current_ip_summary
#   PURPOSE: Derive current and last IP evidence without guessing when no trusted source exists
#   INPUTS: session; assignment_id or user_id; admin_id
#   OUTPUTS: dict with source_status, current_ips, and last_ip
#   SIDE_EFFECTS: database reads and optional admin-only decryption markers
#   LINKS: M-061, V-M-061
# END_CONTRACT: current_ip_summary
# START_BLOCK_CURRENT_SUMMARY
async def current_ip_summary(
    session: AsyncSession,
    *,
    assignment_id: int | None = None,
    user_id: int | None = None,
    admin_id: int | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Return current and last retained IP evidence without inferring missing telemetry."""
    cutoff = _observation_age_cutoff(now)
    conditions = [MTProtoIPObservation.last_seen_at >= cutoff]
    if assignment_id is not None:
        conditions.append(MTProtoIPObservation.assignment_id == assignment_id)
    if user_id is not None:
        conditions.append(MTProtoIPObservation.user_id == user_id)

    result = await session.execute(
        select(MTProtoIPObservation)
        .where(*conditions)
        .order_by(MTProtoIPObservation.last_seen_at.desc(), MTProtoIPObservation.id.desc())
        .limit(100)
    )
    observations = list(result.scalars().all())
    if not observations:
        logger.info(
            "[M-061][current_ip_summary][SOURCE_UNAVAILABLE] "
            f"assignment_id={assignment_id or 'unknown'} user_id={user_id or 'unknown'}"
        )
        return {
            "source_status": "source_ip_unavailable",
            "current_ips": [],
            "last_ip": None,
        }

    current = [row for row in observations if row.current_active]
    return {
        "source_status": "trusted_runtime",
        "current_ips": [
            _serialize_observation(row, admin_id=admin_id, include_decrypted=True)
            for row in current
        ],
        "last_ip": _serialize_observation(observations[0], admin_id=admin_id, include_decrypted=True),
    }
# END_BLOCK_CURRENT_SUMMARY


# START_CONTRACT: apply_ip_retention
#   PURPOSE: Delete exact IP evidence older than retention window
#   INPUTS: session; retention_days; now
#   OUTPUTS: deleted row count
#   SIDE_EFFECTS: Deletes expired encrypted rows and logs count only
#   LINKS: M-061, V-M-061
# END_CONTRACT: apply_ip_retention
# START_BLOCK_IP_RETENTION
async def apply_ip_retention(
    session: AsyncSession,
    *,
    retention_days: int = IP_OBSERVATION_RETENTION_DAYS,
    now: datetime | None = None,
) -> int:
    """Prune exact encrypted IP observations after the configured retention window."""
    cutoff = _observation_age_cutoff(now, retention_days=retention_days)
    result = await session.execute(
        delete(MTProtoIPObservation)
        .where(MTProtoIPObservation.last_seen_at < cutoff)
        .execution_options(synchronize_session=False)
    )
    deleted_count = int(result.rowcount or 0)
    logger.info(
        "[M-061][apply_ip_retention][RETENTION_PRUNE] "
        f"deleted={deleted_count} retention_days={retention_days}"
    )
    return deleted_count
# END_BLOCK_IP_RETENTION


async def ip_observation_count(session: AsyncSession) -> int:
    """Return retained exact IP observation count for storage-budget reporting."""
    return int((await session.execute(select(func.count(MTProtoIPObservation.id)))).scalar() or 0)
