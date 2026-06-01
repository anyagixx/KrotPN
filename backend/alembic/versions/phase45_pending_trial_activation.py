"""add_pending_trial_activation_fields

Revision ID: phase45_pending_trial_activation
Revises: phase44_password_reset_tokens
Create Date: 2026-06-01 00:00:00.000000

# FILE: backend/alembic/versions/phase45_pending_trial_activation.py
# VERSION: 1.0.0
# ROLE: SCRIPT
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Add Phase-45 pending trial activation fields to subscriptions
#   SCOPE: pending_activation, activated_at, trial_duration_days columns and indexes
#   DEPENDS: M-028 (migration governance), M-063 (trial activation)
#   LINKS: M-028, M-063, V-M-028, V-M-063
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   upgrade - Adds pending trial lifecycle fields and lookup indexes
#   downgrade - Removes Phase-45 indexes and columns
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-45 pending trial activation schema
# END_CHANGE_SUMMARY
"""

from typing import Sequence, Union
import logging

import sqlalchemy as sa
from alembic import op


revision: str = "phase45_pending_trial_activation"
down_revision: Union[str, Sequence[str], None] = "phase44_password_reset_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
logger = logging.getLogger("alembic.runtime.migration")


# START_BLOCK_PHASE45_PENDING_TRIAL_SCHEMA
def upgrade() -> None:
    """Upgrade schema with pending trial activation state."""
    logger.info("[M-063][migration][PENDING_TRIAL_SCHEMA] adding Phase-45 subscription columns")
    op.add_column(
        "subscriptions",
        sa.Column("pending_activation", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("subscriptions", sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("trial_duration_days", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_subscriptions_pending_activation"), "subscriptions", ["pending_activation"], unique=False)
    op.create_index(
        "ix_subscriptions_user_pending_trial",
        "subscriptions",
        ["user_id", "pending_activation"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema by removing pending trial activation state."""
    op.drop_index("ix_subscriptions_user_pending_trial", table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_pending_activation"), table_name="subscriptions")
    op.drop_column("subscriptions", "trial_duration_days")
    op.drop_column("subscriptions", "activated_at")
    op.drop_column("subscriptions", "pending_activation")
# END_BLOCK_PHASE45_PENDING_TRIAL_SCHEMA
