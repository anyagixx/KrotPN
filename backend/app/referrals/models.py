"""
Referral models for referral program.
"""
# <!-- GRACE: module="M-005" entity="ReferralCode, Referral" -->

from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.users.models import User


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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: "User" = Relationship(back_populates="referral_code")


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
    first_payment_at: datetime | None = Field(default=None)
    first_payment_amount: float | None = Field(default=None)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    referrer: "User" = Relationship(
        back_populates="referrals_made",
        sa_relationship_kwargs={"foreign_keys": "[Referral.referrer_id]"},
    )
    referred: "User" = Relationship(
        back_populates="referral_received",
        sa_relationship_kwargs={"foreign_keys": "[Referral.referred_id]"},
    )


class ReferralStats(SQLModel):
    """Referral statistics."""
    code: str
    link: str
    total_referrals: int
    paid_referrals: int
    bonus_days_earned: int
    bonus_days_available: int
