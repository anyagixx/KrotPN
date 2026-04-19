"""add vpn client preshared key

Revision ID: 20260418_add_vpn_client_preshared_key
Revises: 2699e47c4e1b
Create Date: 2026-04-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260418_add_vpn_client_preshared_key"
down_revision: Union[str, Sequence[str], None] = "2699e47c4e1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable encrypted preshared key storage for AWG peers."""
    op.add_column("vpn_clients", sa.Column("preshared_key_enc", sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Remove nullable encrypted preshared key storage."""
    op.drop_column("vpn_clients", "preshared_key_enc")
