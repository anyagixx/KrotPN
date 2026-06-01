"""add_password_reset_tokens

Revision ID: phase44_password_reset_tokens
Revises: phase43_mtproto_admin_analytics
Create Date: 2026-06-01 00:00:00.000000

# FILE: backend/alembic/versions/phase44_add_password_reset_tokens.py
# VERSION: 1.0.0
# ROLE: SCRIPT
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Add replay-safe password reset token persistence for Phase-44 account recovery
#   SCOPE: password_reset_tokens table, token hash uniqueness, lifecycle/status indexes, and user/email lookup indexes
#   DEPENDS: M-028 (migration governance), M-062 (auth email UX and password security)
#   LINKS: M-028, M-062, V-M-028, V-M-062
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   upgrade - Creates password_reset_tokens table and indexes
#   downgrade - Drops password_reset_tokens table and indexes
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-44 password reset token schema
# END_CHANGE_SUMMARY
"""

from typing import Sequence, Union
import logging

import sqlalchemy as sa
from alembic import op


revision: str = "phase44_password_reset_tokens"
down_revision: Union[str, Sequence[str], None] = "phase43_mtproto_admin_analytics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
logger = logging.getLogger("alembic.runtime.migration")


# START_BLOCK_PHASE44_PASSWORD_RESET_SCHEMA
def upgrade() -> None:
    """Upgrade schema with password reset token persistence."""
    logger.info("[M-062][migration][PASSWORD_RESET_TOKEN_SCHEMA] creating Phase-44 table")
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_password_reset_tokens_user_id"), "password_reset_tokens", ["user_id"], unique=False)
    op.create_index(op.f("ix_password_reset_tokens_email"), "password_reset_tokens", ["email"], unique=False)
    op.create_index(op.f("ix_password_reset_tokens_token_hash"), "password_reset_tokens", ["token_hash"], unique=True)
    op.create_index(op.f("ix_password_reset_tokens_status"), "password_reset_tokens", ["status"], unique=False)
    op.create_index("ix_password_reset_tokens_user_status", "password_reset_tokens", ["user_id", "status"], unique=False)
    op.create_index("ix_password_reset_tokens_expires_status", "password_reset_tokens", ["expires_at", "status"], unique=False)


def downgrade() -> None:
    """Downgrade schema by removing password reset token persistence."""
    op.drop_index("ix_password_reset_tokens_expires_status", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_status", table_name="password_reset_tokens")
    op.drop_index(op.f("ix_password_reset_tokens_status"), table_name="password_reset_tokens")
    op.drop_index(op.f("ix_password_reset_tokens_token_hash"), table_name="password_reset_tokens")
    op.drop_index(op.f("ix_password_reset_tokens_email"), table_name="password_reset_tokens")
    op.drop_index(op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
# END_BLOCK_PHASE44_PASSWORD_RESET_SCHEMA
