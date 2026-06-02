"""Phase-50 billing tariff catalog tests.

# FILE: backend/tests/test_billing_tariff_catalog.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify the Phase-50 canonical paid tariff catalog and idempotent convergence behavior
#   SCOPE: Catalog definitions, clean DB upsert, stale-value correction, duplicate prevention, and canonical API ordering
#   DEPENDS: M-001 async DB setup, M-004 billing service/models, M-068 paid tariff catalog
#   LINKS: V-M-068
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   billing_session - In-memory async DB fixture
#   test_canonical_tariff_catalog_matches_phase50_matrix - Verifies approved tariff values
#   test_ensure_canonical_tariffs_is_idempotent_and_repairs_stale_rows - Verifies convergence without duplicates
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-50 canonical tariff catalog verification
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.billing.catalog import CANONICAL_TARIFFS
from app.billing.models import Plan
from app.billing.service import BillingService
from app.core.database import import_all_models


@pytest.fixture
async def billing_session():
    import_all_models()
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

    await engine.dispose()


# START_BLOCK: phase50_catalog_matrix
def test_canonical_tariff_catalog_matches_phase50_matrix():
    """The in-code catalog must match the approved Phase-50 matrix exactly."""
    matrix = [
        (tariff.slug, tariff.price, tariff.device_limit, tariff.duration_days, tariff.is_popular)
        for tariff in CANONICAL_TARIFFS
    ]

    assert matrix == [
        ("krotpn-1", 369.0, 1, 30, False),
        ("krotpn-6", 693.0, 6, 30, True),
        ("krotpn-9", 936.0, 9, 30, False),
    ]
# END_BLOCK


# START_BLOCK: phase50_catalog_upsert
@pytest.mark.asyncio
async def test_ensure_canonical_tariffs_is_idempotent_and_repairs_stale_rows(billing_session: AsyncSession):
    """Repeated convergence must not duplicate canonical plan rows."""
    service = BillingService(billing_session)

    first = await service.ensure_canonical_tariffs()
    second = await service.ensure_canonical_tariffs()

    assert [plan.slug for plan in first] == ["krotpn-1", "krotpn-6", "krotpn-9"]
    assert [plan.id for plan in first] == [plan.id for plan in second]

    stale = first[1]
    stale.price = 1.0
    stale.device_limit = 2
    stale.is_active = False
    await billing_session.flush()

    repaired = await service.ensure_canonical_tariffs()
    repaired_by_slug = {plan.slug: plan for plan in repaired}
    assert repaired_by_slug["krotpn-6"].price == 693.0
    assert repaired_by_slug["krotpn-6"].device_limit == 6
    assert repaired_by_slug["krotpn-6"].is_active is True

    result = await billing_session.execute(select(Plan).where(Plan.is_canonical == True))
    canonical_rows = list(result.scalars().all())
    assert sorted(plan.slug for plan in canonical_rows) == ["krotpn-1", "krotpn-6", "krotpn-9"]
# END_BLOCK
