"""MTProto usage telemetry persistence models.

# FILE: backend/app/mtproto/usage_models.py
# VERSION: 1.2.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Persist metadata-only MTProto proxy telemetry for admin analytics
#   SCOPE: Usage events, sessions, usage state, rollups, observe-only abuse signals,
#          encrypted IP observations, admin alerts, and reviewed IP block records
#   DEPENDS: M-001 (core database), M-002 (users), M-042 (MTProto assignments)
#   LINKS: M-054, M-060, M-061, V-M-054, V-M-060, V-M-061
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MTProtoUsageEventType - Supported secret-free telemetry and IP-observation event types
#   MTProtoUsageWindow - Aggregate rollup window names
#   MTProtoAbuseSignalType - Observe-only abuse signal categories
#   MTProtoAdminAlertStatus - Operator review lifecycle for durable MTProto alerts
#   MTProtoIPBlockStatus - TTL-bound admin IP block record lifecycle
#   MTProtoUsageEvent - Append-only runtime telemetry event row
#   MTProtoUsageSession - Per-assignment connection/session aggregate row
#   MTProtoUsageState - Current last-seen and active-connection state per assignment
#   MTProtoUsageRollup - Windowed aggregate counters by assignment or global scope
#   MTProtoAbuseSignal - Observe-only analytics signal row
#   MTProtoIPObservation - Encrypted admin-only client IP observation row
#   MTProtoAdminAlert - Durable high/critical abuse alert inbox row
#   MTProtoBlockedIP - TTL-bound reviewed IP block record row
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.2.0 - Added IP_OBSERVATION event type for runtime client-IP samples that must not inflate usage counters.
#   LAST_CHANGE: v1.1.0 - Added Phase-43 encrypted IP observability and admin alert models
#   LAST_CHANGE: v1.0.0 - Added Phase-42 MTProto usage telemetry persistence models
# END_CHANGE_SUMMARY
"""

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Index, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


# START_BLOCK_USAGE_TYPES
class MTProtoUsageEventType(str, Enum):
    """Secret-free runtime telemetry event types."""

    HANDSHAKE = "handshake"
    CLOSE = "close"
    BYTES = "bytes"
    ERROR = "error"
    UNKNOWN_SNI = "unknown_sni"
    REJECTED_SNI = "rejected_sni"
    ACTIVE_CONNECTION = "active_connection"
    REQ_PQ_PROOF = "req_pq_proof"
    IP_OBSERVATION = "ip_observation"


class MTProtoUsageWindow(str, Enum):
    """Rollup window names used by admin analytics."""

    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class MTProtoAbuseSignalType(str, Enum):
    """Observe-only abuse signal categories."""

    MANY_IP_HASHES = "many_ip_hashes"
    HIGH_CONCURRENCY = "high_concurrency"
    TRAFFIC_SPIKE = "traffic_spike"
    REPEATED_ERRORS = "repeated_errors"


class MTProtoAdminAlertStatus(str, Enum):
    """Durable admin review lifecycle states for abuse alerts."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class MTProtoIPBlockStatus(str, Enum):
    """TTL-bound IP block record lifecycle states."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
# END_BLOCK_USAGE_TYPES


# START_BLOCK_USAGE_EVENT
class MTProtoUsageEvent(SQLModel, table=True):
    """Append-only secret-free runtime telemetry event."""

    __tablename__ = "mtproto_usage_events"

    id: int | None = Field(default=None, primary_key=True)
    runtime_event_id: str = Field(unique=True, index=True, max_length=128)
    assignment_id: int | None = Field(default=None, foreign_key="mtproto_assignments.id", index=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    event_type: MTProtoUsageEventType = Field(index=True, max_length=50)
    observed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), index=True),
    )
    sni_masked: str | None = Field(default=None, max_length=255)
    ip_hash: str | None = Field(default=None, index=True, max_length=128)
    ip_prefix: str | None = Field(default=None, max_length=80)
    bytes_in: int = Field(default=0, ge=0)
    bytes_out: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    connection_count: int = Field(default=0, ge=0)
    error_code: str | None = Field(default=None, max_length=80)
    reason_code: str | None = Field(default=None, max_length=80)
    metadata_json: str | None = Field(default=None, sa_column=Column(Text))

    __table_args__ = (
        Index("ix_mtproto_usage_events_assignment_time", "assignment_id", "observed_at"),
        Index("ix_mtproto_usage_events_user_time", "user_id", "observed_at"),
        Index("ix_mtproto_usage_events_type_time", "event_type", "observed_at"),
    )
