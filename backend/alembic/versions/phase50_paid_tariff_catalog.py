"""add_paid_tariff_catalog_fields

Revision ID: phase50_paid_tariff_catalog
Revises: phase45_pending_trial_activation
Create Date: 2026-06-02 00:00:00.000000

# FILE: backend/alembic/versions/phase50_paid_tariff_catalog.py
# VERSION: 1.0.0
# ROLE: SCRIPT
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Add Phase-50 canonical paid tariff identity fields to plans
#   SCOPE: plans.slug, plans.is_canonical, slug index, and canonical tariff seed data
#   DEPENDS: M-028 (migration governance), M-068 (paid tariff catalog)
#   LINKS: M-028, M-068, V-M-028, V-M-068
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   upgrade - Adds tariff identity fields and converges the three canonical plans
#   downgrade - Removes Phase-50 index and identity fields
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-50 canonical paid tariff catalog schema
# END_CHANGE_SUMMARY
"""

from typing import Sequence, Union
import logging

import sqlalchemy as sa
from alembic import op


revision: str = "phase50_paid_tariff_catalog"
down_revision: Union[str, Sequence[str], None] = "phase45_pending_trial_activation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
logger = logging.getLogger("alembic.runtime.migration")


# START_BLOCK_PHASE50_PAID_TARIFF_CATALOG_SCHEMA
def upgrade() -> None:
    """Upgrade schema with canonical paid tariff identity."""
    logger.info("[M-068][migration][PAID_TARIFF_CATALOG_SCHEMA] adding Phase-50 plan fields")
    op.add_column("plans", sa.Column("slug", sa.String(length=80), nullable=True))
    op.add_column(
        "plans",
        sa.Column("is_canonical", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(op.f("ix_plans_slug"), "plans", ["slug"], unique=False)

    catalog = [
        (
            "krotpn-1",
            "KrotPN 1",
            "Персональный тариф для одного устройства.",
            369.0,
            1,
            '["1 устройство", "AmneziaWG Full Tunnel", "Персональный Telegram MTProto proxy", "Личный кабинет и QR/.conf"]',
            False,
            10,
        ),
        (
            "krotpn-6",
            "KrotPN 6",
            "Оптимальный тариф для нескольких устройств.",
            693.0,
            6,
            '["До 6 устройств", "AmneziaWG Full Tunnel", "Персональный Telegram MTProto proxy", "Удобно для семьи и рабочих устройств"]',
            True,
            20,
        ),
        (
            "krotpn-9",
            "KrotPN 9",
            "Максимальный стандартный тариф KrotPN.",
            936.0,
            9,
            '["До 9 устройств", "AmneziaWG Full Tunnel", "Персональный Telegram MTProto proxy", "Максимальный лимит стандартной линейки"]',
            False,
            30,
        ),
    ]
    for slug, name, description, price, device_limit, features, is_popular, sort_order in catalog:
        op.execute(
            sa.text(
                """
                INSERT INTO plans (
                    slug, name, description, price, currency, duration_days,
                    device_limit, features, is_active, is_canonical,
                    is_popular, sort_order, created_at, updated_at
                )
                SELECT
                    :slug, :name, :description, :price, 'RUB', 30,
                    :device_limit, :features, TRUE, TRUE,
                    :is_popular, :sort_order, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                WHERE NOT EXISTS (SELECT 1 FROM plans WHERE slug = :slug)
                """
            ).bindparams(
                slug=slug,
                name=name,
                description=description,
                price=price,
                device_limit=device_limit,
                features=features,
                is_popular=is_popular,
                sort_order=sort_order,
            )
        )
        op.execute(
            sa.text(
                """
                UPDATE plans
                SET
                    name = :name,
                    description = :description,
                    price = :price,
                    currency = 'RUB',
                    duration_days = 30,
                    device_limit = :device_limit,
                    features = :features,
                    is_active = TRUE,
                    is_canonical = TRUE,
                    is_popular = :is_popular,
                    sort_order = :sort_order,
                    updated_at = CURRENT_TIMESTAMP
                WHERE slug = :slug
                """
            ).bindparams(
                slug=slug,
                name=name,
                description=description,
                price=price,
                device_limit=device_limit,
                features=features,
                is_popular=is_popular,
                sort_order=sort_order,
            )
        )


def downgrade() -> None:
    """Downgrade schema by removing Phase-50 tariff identity fields."""
    op.drop_index(op.f("ix_plans_slug"), table_name="plans")
    op.drop_column("plans", "is_canonical")
    op.drop_column("plans", "slug")
# END_BLOCK_PHASE50_PAID_TARIFF_CATALOG_SCHEMA
