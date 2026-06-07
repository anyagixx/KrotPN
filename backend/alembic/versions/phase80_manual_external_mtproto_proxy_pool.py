"""add_manual_external_mtproto_proxy_pool

Revision ID: phase80_manual_external_mtproto_pool
Revises: phase78_vpn_device_abuse_alerts
Create Date: 2026-06-07 00:00:00.000000

# FILE: backend/alembic/versions/phase80_manual_external_mtproto_proxy_pool.py
# VERSION: 1.0.0
# ROLE: SCRIPT
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Add Phase-80 manual external MTProto proxy pool and delivery settings schema
#   SCOPE: mtproto_manual_external_proxies and mtproto_delivery_settings tables plus indexes
#   DEPENDS: M-028 (migration governance), M-082 (manual external MTProto proxy pool)
#   LINKS: M-028, M-082, V-M-082
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   upgrade - Creates manual external MTProto pool and delivery settings tables
#   downgrade - Drops Phase-80 manual external MTProto tables
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-80 manual external MTProto proxy pool migration.
# END_CHANGE_SUMMARY
"""

from typing import Sequence, Union
import logging

import sqlalchemy as sa
from alembic import op


revision: str = "phase80_manual_external_mtproto_pool"
down_revision: Union[str, Sequence[str], None] = "phase78_vpn_device_abuse_alerts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
logger = logging.getLogger("alembic.runtime.migration")


# START_BLOCK_PHASE80_MANUAL_EXTERNAL_MTPROTO_SCHEMA
def upgrade() -> None:
    """Upgrade schema with manual external MTProto proxy pool rows."""
    logger.info("[M-082][migration][MANUAL_EXTERNAL_MTPROTO_SCHEMA] creating Phase-80 tables")
    op.create_table(
        "mtproto_manual_external_proxies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("server", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default="443"),
        sa.Column("secret_enc", sa.Text(), nullable=False),
        sa.Column("secret_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="ready"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_admin_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mtproto_manual_external_proxies_name"), "mtproto_manual_external_proxies", ["name"], unique=False)
    op.create_index(op.f("ix_mtproto_manual_external_proxies_server"), "mtproto_manual_external_proxies", ["server"], unique=False)
    op.create_index(op.f("ix_mtproto_manual_external_proxies_secret_fingerprint"), "mtproto_manual_external_proxies", ["secret_fingerprint"], unique=False)
    op.create_index(op.f("ix_mtproto_manual_external_proxies_status"), "mtproto_manual_external_proxies", ["status"], unique=False)
    op.create_index(op.f("ix_mtproto_manual_external_proxies_priority"), "mtproto_manual_external_proxies", ["priority"], unique=False)
    op.create_index(op.f("ix_mtproto_manual_external_proxies_created_by_admin_id"), "mtproto_manual_external_proxies", ["created_by_admin_id"], unique=False)
    op.create_index(op.f("ix_mtproto_manual_external_proxies_updated_by_admin_id"), "mtproto_manual_external_proxies", ["updated_by_admin_id"], unique=False)

    op.create_table(
        "mtproto_delivery_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=50), nullable=False, server_default="automatic"),
        sa.Column("active_manual_proxy_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["active_manual_proxy_id"], ["mtproto_manual_external_proxies.id"]),
        sa.ForeignKeyConstraint(["updated_by_admin_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mtproto_delivery_settings_mode"), "mtproto_delivery_settings", ["mode"], unique=False)
    op.create_index(op.f("ix_mtproto_delivery_settings_active_manual_proxy_id"), "mtproto_delivery_settings", ["active_manual_proxy_id"], unique=False)
    op.create_index(op.f("ix_mtproto_delivery_settings_updated_by_admin_id"), "mtproto_delivery_settings", ["updated_by_admin_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema by removing Phase-80 manual external MTProto tables."""
    op.drop_index(op.f("ix_mtproto_delivery_settings_updated_by_admin_id"), table_name="mtproto_delivery_settings")
    op.drop_index(op.f("ix_mtproto_delivery_settings_active_manual_proxy_id"), table_name="mtproto_delivery_settings")
    op.drop_index(op.f("ix_mtproto_delivery_settings_mode"), table_name="mtproto_delivery_settings")
    op.drop_table("mtproto_delivery_settings")
    op.drop_index(op.f("ix_mtproto_manual_external_proxies_updated_by_admin_id"), table_name="mtproto_manual_external_proxies")
    op.drop_index(op.f("ix_mtproto_manual_external_proxies_created_by_admin_id"), table_name="mtproto_manual_external_proxies")
    op.drop_index(op.f("ix_mtproto_manual_external_proxies_priority"), table_name="mtproto_manual_external_proxies")
    op.drop_index(op.f("ix_mtproto_manual_external_proxies_status"), table_name="mtproto_manual_external_proxies")
    op.drop_index(op.f("ix_mtproto_manual_external_proxies_secret_fingerprint"), table_name="mtproto_manual_external_proxies")
    op.drop_index(op.f("ix_mtproto_manual_external_proxies_server"), table_name="mtproto_manual_external_proxies")
    op.drop_index(op.f("ix_mtproto_manual_external_proxies_name"), table_name="mtproto_manual_external_proxies")
    op.drop_table("mtproto_manual_external_proxies")
# END_BLOCK_PHASE80_MANUAL_EXTERNAL_MTPROTO_SCHEMA
