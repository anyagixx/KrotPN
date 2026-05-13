"""add_mtproto_assignments

Revision ID: b3f1e0d2c9a4
Revises: 2699e47c4e1b
Create Date: 2026-05-14 00:00:00.000000

# FILE: backend/alembic/versions/b3f1e0d2c9a4_add_mtproto_assignments.py
# VERSION: 1.0.0
# ROLE: SCRIPT
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Add restore-safe MTProto assignment registry schema
#   SCOPE: mtproto_assignments table, user/SNI uniqueness indexes,
#          lifecycle indexes, downgrade cleanup
#   DEPENDS: M-028 (migration governance), M-042 (assignment registry)
#   LINKS: M-028, M-042, V-M-028, V-M-042
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   upgrade - Creates mtproto_assignments and uniqueness indexes
#   downgrade - Drops mtproto_assignments and PostgreSQL enum types when applicable
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-29 MTProto assignment registry migration
# END_CHANGE_SUMMARY
"""
import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b3f1e0d2c9a4"
down_revision: Union[str, Sequence[str], None] = "2699e47c4e1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
logger = logging.getLogger("alembic.runtime.migration")


# START_BLOCK_MTPROTO_ASSIGNMENT_SCHEMA
def upgrade() -> None:
    """Upgrade schema with MTProto assignment registry."""
    logger.info("[M-042][migration][MTPROTO_ASSIGNMENT_SCHEMA] creating mtproto_assignments")
    op.create_table(
        "mtproto_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("sni", sa.String(length=255), nullable=False),
        sa.Column(
            "credential_mode",
            sa.Enum("DERIVED_PER_SNI", name="mtprotocredentialmode"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE",
                "REISSUE_REQUIRED",
                "SUPERSEDED",
                "DISABLED",
                name="mtprotoassignmentstatus",
            ),
            nullable=False,
        ),
        sa.Column("rotation_marker", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mtproto_assignments_user_id"),
        "mtproto_assignments",
        ["user_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_mtproto_assignments_sni"),
        "mtproto_assignments",
        ["sni"],
        unique=True,
    )
    op.create_index(
        op.f("ix_mtproto_assignments_status"),
        "mtproto_assignments",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema by removing MTProto assignment registry."""
    op.drop_index(op.f("ix_mtproto_assignments_status"), table_name="mtproto_assignments")
    op.drop_index(op.f("ix_mtproto_assignments_sni"), table_name="mtproto_assignments")
    op.drop_index(op.f("ix_mtproto_assignments_user_id"), table_name="mtproto_assignments")
    op.drop_table("mtproto_assignments")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS mtprotoassignmentstatus")
        op.execute("DROP TYPE IF EXISTS mtprotocredentialmode")
# END_BLOCK_MTPROTO_ASSIGNMENT_SCHEMA
