"""MTProto usage telemetry persistence models.

# FILE: backend/app/mtproto/usage_models.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Persist metadata-only MTProto proxy telemetry for admin analytics
#   SCOPE: Usage events, sessions, usage state, rollups, and observe-only abuse signals
#   DEPENDS: M-001 (core database), M-002 (users), M-042 (MTProto assignments)
#   LINKS: M-054, V-M-054
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MTProtoUsageEventType - Supported secret-free telemetry event types
#   MTProtoUsageWindow - Aggregate rollup window names
#   MTProtoAbuseSignalType - Observe-only abuse signal categories
#   MTProtoUsageEvent - Append-only runtime telemetry event row
#   MTProtoUsageSession - Per-assignment connection/session aggregate row
#   MTProtoUsageState - Current last-seen and active-connection state per assignment
#   MTProtoUsageRollup - Windowed aggregate counters by assignment or global scope
#   MTProtoAbuseSignal - Observe-only analytics signal row
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
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
