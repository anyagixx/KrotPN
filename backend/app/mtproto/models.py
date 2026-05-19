"""MTProto assignment persistence models.

# FILE: backend/app/mtproto/models.py
# VERSION: 1.2.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Persist restore-safe personal Telegram MTProto proxy assignments
#   SCOPE: Assignment table, credential mode, lifecycle status,
#          SNI uniqueness, and rotation metadata
#   DEPENDS: M-001 (core database), M-002 (users)
#   LINKS: M-042, V-M-042
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MTProtoCredentialMode - Stored credential derivation mode
#   MTProtoAssignmentStatus - Assignment lifecycle state
#   MTProtoAssignment - User-linked assignment row without raw secrets or tg://proxy links
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.2.0 - Restored derived-per-SNI as the default production credential mode.
#   LAST_CHANGE: v1.1.0 - Added Phase-40 official MTProxy secure credential mode.
#   LAST_CHANGE: v1.0.0 - Added Phase-29 MTProto assignment model
# END_CHANGE_SUMMARY
"""

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


# START_BLOCK_MTPROTO_ASSIGNMENT_TYPES
class MTProtoCredentialMode(str, Enum):
    """Supported MTProto credential derivation modes."""

    DERIVED_PER_SNI = "derived_per_sni"
    OFFICIAL_SECURE = "official_secure"


class MTProtoAssignmentStatus(str, Enum):
    """Lifecycle state for a personal MTProto assignment."""

    ACTIVE = "active"
    REISSUE_REQUIRED = "reissue_required"
    SUPERSEDED = "superseded"
    DISABLED = "disabled"
# END_BLOCK_MTPROTO_ASSIGNMENT_TYPES


# START_BLOCK_MTPROTO_ASSIGNMENT
class MTProtoAssignment(SQLModel, table=True):
    """Restore-safe assignment record for one user's personal MTProto proxy."""

    __tablename__ = "mtproto_assignments"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    sni: str = Field(unique=True, index=True, max_length=255)
    credential_mode: MTProtoCredentialMode = Field(
        default=MTProtoCredentialMode.DERIVED_PER_SNI,
        max_length=50,
    )
    status: MTProtoAssignmentStatus = Field(
        default=MTProtoAssignmentStatus.ACTIVE,
        index=True,
        max_length=50,
    )
    rotation_marker: str = Field(default="v1", max_length=64)
    issued_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    superseded_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
# END_BLOCK_MTPROTO_ASSIGNMENT
