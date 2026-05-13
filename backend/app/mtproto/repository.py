"""MTProto assignment repository.

# FILE: backend/app/mtproto/repository.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Provide idempotent persistence helpers for MTProto assignments
#   SCOPE: Lookup by user/SNI, save/update assignment rows, and admin-safe listing
#   DEPENDS: M-042 (models), SQLAlchemy AsyncSession
#   LINKS: M-042, V-M-042
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MTProtoAssignmentConflict - Stable uniqueness conflict exception
#   MTProtoAssignmentRepository - Async repository for MTProtoAssignment rows
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-29 MTProto assignment repository
# END_CHANGE_SUMMARY
"""

from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mtproto.models import (
    MTProtoAssignment,
    MTProtoAssignmentStatus,
    MTProtoCredentialMode,
)


class MTProtoAssignmentConflict(ValueError):
    """Raised when an MTProto assignment uniqueness invariant would be violated."""


class MTProtoAssignmentRepository:
    """Persistence boundary for personal MTProto proxy assignments."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # START_CONTRACT: get_user_assignment
    #   PURPOSE: Return the canonical assignment row for one user
    #   INPUTS: user_id: int - canonical user id
    #   OUTPUTS: MTProtoAssignment | None
    #   SIDE_EFFECTS: database read and redacted log marker
    #   LINKS: M-042, V-M-042
    # END_CONTRACT: get_user_assignment
    # START_BLOCK_LOOKUP_USER
    async def get_user_assignment(self, user_id: int) -> MTProtoAssignment | None:
        """Return one user's assignment, if it exists."""
        logger.info(f"[M-042][get_user_assignment][LOOKUP_USER] user_id={user_id}")
        result = await self.session.execute(
            select(MTProtoAssignment).where(MTProtoAssignment.user_id == user_id)
        )
        return result.scalar_one_or_none()
    # END_BLOCK_LOOKUP_USER

    # START_CONTRACT: get_assignment_by_sni
    #   PURPOSE: Return an assignment by SNI for collision checks
    #   INPUTS: sni: str - candidate SNI domain
    #   OUTPUTS: MTProtoAssignment | None
    #   SIDE_EFFECTS: database read
    #   LINKS: M-042, V-M-042
    # END_CONTRACT: get_assignment_by_sni
    # START_BLOCK_LOOKUP_SNI
    async def get_assignment_by_sni(self, sni: str) -> MTProtoAssignment | None:
        """Return an assignment for an SNI, if it exists."""
        result = await self.session.execute(
            select(MTProtoAssignment).where(MTProtoAssignment.sni == sni)
        )
        return result.scalar_one_or_none()
    # END_BLOCK_LOOKUP_SNI

    # START_CONTRACT: save_assignment
    #   PURPOSE: Create or update one canonical user assignment idempotently
    #   INPUTS: user_id, sni, credential_mode, status, rotation_marker, replace
    #   OUTPUTS: MTProtoAssignment
    #   SIDE_EFFECTS: database write and redacted log markers
    #   LINKS: M-042, V-M-042
    # END_CONTRACT: save_assignment
    # START_BLOCK_WRITE_ASSIGNMENT
    async def save_assignment(
        self,
        *,
        user_id: int,
        sni: str,
        credential_mode: MTProtoCredentialMode = MTProtoCredentialMode.DERIVED_PER_SNI,
        status: MTProtoAssignmentStatus = MTProtoAssignmentStatus.ACTIVE,
        rotation_marker: str = "v1",
        replace: bool = False,
    ) -> MTProtoAssignment:
        """Create or update a user's canonical assignment without storing secrets."""
        now = datetime.now(timezone.utc)
        existing_for_sni = await self.get_assignment_by_sni(sni)
        if existing_for_sni is not None and existing_for_sni.user_id != user_id:
            logger.warning(
                "[M-042][save_assignment][UNIQUENESS_CONFLICT] "
                f"user_id={user_id} assignment_id={existing_for_sni.id}"
            )
            raise MTProtoAssignmentConflict("SNI is already assigned")

        existing = await self.get_user_assignment(user_id)
        if existing is not None:
            if existing.sni != sni and not replace:
                logger.info(
                    "[M-042][save_assignment][WRITE_ASSIGNMENT] "
                    f"user_id={user_id} assignment_id={existing.id} reused=true"
                )
                return existing
            existing.sni = sni
            existing.credential_mode = credential_mode
            existing.status = status
            existing.rotation_marker = rotation_marker
            existing.issued_at = now
            existing.updated_at = now
            existing.superseded_at = None
            await self.session.flush()
            await self.session.refresh(existing)
            logger.info(
                "[M-042][save_assignment][WRITE_ASSIGNMENT] "
                f"user_id={user_id} assignment_id={existing.id} reused=false"
            )
            return existing

        assignment = MTProtoAssignment(
            user_id=user_id,
            sni=sni,
            credential_mode=credential_mode,
            status=status,
            rotation_marker=rotation_marker,
            issued_at=now,
            created_at=now,
            updated_at=now,
        )
        self.session.add(assignment)
        await self.session.flush()
        await self.session.refresh(assignment)
        logger.info(
            "[M-042][save_assignment][WRITE_ASSIGNMENT] "
            f"user_id={user_id} assignment_id={assignment.id} reused=false"
        )
        return assignment
    # END_BLOCK_WRITE_ASSIGNMENT

    # START_CONTRACT: list_assignments
    #   PURPOSE: Return admin-safe assignment rows without secrets or tg links
    #   INPUTS: offset: int; limit: int
    #   OUTPUTS: list[MTProtoAssignment]
    #   SIDE_EFFECTS: database read and redaction log marker
    #   LINKS: M-042, V-M-042
    # END_CONTRACT: list_assignments
    # START_BLOCK_REDACT_ADMIN_LIST
    async def list_assignments(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[MTProtoAssignment]:
        """Return assignment rows; raw secrets and tg links are not persisted here."""
        safe_limit = min(max(limit, 1), 500)
        logger.info(
            "[M-042][list_assignments][REDACT_ADMIN_LIST] "
            f"offset={offset} limit={safe_limit}"
        )
        result = await self.session.execute(
            select(MTProtoAssignment)
            .order_by(MTProtoAssignment.id.desc())
            .offset(max(offset, 0))
            .limit(safe_limit)
        )
        return list(result.scalars().all())
    # END_BLOCK_REDACT_ADMIN_LIST
