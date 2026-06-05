"""add_vpn_device_abuse_alerts

Revision ID: phase78_vpn_device_abuse_alerts
Revises: phase50_paid_tariff_catalog
Create Date: 2026-06-06 00:00:00.000000

# FILE: backend/alembic/versions/phase78_vpn_device_abuse_alerts.py
# VERSION: 1.0.0
# ROLE: SCRIPT
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Add Phase-78 durable VPN device abuse alert inbox schema
#   SCOPE: vpn_device_abuse_alerts table and indexes for open inbox plus resolved archive
#   DEPENDS: M-028 (migration governance), M-081 (VPN device abuse alert inbox)
#   LINKS: M-028, M-081, V-M-081
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   upgrade - Creates vpn_device_abuse_alerts with safe review/action metadata
#   downgrade - Drops vpn_device_abuse_alerts and its indexes
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-78 VPN device abuse alert inbox migration
# END_CHANGE_SUMMARY
"""

from typing import Sequence, Union
import logging

import sqlalchemy as sa
from alembic import op


revision: str = "phase78_vpn_device_abuse_alerts"
down_revision: Union[str, Sequence[str], None] = "phase50_paid_tariff_catalog"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
logger = logging.getLogger("alembic.runtime.migration")


# START_BLOCK_PHASE78_VPN_DEVICE_ABUSE_ALERTS_SCHEMA
def upgrade() -> None:
    """Upgrade schema with durable VPN device abuse alert inbox rows."""
    logger.info("[M-081][migration][VPN_DEVICE_ABUSE_ALERTS_SCHEMA] creating Phase-78 table")
    op.create_table(
        "vpn_device_abuse_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=180), nullable=False),
        sa.Column("source_event_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("signal_type", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="warning"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False, server_default="confirmed_anti_sharing_signal"),
        sa.Column("user_email_snapshot", sa.String(length=255), nullable=True),
        sa.Column("device_name_snapshot", sa.String(length=120), nullable=True),
        sa.Column("device_status_snapshot", sa.String(length=30), nullable=True),
        sa.Column("config_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_endpoint", sa.String(length=255), nullable=True),
        sa.Column("last_handshake_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("action_taken", sa.String(length=80), nullable=True),
        sa.Column("action_result", sa.String(length=160), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["source_event_id"], ["device_security_events.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["device_id"], ["user_devices.id"]),
        sa.ForeignKeyConstraint(["resolved_by_admin_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_vpn_device_abuse_alerts_dedupe_key"), "vpn_device_abuse_alerts", ["dedupe_key"], unique=False)
    op.create_index(op.f("ix_vpn_device_abuse_alerts_source_event_id"), "vpn_device_abuse_alerts", ["source_event_id"], unique=False)
    op.create_index(op.f("ix_vpn_device_abuse_alerts_user_id"), "vpn_device_abuse_alerts", ["user_id"], unique=False)
    op.create_index(op.f("ix_vpn_device_abuse_alerts_device_id"), "vpn_device_abuse_alerts", ["device_id"], unique=False)
    op.create_index(op.f("ix_vpn_device_abuse_alerts_signal_type"), "vpn_device_abuse_alerts", ["signal_type"], unique=False)
    op.create_index(op.f("ix_vpn_device_abuse_alerts_severity"), "vpn_device_abuse_alerts", ["severity"], unique=False)
    op.create_index(op.f("ix_vpn_device_abuse_alerts_status"), "vpn_device_abuse_alerts", ["status"], unique=False)
    op.create_index(op.f("ix_vpn_device_abuse_alerts_first_seen_at"), "vpn_device_abuse_alerts", ["first_seen_at"], unique=False)
    op.create_index(op.f("ix_vpn_device_abuse_alerts_last_seen_at"), "vpn_device_abuse_alerts", ["last_seen_at"], unique=False)
    op.create_index(op.f("ix_vpn_device_abuse_alerts_created_at"), "vpn_device_abuse_alerts", ["created_at"], unique=False)
    op.create_index(op.f("ix_vpn_device_abuse_alerts_resolved_by_admin_id"), "vpn_device_abuse_alerts", ["resolved_by_admin_id"], unique=False)
    op.create_index("ix_vpn_device_abuse_alerts_status_seen", "vpn_device_abuse_alerts", ["status", "last_seen_at"], unique=False)
    op.create_index("ix_vpn_device_abuse_alerts_device_status", "vpn_device_abuse_alerts", ["device_id", "status"], unique=False)
    op.create_index("ix_vpn_device_abuse_alerts_user_status", "vpn_device_abuse_alerts", ["user_id", "status"], unique=False)
    op.create_index("ix_vpn_device_abuse_alerts_open_dedupe", "vpn_device_abuse_alerts", ["dedupe_key", "status"], unique=False)


def downgrade() -> None:
    """Downgrade schema by removing VPN device abuse alert inbox rows."""
    op.drop_index("ix_vpn_device_abuse_alerts_open_dedupe", table_name="vpn_device_abuse_alerts")
    op.drop_index("ix_vpn_device_abuse_alerts_user_status", table_name="vpn_device_abuse_alerts")
    op.drop_index("ix_vpn_device_abuse_alerts_device_status", table_name="vpn_device_abuse_alerts")
    op.drop_index("ix_vpn_device_abuse_alerts_status_seen", table_name="vpn_device_abuse_alerts")
    op.drop_index(op.f("ix_vpn_device_abuse_alerts_resolved_by_admin_id"), table_name="vpn_device_abuse_alerts")
    op.drop_index(op.f("ix_vpn_device_abuse_alerts_created_at"), table_name="vpn_device_abuse_alerts")
    op.drop_index(op.f("ix_vpn_device_abuse_alerts_last_seen_at"), table_name="vpn_device_abuse_alerts")
    op.drop_index(op.f("ix_vpn_device_abuse_alerts_first_seen_at"), table_name="vpn_device_abuse_alerts")
    op.drop_index(op.f("ix_vpn_device_abuse_alerts_status"), table_name="vpn_device_abuse_alerts")
    op.drop_index(op.f("ix_vpn_device_abuse_alerts_severity"), table_name="vpn_device_abuse_alerts")
    op.drop_index(op.f("ix_vpn_device_abuse_alerts_signal_type"), table_name="vpn_device_abuse_alerts")
    op.drop_index(op.f("ix_vpn_device_abuse_alerts_device_id"), table_name="vpn_device_abuse_alerts")
    op.drop_index(op.f("ix_vpn_device_abuse_alerts_user_id"), table_name="vpn_device_abuse_alerts")
    op.drop_index(op.f("ix_vpn_device_abuse_alerts_source_event_id"), table_name="vpn_device_abuse_alerts")
    op.drop_index(op.f("ix_vpn_device_abuse_alerts_dedupe_key"), table_name="vpn_device_abuse_alerts")
    op.drop_table("vpn_device_abuse_alerts")
# END_BLOCK_PHASE78_VPN_DEVICE_ABUSE_ALERTS_SCHEMA
