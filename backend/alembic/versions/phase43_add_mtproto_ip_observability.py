"""add_mtproto_ip_observability_admin_alerts

Revision ID: phase43_mtproto_admin_analytics
Revises: phase42_mtproto_usage
Create Date: 2026-05-20 00:00:00.000000

# FILE: backend/alembic/versions/phase43_add_mtproto_ip_observability.py
# VERSION: 1.0.0
# ROLE: SCRIPT
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Add Phase-43 encrypted MTProto IP observability and admin alert schemas
#   SCOPE: Encrypted IP observations, deduplicated abuse alerts, and TTL-bound IP block records
#   DEPENDS: M-028 (migration governance), M-060 (admin alerts), M-061 (IP observability)
#   LINKS: M-028, M-060, M-061, V-M-060, V-M-061
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   upgrade - Creates Phase-43 MTProto observability and alert tables
#   downgrade - Drops Phase-43 MTProto observability and alert tables
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-43 MTProto admin analytics persistence migration
# END_CHANGE_SUMMARY
"""
import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "phase43_mtproto_admin_analytics"
down_revision: Union[str, Sequence[str], None] = "phase42_mtproto_usage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
logger = logging.getLogger("alembic.runtime.migration")


# START_BLOCK_PHASE43_SCHEMA
def upgrade() -> None:
    """Upgrade schema with encrypted IP observations and durable admin alerts."""
    logger.info("[M-061][migration][MTPROTO_IP_OBSERVABILITY_SCHEMA] creating Phase-43 tables")
    op.create_table(
        "mtproto_ip_observations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ip_hash", sa.String(length=128), nullable=False),
        sa.Column("ip_prefix", sa.String(length=80), nullable=True),
        sa.Column("encrypted_ip", sa.Text(), nullable=False),
        sa.Column("source_status", sa.String(length=50), nullable=False, server_default="trusted_runtime"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active_connections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("connection_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_event_type", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assignment_id"], ["mtproto_assignments.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id", "ip_hash", name="uq_mtproto_ip_observation_assignment_hash"),
    )
    op.create_index(op.f("ix_mtproto_ip_observations_assignment_id"), "mtproto_ip_observations", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_mtproto_ip_observations_user_id"), "mtproto_ip_observations", ["user_id"], unique=False)
    op.create_index(op.f("ix_mtproto_ip_observations_ip_hash"), "mtproto_ip_observations", ["ip_hash"], unique=False)
    op.create_index(op.f("ix_mtproto_ip_observations_first_seen_at"), "mtproto_ip_observations", ["first_seen_at"], unique=False)
    op.create_index(op.f("ix_mtproto_ip_observations_last_seen_at"), "mtproto_ip_observations", ["last_seen_at"], unique=False)
    op.create_index(op.f("ix_mtproto_ip_observations_last_active_at"), "mtproto_ip_observations", ["last_active_at"], unique=False)
    op.create_index(op.f("ix_mtproto_ip_observations_current_active"), "mtproto_ip_observations", ["current_active"], unique=False)
    op.create_index("ix_mtproto_ip_observations_assignment_active", "mtproto_ip_observations", ["assignment_id", "current_active"], unique=False)
    op.create_index("ix_mtproto_ip_observations_user_last_seen", "mtproto_ip_observations", ["user_id", "last_seen_at"], unique=False)
    op.create_index("ix_mtproto_ip_observations_hash_last_seen", "mtproto_ip_observations", ["ip_hash", "last_seen_at"], unique=False)

    op.create_table(
        "mtproto_admin_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=180), nullable=False),
        sa.Column("abuse_signal_id", sa.Integer(), nullable=True),
        sa.Column("assignment_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("signal_type", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="high"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=False, server_default="threshold_exceeded"),
        sa.Column("metric_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("threshold_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("action_taken", sa.String(length=80), nullable=True),
        sa.Column("action_result", sa.String(length=120), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["abuse_signal_id"], ["mtproto_abuse_signals.id"]),
        sa.ForeignKeyConstraint(["assignment_id"], ["mtproto_assignments.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["acknowledged_by_admin_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["resolved_by_admin_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_index(op.f("ix_mtproto_admin_alerts_dedupe_key"), "mtproto_admin_alerts", ["dedupe_key"], unique=True)
    op.create_index(op.f("ix_mtproto_admin_alerts_abuse_signal_id"), "mtproto_admin_alerts", ["abuse_signal_id"], unique=False)
    op.create_index(op.f("ix_mtproto_admin_alerts_assignment_id"), "mtproto_admin_alerts", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_mtproto_admin_alerts_user_id"), "mtproto_admin_alerts", ["user_id"], unique=False)
    op.create_index(op.f("ix_mtproto_admin_alerts_signal_type"), "mtproto_admin_alerts", ["signal_type"], unique=False)
    op.create_index(op.f("ix_mtproto_admin_alerts_severity"), "mtproto_admin_alerts", ["severity"], unique=False)
    op.create_index(op.f("ix_mtproto_admin_alerts_status"), "mtproto_admin_alerts", ["status"], unique=False)
    op.create_index(op.f("ix_mtproto_admin_alerts_window_start"), "mtproto_admin_alerts", ["window_start"], unique=False)
    op.create_index(op.f("ix_mtproto_admin_alerts_window_end"), "mtproto_admin_alerts", ["window_end"], unique=False)
    op.create_index(op.f("ix_mtproto_admin_alerts_first_seen_at"), "mtproto_admin_alerts", ["first_seen_at"], unique=False)
    op.create_index(op.f("ix_mtproto_admin_alerts_last_seen_at"), "mtproto_admin_alerts", ["last_seen_at"], unique=False)
    op.create_index(op.f("ix_mtproto_admin_alerts_created_at"), "mtproto_admin_alerts", ["created_at"], unique=False)
    op.create_index(op.f("ix_mtproto_admin_alerts_acknowledged_by_admin_id"), "mtproto_admin_alerts", ["acknowledged_by_admin_id"], unique=False)
    op.create_index(op.f("ix_mtproto_admin_alerts_resolved_by_admin_id"), "mtproto_admin_alerts", ["resolved_by_admin_id"], unique=False)
    op.create_index("ix_mtproto_admin_alerts_status_severity", "mtproto_admin_alerts", ["status", "severity"], unique=False)
    op.create_index("ix_mtproto_admin_alerts_assignment_status", "mtproto_admin_alerts", ["assignment_id", "status"], unique=False)
    op.create_index("ix_mtproto_admin_alerts_user_status", "mtproto_admin_alerts", ["user_id", "status"], unique=False)

    op.create_table(
        "mtproto_blocked_ips",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("ip_observation_id", sa.Integer(), nullable=False),
        sa.Column("ip_hash", sa.String(length=128), nullable=False),
        sa.Column("ip_prefix", sa.String(length=80), nullable=True),
        sa.Column("encrypted_ip", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("reason_code", sa.String(length=80), nullable=False, server_default="admin_reviewed_abuse"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["assignment_id"], ["mtproto_assignments.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["ip_observation_id"], ["mtproto_ip_observations.id"]),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mtproto_blocked_ips_assignment_id"), "mtproto_blocked_ips", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_mtproto_blocked_ips_user_id"), "mtproto_blocked_ips", ["user_id"], unique=False)
    op.create_index(op.f("ix_mtproto_blocked_ips_ip_observation_id"), "mtproto_blocked_ips", ["ip_observation_id"], unique=False)
    op.create_index(op.f("ix_mtproto_blocked_ips_ip_hash"), "mtproto_blocked_ips", ["ip_hash"], unique=False)
    op.create_index(op.f("ix_mtproto_blocked_ips_status"), "mtproto_blocked_ips", ["status"], unique=False)
    op.create_index(op.f("ix_mtproto_blocked_ips_expires_at"), "mtproto_blocked_ips", ["expires_at"], unique=False)
    op.create_index(op.f("ix_mtproto_blocked_ips_created_by_admin_id"), "mtproto_blocked_ips", ["created_by_admin_id"], unique=False)
    op.create_index(op.f("ix_mtproto_blocked_ips_created_at"), "mtproto_blocked_ips", ["created_at"], unique=False)
    op.create_index("ix_mtproto_blocked_ips_hash_status", "mtproto_blocked_ips", ["ip_hash", "status"], unique=False)
    op.create_index("ix_mtproto_blocked_ips_assignment_status", "mtproto_blocked_ips", ["assignment_id", "status"], unique=False)
    op.create_index("ix_mtproto_blocked_ips_expires_status", "mtproto_blocked_ips", ["expires_at", "status"], unique=False)


def downgrade() -> None:
    """Downgrade schema by removing Phase-43 MTProto analytics tables."""
    op.drop_index("ix_mtproto_blocked_ips_expires_status", table_name="mtproto_blocked_ips")
    op.drop_index("ix_mtproto_blocked_ips_assignment_status", table_name="mtproto_blocked_ips")
    op.drop_index("ix_mtproto_blocked_ips_hash_status", table_name="mtproto_blocked_ips")
    op.drop_index(op.f("ix_mtproto_blocked_ips_created_at"), table_name="mtproto_blocked_ips")
    op.drop_index(op.f("ix_mtproto_blocked_ips_created_by_admin_id"), table_name="mtproto_blocked_ips")
    op.drop_index(op.f("ix_mtproto_blocked_ips_expires_at"), table_name="mtproto_blocked_ips")
    op.drop_index(op.f("ix_mtproto_blocked_ips_status"), table_name="mtproto_blocked_ips")
    op.drop_index(op.f("ix_mtproto_blocked_ips_ip_hash"), table_name="mtproto_blocked_ips")
    op.drop_index(op.f("ix_mtproto_blocked_ips_ip_observation_id"), table_name="mtproto_blocked_ips")
    op.drop_index(op.f("ix_mtproto_blocked_ips_user_id"), table_name="mtproto_blocked_ips")
    op.drop_index(op.f("ix_mtproto_blocked_ips_assignment_id"), table_name="mtproto_blocked_ips")
    op.drop_table("mtproto_blocked_ips")

    op.drop_index("ix_mtproto_admin_alerts_user_status", table_name="mtproto_admin_alerts")
    op.drop_index("ix_mtproto_admin_alerts_assignment_status", table_name="mtproto_admin_alerts")
    op.drop_index("ix_mtproto_admin_alerts_status_severity", table_name="mtproto_admin_alerts")
    op.drop_index(op.f("ix_mtproto_admin_alerts_resolved_by_admin_id"), table_name="mtproto_admin_alerts")
    op.drop_index(op.f("ix_mtproto_admin_alerts_acknowledged_by_admin_id"), table_name="mtproto_admin_alerts")
    op.drop_index(op.f("ix_mtproto_admin_alerts_created_at"), table_name="mtproto_admin_alerts")
    op.drop_index(op.f("ix_mtproto_admin_alerts_last_seen_at"), table_name="mtproto_admin_alerts")
    op.drop_index(op.f("ix_mtproto_admin_alerts_first_seen_at"), table_name="mtproto_admin_alerts")
    op.drop_index(op.f("ix_mtproto_admin_alerts_window_end"), table_name="mtproto_admin_alerts")
    op.drop_index(op.f("ix_mtproto_admin_alerts_window_start"), table_name="mtproto_admin_alerts")
    op.drop_index(op.f("ix_mtproto_admin_alerts_status"), table_name="mtproto_admin_alerts")
    op.drop_index(op.f("ix_mtproto_admin_alerts_severity"), table_name="mtproto_admin_alerts")
    op.drop_index(op.f("ix_mtproto_admin_alerts_signal_type"), table_name="mtproto_admin_alerts")
    op.drop_index(op.f("ix_mtproto_admin_alerts_user_id"), table_name="mtproto_admin_alerts")
    op.drop_index(op.f("ix_mtproto_admin_alerts_assignment_id"), table_name="mtproto_admin_alerts")
    op.drop_index(op.f("ix_mtproto_admin_alerts_abuse_signal_id"), table_name="mtproto_admin_alerts")
    op.drop_index(op.f("ix_mtproto_admin_alerts_dedupe_key"), table_name="mtproto_admin_alerts")
    op.drop_table("mtproto_admin_alerts")

    op.drop_index("ix_mtproto_ip_observations_hash_last_seen", table_name="mtproto_ip_observations")
    op.drop_index("ix_mtproto_ip_observations_user_last_seen", table_name="mtproto_ip_observations")
    op.drop_index("ix_mtproto_ip_observations_assignment_active", table_name="mtproto_ip_observations")
    op.drop_index(op.f("ix_mtproto_ip_observations_current_active"), table_name="mtproto_ip_observations")
    op.drop_index(op.f("ix_mtproto_ip_observations_last_active_at"), table_name="mtproto_ip_observations")
    op.drop_index(op.f("ix_mtproto_ip_observations_last_seen_at"), table_name="mtproto_ip_observations")
    op.drop_index(op.f("ix_mtproto_ip_observations_first_seen_at"), table_name="mtproto_ip_observations")
    op.drop_index(op.f("ix_mtproto_ip_observations_ip_hash"), table_name="mtproto_ip_observations")
    op.drop_index(op.f("ix_mtproto_ip_observations_user_id"), table_name="mtproto_ip_observations")
    op.drop_index(op.f("ix_mtproto_ip_observations_assignment_id"), table_name="mtproto_ip_observations")
    op.drop_table("mtproto_ip_observations")
# END_BLOCK_PHASE43_SCHEMA
