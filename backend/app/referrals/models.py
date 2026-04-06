# FILE: backend/app/referrals/models.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Referral program models — codes, relationships, and statistics
#   SCOPE: ReferralCode (per-user code with stats), Referral (referrer-referred linkage with bonus tracking), ReferralStats (response model)
#   DEPENDS: M-001 (core database), M-002 (users identities)
#   LINKS: M-005 (referral-program), V-M-005
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   ReferralCode - User's referral code with uses_count and bonus_earned_days tracking
#   Referral - Referral relationship with bonus_given, first_payment tracking
#   ReferralStats - Response model for aggregated referral statistics
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""
Referral models for referral program.

MODULE_CONTRACT
- PURPOSE: Persist referral program data — codes, referral relationships, and statistics.
- SCOPE: ReferralCode (per-user code with stats), Referral (referrer-referred linkage with bonus tracking), ReferralStats (response model for stats).
- DEPENDS: M-001 database metadata, M-002 user identities (User relationship).
- LINKS: M-005 referral-program, V-M-005.

MODULE_MAP
- ReferralCode: User's referral code with uses_count and bonus_earned_days tracking.
- Referral: Referral relationship with bonus_given, first_payment tracking.
- ReferralStats: Response model for aggregated referral statistics.

CHANGE_SUMMARY
- v2.8.0: Added GRACE-lite runtime markup with START_BLOCK/END_BLOCK for each model class.
"""
# <!-- GRACE: module="M-005" entity="ReferralCode, Referral, ReferralStats" role="RUNTIME" MAP_MODE="EXPORTS" -->

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.users.models import User


# <!-- START_BLOCK: ReferralCode -->
class ReferralCode(SQLModel, table=True):
    """User's referral code."""

    __tablename__ = "referral_codes"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    code: str = Field(max_length=20, unique=True, index=True)

    # Stats
    uses_count: int = Field(default=0)
    bonus_earned_days: int = Field(default=0)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))

    # Relationships
    user: "User" = Relationship(back_populates="referral_code")
# <!-- END_BLOCK: ReferralCode -->


# <!-- START_BLOCK: Referral -->
class Referral(SQLModel, table=True):
    """Referral relationship record."""

    __tablename__ = "referrals"

    id: int | None = Field(default=None, primary_key=True)

    # Referrer (who invited)
    referrer_id: int = Field(foreign_key="users.id", index=True)

    # Referred (who was invited)
    referred_id: int = Field(foreign_key="users.id", unique=True, index=True)

    # Bonus tracking
    bonus_given: bool = Field(default=False)
    bonus_days: int = Field(default=0)

    # Payment tracking for bonus
    first_payment_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    first_payment_amount: float | None = Field(default=None)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))

    # Relationships
    referrer: "User" = Relationship(
        back_populates="referrals_made",
        sa_relationship_kwargs={"foreign_keys": "[Referral.referrer_id]"},
    )
    referred: "User" = Relationship(
        back_populates="referral_received",
        sa_relationship_kwargs={"foreign_keys": "[Referral.referred_id]"},
    )
# <!-- END_BLOCK: Referral -->


# <!-- START_BLOCK: ReferralStats -->
class ReferralStats(SQLModel):
    """Referral statistics."""
    code: str
    link: str
    total_referrals: int
    paid_referrals: int
    bonus_days_earned: int
    bonus_days_available: int
# <!-- END_BLOCK: ReferralStats -->
