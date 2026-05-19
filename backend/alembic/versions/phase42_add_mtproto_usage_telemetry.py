"""add_mtproto_usage_telemetry

Revision ID: phase42_mtproto_usage
Revises: b3f1e0d2c9a4
Create Date: 2026-05-19 00:00:00.000000

# FILE: backend/alembic/versions/phase42_add_mtproto_usage_telemetry.py
# VERSION: 1.0.0
# ROLE: SCRIPT
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Add MTProto usage telemetry, analytics rollups, abuse signals, and promotion tag state schema
#   SCOPE: Phase-42 tables and indexes for metadata-only analytics without secret storage in admin payloads
#   DEPENDS: M-028 (migration governance), M-054 (usage telemetry), M-059 (promotion tag)
#   LINKS: M-028, M-054, M-059, V-M-054, V-M-059
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   upgrade - Creates MTProto telemetry, rollup, abuse, and promotion tag tables
#   downgrade - Drops Phase-42 MTProto analytics tables
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-42 MTProto usage analytics migration
# END_CHANGE_SUMMARY
"""
import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "phase42_mtproto_usage"
down_revision: Union[str, Sequence[str], None] = "b3f1e0d2c9a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
logger = logging.getLogger("alembic.runtime.migration")


# START_BLOCK_MTPROTO_USAGE_SCHEMA
def upgrade() -> None:
    """Upgrade schema with MTProto metadata-only usage analytics tables."""
    logger.info("[M-054][migration][MTPROTO_USAGE_SCHEMA] creating Phase-42 analytics tables")
    op.create_table(
        "mtproto_usage_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("runtime_event_id", sa.String(length=128), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sni_masked", sa.String(length=255), nullable=True),
        sa.Column("ip_hash", sa.String(length=128), nullable=True),
        sa.Column("ip_prefix", sa.String(length=80), nullable=True),
        sa.Column("bytes_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bytes_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("connection_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("reason_code", sa.String(length=80), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["assignment_id"], ["mtproto_assignments.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("runtime_event_id"),
    )
    op.create_index(op.f("ix_mtproto_usage_events_runtime_event_id"), "mtproto_usage_events", ["runtime_event_id"], unique=True)
    op.create_index(op.f("ix_mtproto_usage_events_assignment_id"), "mtproto_usage_events", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_mtproto_usage_events_user_id"), "mtproto_usage_events", ["user_id"], unique=False)
    op.create_index(op.f("ix_mtproto_usage_events_event_type"), "mtproto_usage_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_mtproto_usage_events_observed_at"), "mtproto_usage_events", ["observed_at"], unique=False)
    op.create_index("ix_mtproto_usage_events_assignment_time", "mtproto_usage_events", ["assignment_id", "observed_at"], unique=False)
    op.create_index("ix_mtproto_usage_events_user_time", "mtproto_usage_events", ["user_id", "observed_at"], unique=False)
    op.create_index("ix_mtproto_usage_events_type_time", "mtproto_usage_events", ["event_type", "observed_at"], unique=False)

    op.create_table(
        "mtproto_usage_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bytes_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bytes_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("connection_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("client_ip_hash", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assignment_id"], ["mtproto_assignments.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mtproto_usage_sessions_assignment_id"), "mtproto_usage_sessions", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_mtproto_usage_sessions_user_id"), "mtproto_usage_sessions", ["user_id"], unique=False)
    op.create_index(op.f("ix_mtproto_usage_sessions_started_at"), "mtproto_usage_sessions", ["started_at"], unique=False)
    op.create_index(op.f("ix_mtproto_usage_sessions_ended_at"), "mtproto_usage_sessions", ["ended_at"], unique=False)
    op.create_index(op.f("ix_mtproto_usage_sessions_active"), "mtproto_usage_sessions", ["active"], unique=False)
    op.create_index(op.f("ix_mtproto_usage_sessions_client_ip_hash"), "mtproto_usage_sessions", ["client_ip_hash"], unique=False)
    op.create_index("ix_mtproto_usage_sessions_assignment_active", "mtproto_usage_sessions", ["assignment_id", "active"], unique=False)
    op.create_index("ix_mtproto_usage_sessions_user_started", "mtproto_usage_sessions", ["user_id", "started_at"], unique=False)

    op.create_table(
        "mtproto_usage_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_req_pq_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_connections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_connections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_bytes_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_bytes_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("telemetry_status", sa.String(length=50), nullable=False, server_default="fresh"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assignment_id"], ["mtproto_assignments.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id"),
    )
    op.create_index(op.f("ix_mtproto_usage_states_assignment_id"), "mtproto_usage_states", ["assignment_id"], unique=True)
    op.create_index(op.f("ix_mtproto_usage_states_user_id"), "mtproto_usage_states", ["user_id"], unique=False)
    op.create_index(op.f("ix_mtproto_usage_states_last_seen_at"), "mtproto_usage_states", ["last_seen_at"], unique=False)
    op.create_index(op.f("ix_mtproto_usage_states_last_req_pq_at"), "mtproto_usage_states", ["last_req_pq_at"], unique=False)

    op.create_table(
        "mtproto_usage_rollups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("window_type", sa.String(length=20), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assignment_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("bytes_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bytes_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("connection_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assignment_id"], ["mtproto_assignments.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("window_type", "window_start", "assignment_id", name="uq_mtproto_usage_rollup_assignment_window"),
    )
    op.create_index(op.f("ix_mtproto_usage_rollups_window_type"), "mtproto_usage_rollups", ["window_type"], unique=False)
    op.create_index(op.f("ix_mtproto_usage_rollups_window_start"), "mtproto_usage_rollups", ["window_start"], unique=False)
    op.create_index(op.f("ix_mtproto_usage_rollups_assignment_id"), "mtproto_usage_rollups", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_mtproto_usage_rollups_user_id"), "mtproto_usage_rollups", ["user_id"], unique=False)
    op.create_index("ix_mtproto_usage_rollups_window_user", "mtproto_usage_rollups", ["window_type", "window_start", "user_id"], unique=False)

    op.create_table(
        "mtproto_abuse_signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("signal_type", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="low"),
        sa.Column("observe_only", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metric_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("threshold_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reason_code", sa.String(length=80), nullable=False, server_default="threshold_exceeded"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assignment_id"], ["mtproto_assignments.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mtproto_abuse_signals_assignment_id"), "mtproto_abuse_signals", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_mtproto_abuse_signals_user_id"), "mtproto_abuse_signals", ["user_id"], unique=False)
    op.create_index(op.f("ix_mtproto_abuse_signals_signal_type"), "mtproto_abuse_signals", ["signal_type"], unique=False)
    op.create_index(op.f("ix_mtproto_abuse_signals_observe_only"), "mtproto_abuse_signals", ["observe_only"], unique=False)
    op.create_index(op.f("ix_mtproto_abuse_signals_window_start"), "mtproto_abuse_signals", ["window_start"], unique=False)
    op.create_index(op.f("ix_mtproto_abuse_signals_window_end"), "mtproto_abuse_signals", ["window_end"], unique=False)
    op.create_index(op.f("ix_mtproto_abuse_signals_created_at"), "mtproto_abuse_signals", ["created_at"], unique=False)
    op.create_index("ix_mtproto_abuse_assignment_window", "mtproto_abuse_signals", ["assignment_id", "window_start", "signal_type"], unique=False)

    op.create_table(
        "mtproto_promotion_tag_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tag_value", sa.String(length=32), nullable=False),
        sa.Column("tag_masked", sa.String(length=20), nullable=False),
        sa.Column("tag_hash", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("runtime_status", sa.String(length=40), nullable=False),
        sa.Column("pending_restart", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["updated_by_admin_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mtproto_promotion_tag_state_pending_restart"), "mtproto_promotion_tag_state", ["pending_restart"], unique=False)
    op.create_index(op.f("ix_mtproto_promotion_tag_state_updated_by_admin_id"), "mtproto_promotion_tag_state", ["updated_by_admin_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema by removing Phase-42 MTProto analytics tables."""
    op.drop_index(op.f("ix_mtproto_promotion_tag_state_updated_by_admin_id"), table_name="mtproto_promotion_tag_state")
    op.drop_index(op.f("ix_mtproto_promotion_tag_state_pending_restart"), table_name="mtproto_promotion_tag_state")
    op.drop_table("mtproto_promotion_tag_state")

    op.drop_index("ix_mtproto_abuse_assignment_window", table_name="mtproto_abuse_signals")
    op.drop_index(op.f("ix_mtproto_abuse_signals_created_at"), table_name="mtproto_abuse_signals")
    op.drop_index(op.f("ix_mtproto_abuse_signals_window_end"), table_name="mtproto_abuse_signals")
    op.drop_index(op.f("ix_mtproto_abuse_signals_window_start"), table_name="mtproto_abuse_signals")
    op.drop_index(op.f("ix_mtproto_abuse_signals_observe_only"), table_name="mtproto_abuse_signals")
    op.drop_index(op.f("ix_mtproto_abuse_signals_signal_type"), table_name="mtproto_abuse_signals")
    op.drop_index(op.f("ix_mtproto_abuse_signals_user_id"), table_name="mtproto_abuse_signals")
    op.drop_index(op.f("ix_mtproto_abuse_signals_assignment_id"), table_name="mtproto_abuse_signals")
    op.drop_table("mtproto_abuse_signals")

    op.drop_index("ix_mtproto_usage_rollups_window_user", table_name="mtproto_usage_rollups")
    op.drop_index(op.f("ix_mtproto_usage_rollups_user_id"), table_name="mtproto_usage_rollups")
    op.drop_index(op.f("ix_mtproto_usage_rollups_assignment_id"), table_name="mtproto_usage_rollups")
    op.drop_index(op.f("ix_mtproto_usage_rollups_window_start"), table_name="mtproto_usage_rollups")
    op.drop_index(op.f("ix_mtproto_usage_rollups_window_type"), table_name="mtproto_usage_rollups")
    op.drop_table("mtproto_usage_rollups")

    op.drop_index(op.f("ix_mtproto_usage_states_last_req_pq_at"), table_name="mtproto_usage_states")
    op.drop_index(op.f("ix_mtproto_usage_states_last_seen_at"), table_name="mtproto_usage_states")
    op.drop_index(op.f("ix_mtproto_usage_states_user_id"), table_name="mtproto_usage_states")
    op.drop_index(op.f("ix_mtproto_usage_states_assignment_id"), table_name="mtproto_usage_states")
    op.drop_table("mtproto_usage_states")

    op.drop_index("ix_mtproto_usage_sessions_user_started", table_name="mtproto_usage_sessions")
    op.drop_index("ix_mtproto_usage_sessions_assignment_active", table_name="mtproto_usage_sessions")
    op.drop_index(op.f("ix_mtproto_usage_sessions_client_ip_hash"), table_name="mtproto_usage_sessions")
    op.drop_index(op.f("ix_mtproto_usage_sessions_active"), table_name="mtproto_usage_sessions")
    op.drop_index(op.f("ix_mtproto_usage_sessions_ended_at"), table_name="mtproto_usage_sessions")
    op.drop_index(op.f("ix_mtproto_usage_sessions_started_at"), table_name="mtproto_usage_sessions")
    op.drop_index(op.f("ix_mtproto_usage_sessions_user_id"), table_name="mtproto_usage_sessions")
    op.drop_index(op.f("ix_mtproto_usage_sessions_assignment_id"), table_name="mtproto_usage_sessions")
    op.drop_table("mtproto_usage_sessions")

    op.drop_index("ix_mtproto_usage_events_type_time", table_name="mtproto_usage_events")
    op.drop_index("ix_mtproto_usage_events_user_time", table_name="mtproto_usage_events")
    op.drop_index("ix_mtproto_usage_events_assignment_time", table_name="mtproto_usage_events")
    op.drop_index(op.f("ix_mtproto_usage_events_observed_at"), table_name="mtproto_usage_events")
    op.drop_index(op.f("ix_mtproto_usage_events_event_type"), table_name="mtproto_usage_events")
    op.drop_index(op.f("ix_mtproto_usage_events_user_id"), table_name="mtproto_usage_events")
    op.drop_index(op.f("ix_mtproto_usage_events_assignment_id"), table_name="mtproto_usage_events")
    op.drop_index(op.f("ix_mtproto_usage_events_runtime_event_id"), table_name="mtproto_usage_events")
    op.drop_table("mtproto_usage_events")
# END_BLOCK_MTPROTO_USAGE_SCHEMA
