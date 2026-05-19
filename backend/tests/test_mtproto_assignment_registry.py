"""MTProto assignment registry tests.

# FILE: backend/tests/test_mtproto_assignment_registry.py
# VERSION: 1.2.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify restore-safe MTProto assignment persistence invariants
#   SCOPE: Idempotent derived-per-SNI assignment writes, user/SNI uniqueness,
#          redacted listing, and migration evidence
#   DEPENDS: M-042, M-028, M-044
#   LINKS: V-M-042, V-M-028, V-M-044
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   test_save_assignment_is_idempotent_and_redacted - Covers one-assignment-per-user
#   test_save_assignment_rejects_duplicate_sni_for_other_user - Covers SNI uniqueness
#   test_assignment_model_is_restore_safe - Covers persisted column allowlist
#   test_mtproto_assignment_migration_contains_registry_schema - Covers migration evidence
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.2.0 - Restored default assignment mode to KPprotoN derived-per-SNI.
#   LAST_CHANGE: v1.1.0 - Updated default assignment mode for Phase-40 official MTProxy.
#   LAST_CHANGE: v1.0.0 - Added Phase-29 assignment registry tests
# END_CHANGE_SUMMARY
"""

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.mtproto.models import (
    MTProtoAssignment,
    MTProtoAssignmentStatus,
    MTProtoCredentialMode,
)
from app.mtproto.repository import MTProtoAssignmentConflict, MTProtoAssignmentRepository
from app.users.models import User


# START_BLOCK_FIXTURES
async def _create_user(db_session: AsyncSession, email: str) -> User:
    user = User(email=email, email_verified=True, is_active=True)
    db_session.add(user)
    await db_session.flush()
    return user
# END_BLOCK_FIXTURES


# START_BLOCK_ASSIGNMENT_REGISTRY_TESTS
@pytest.mark.asyncio
async def test_save_assignment_is_idempotent_and_redacted(db_session: AsyncSession):
    user = await _create_user(db_session, "mtproto-user@example.com")
    repo = MTProtoAssignmentRepository(db_session)

    first = await repo.save_assignment(
        user_id=int(user.id),
        sni="u-111111111111.krotpn.xyz",
        rotation_marker="v1",
    )
    second = await repo.save_assignment(
        user_id=int(user.id),
        sni="u-222222222222.krotpn.xyz",
        rotation_marker="v1",
    )
    listed = await repo.list_assignments()

    assert second.id == first.id
    assert second.sni == "u-111111111111.krotpn.xyz"
    assert second.credential_mode == MTProtoCredentialMode.DERIVED_PER_SNI
    assert second.status == MTProtoAssignmentStatus.ACTIVE
    assert len(listed) == 1
    assert not hasattr(listed[0], "secret")
    assert not hasattr(listed[0], "tg_link")
    assert not hasattr(listed[0], "base_secret")


@pytest.mark.asyncio
async def test_save_assignment_rejects_duplicate_sni_for_other_user(db_session: AsyncSession):
    first_user = await _create_user(db_session, "mtproto-first@example.com")
    second_user = await _create_user(db_session, "mtproto-second@example.com")
    repo = MTProtoAssignmentRepository(db_session)

    await repo.save_assignment(
        user_id=int(first_user.id),
        sni="u-aaaaaaaaaaaa.krotpn.xyz",
        rotation_marker="v1",
    )

    with pytest.raises(MTProtoAssignmentConflict):
        await repo.save_assignment(
            user_id=int(second_user.id),
            sni="u-aaaaaaaaaaaa.krotpn.xyz",
            rotation_marker="v1",
        )


def test_assignment_model_is_restore_safe():
    persisted_fields = set(MTProtoAssignment.model_fields)

    assert {"id", "user_id", "sni", "credential_mode", "status", "rotation_marker"} <= (
        persisted_fields
    )
    assert "secret" not in persisted_fields
    assert "tg_link" not in persisted_fields
    assert "base_secret" not in persisted_fields
    assert "secret_salt" not in persisted_fields


def test_mtproto_assignment_migration_contains_registry_schema():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "b3f1e0d2c9a4_add_mtproto_assignments.py"
    )
    migration_text = migration_path.read_text(encoding="utf-8")

    assert "mtproto_assignments" in migration_text
    assert "ix_mtproto_assignments_user_id" in migration_text
    assert "ix_mtproto_assignments_sni" in migration_text
    assert "[M-042][migration][MTPROTO_ASSIGNMENT_SCHEMA]" in migration_text
# END_BLOCK_ASSIGNMENT_REGISTRY_TESTS