# END_BLOCK_USAGE_EVENT


# START_BLOCK_USAGE_SESSION
class MTProtoUsageSession(SQLModel, table=True):
    """Per-assignment session state and aggregate counters."""

    __tablename__ = "mtproto_usage_sessions"

    id: int | None = Field(default=None, primary_key=True)
    assignment_id: int = Field(foreign_key="mtproto_assignments.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), index=True),
    )
    ended_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), index=True))
    duration_ms: int = Field(default=0, ge=0)
    bytes_in: int = Field(default=0, ge=0)
    bytes_out: int = Field(default=0, ge=0)
    connection_count: int = Field(default=1, ge=0)
    error_count: int = Field(default=0, ge=0)
    active: bool = Field(default=True, index=True)
    client_ip_hash: str | None = Field(default=None, index=True, max_length=128)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )

    __table_args__ = (
        Index("ix_mtproto_usage_sessions_assignment_active", "assignment_id", "active"),
        Index("ix_mtproto_usage_sessions_user_started", "user_id", "started_at"),
    )
# END_BLOCK_USAGE_SESSION


# START_BLOCK_USAGE_STATE
class MTProtoUsageState(SQLModel, table=True):
    """Current usage state per known assignment."""

    __tablename__ = "mtproto_usage_states"

    id: int | None = Field(default=None, primary_key=True)
    assignment_id: int = Field(foreign_key="mtproto_assignments.id", unique=True, index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    last_seen_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), index=True))
    last_req_pq_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), index=True))
    active_connections: int = Field(default=0, ge=0)
    total_connections: int = Field(default=0, ge=0)
    total_errors: int = Field(default=0, ge=0)
    total_bytes_in: int = Field(default=0, ge=0)
    total_bytes_out: int = Field(default=0, ge=0)
    telemetry_status: str = Field(default="fresh", max_length=50)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
# END_BLOCK_USAGE_STATE


# START_BLOCK_USAGE_ROLLUP
class MTProtoUsageRollup(SQLModel, table=True):
    """Windowed aggregate counters for usage reporting."""

    __tablename__ = "mtproto_usage_rollups"

    id: int | None = Field(default=None, primary_key=True)
    window_type: MTProtoUsageWindow = Field(index=True, max_length=20)
    window_start: datetime = Field(sa_column=Column(DateTime(timezone=True), index=True))
    assignment_id: int | None = Field(default=None, foreign_key="mtproto_assignments.id", index=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    bytes_in: int = Field(default=0, ge=0)
    bytes_out: int = Field(default=0, ge=0)
    connection_count: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    event_count: int = Field(default=0, ge=0)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )

    __table_args__ = (
        UniqueConstraint(
            "window_type",
            "window_start",
            "assignment_id",
            name="uq_mtproto_usage_rollup_assignment_window",
        ),
        Index("ix_mtproto_usage_rollups_window_user", "window_type", "window_start", "user_id"),
    )
# END_BLOCK_USAGE_ROLLUP


# START_BLOCK_ABUSE_SIGNAL
class MTProtoAbuseSignal(SQLModel, table=True):
    """Observe-only MTProto abuse signal."""

    __tablename__ = "mtproto_abuse_signals"

    id: int | None = Field(default=None, primary_key=True)
    assignment_id: int | None = Field(default=None, foreign_key="mtproto_assignments.id", index=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    signal_type: MTProtoAbuseSignalType = Field(index=True, max_length=50)
    severity: str = Field(default="low", max_length=20)
    observe_only: bool = Field(default=True, index=True)
    window_start: datetime = Field(sa_column=Column(DateTime(timezone=True), index=True))
    window_end: datetime = Field(sa_column=Column(DateTime(timezone=True), index=True))
    metric_value: int = Field(default=0, ge=0)
    threshold_value: int = Field(default=0, ge=0)
    reason_code: str = Field(default="threshold_exceeded", max_length=80)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), index=True),
    )

    __table_args__ = (
        Index("ix_mtproto_abuse_assignment_window", "assignment_id", "window_start", "signal_type"),
    )
# END_BLOCK_ABUSE_SIGNAL


# START_BLOCK_IP_OBSERVATION
class MTProtoIPObservation(SQLModel, table=True):
    """Encrypted admin-only client IP history for one assignment."""

    __tablename__ = "mtproto_ip_observations"

    id: int | None = Field(default=None, primary_key=True)
    assignment_id: int = Field(foreign_key="mtproto_assignments.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    ip_hash: str = Field(index=True, max_length=128)
    ip_prefix: str | None = Field(default=None, max_length=80)
    encrypted_ip: str = Field(sa_column=Column(Text))
    source_status: str = Field(default="trusted_runtime", max_length=50)
    first_seen_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), index=True),
    )
    last_seen_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), index=True),
    )
    last_active_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), index=True))
    current_active: bool = Field(default=False, index=True)
    active_connections: int = Field(default=0, ge=0)
    connection_count: int = Field(default=0, ge=0)
    last_event_type: str | None = Field(default=None, max_length=50)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )

    __table_args__ = (
        UniqueConstraint(
            "assignment_id",
            "ip_hash",
            name="uq_mtproto_ip_observation_assignment_hash",
        ),
        Index("ix_mtproto_ip_observations_assignment_active", "assignment_id", "current_active"),
        Index("ix_mtproto_ip_observations_user_last_seen", "user_id", "last_seen_at"),
        Index("ix_mtproto_ip_observations_hash_last_seen", "ip_hash", "last_seen_at"),
    )
# END_BLOCK_IP_OBSERVATION


# START_BLOCK_ADMIN_ALERT
class MTProtoAdminAlert(SQLModel, table=True):
    """Durable admin alert for high/critical MTProto abuse signals."""

    __tablename__ = "mtproto_admin_alerts"

    id: int | None = Field(default=None, primary_key=True)
    dedupe_key: str = Field(unique=True, index=True, max_length=180)
    abuse_signal_id: int | None = Field(default=None, foreign_key="mtproto_abuse_signals.id", index=True)
    assignment_id: int | None = Field(default=None, foreign_key="mtproto_assignments.id", index=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    signal_type: str = Field(index=True, max_length=50)
    severity: str = Field(default="high", index=True, max_length=20)
    status: MTProtoAdminAlertStatus = Field(default=MTProtoAdminAlertStatus.OPEN, index=True, max_length=30)
    title: str = Field(max_length=160)
    reason_code: str = Field(default="threshold_exceeded", max_length=80)
    metric_value: int = Field(default=0, ge=0)
    threshold_value: int = Field(default=0, ge=0)
    window_start: datetime = Field(sa_column=Column(DateTime(timezone=True), index=True))
    window_end: datetime = Field(sa_column=Column(DateTime(timezone=True), index=True))
    first_seen_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), index=True),
    )
    last_seen_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), index=True),
    )
    occurrence_count: int = Field(default=1, ge=1)
    acknowledged_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    acknowledged_by_admin_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    resolved_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    resolved_by_admin_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    action_taken: str | None = Field(default=None, max_length=80)
    action_result: str | None = Field(default=None, max_length=120)
    metadata_json: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), index=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )

    __table_args__ = (
        Index("ix_mtproto_admin_alerts_status_severity", "status", "severity"),
        Index("ix_mtproto_admin_alerts_assignment_status", "assignment_id", "status"),
        Index("ix_mtproto_admin_alerts_user_status", "user_id", "status"),
    )
# END_BLOCK_ADMIN_ALERT


# START_BLOCK_BLOCKED_IP
class MTProtoBlockedIP(SQLModel, table=True):
    """Reviewed TTL-bound IP block record based on trusted IP observation evidence."""

    __tablename__ = "mtproto_blocked_ips"

    id: int | None = Field(default=None, primary_key=True)
    assignment_id: int | None = Field(default=None, foreign_key="mtproto_assignments.id", index=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    ip_observation_id: int = Field(foreign_key="mtproto_ip_observations.id", index=True)
    ip_hash: str = Field(index=True, max_length=128)
    ip_prefix: str | None = Field(default=None, max_length=80)
    encrypted_ip: str = Field(sa_column=Column(Text))
    status: MTProtoIPBlockStatus = Field(default=MTProtoIPBlockStatus.ACTIVE, index=True, max_length=30)
    reason_code: str = Field(default="admin_reviewed_abuse", max_length=80)
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), index=True))
    created_by_admin_id: int = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), index=True),
    )
    revoked_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    metadata_json: str | None = Field(default=None, sa_column=Column(Text))

    __table_args__ = (
        Index("ix_mtproto_blocked_ips_hash_status", "ip_hash", "status"),
        Index("ix_mtproto_blocked_ips_assignment_status", "assignment_id", "status"),
        Index("ix_mtproto_blocked_ips_expires_status", "expires_at", "status"),
    )
# END_BLOCK_BLOCKED_IP
