"""
User models for authentication and profile management.

# FILE: backend/app/users/models.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: User, auth and profile database models
#   SCOPE: User model with roles, Telegram linkage, email/password fields; UserProfile and UserStats response models
#   DEPENDS: M-001 (core database, SQLModel), SQLAlchemy Column types
#   LINKS: M-002 (users), M-004 (billing.Subscription), M-005 (vpn.VPNClient), M-006 (referrals)
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   UserRole - Enum for user roles (USER, ADMIN, SUPERADMIN)
#   User - Main user table model with auth, Telegram, profile, referral, and relationship fields
#   UserProfile - User profile data for responses (non-table SQLModel)
#   UserStats - User statistics for dashboard (non-table SQLModel)
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: 2026-04-06 - Added full GRACE MODULE_CONTRACT, MODULE_MAP, BLOCK markers per GRACE governance protocol
# END_CHANGE_SUMMARY
"""
# <!-- GRACE: module="M-002" entity="User" -->

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime
from enum import Enum
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.billing.models import Subscription
    from app.devices.models import UserDevice
    from app.referrals.models import Referral, ReferralCode
    from app.vpn.models import VPNClient


# START_BLOCK_USERROLE
class UserRole(str, Enum):
    """User roles for authorization."""
    USER = "user"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"
# END_BLOCK_USERROLE


# START_BLOCK_USER
class User(SQLModel, table=True):
    """User account model."""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    email: str | None = Field(default=None, unique=True, index=True, max_length=255)
    email_verified: bool = Field(default=False)
    password_hash: str | None = Field(default=None, max_length=255)

    # Telegram auth
    telegram_id: int | None = Field(default=None, unique=True, index=True)
    telegram_username: str | None = Field(default=None, max_length=100)

    # Profile
    name: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)
    language: str = Field(default="ru", max_length=5)  # ru, en

    # Role and status
    role: UserRole = Field(default=UserRole.USER)
    is_active: bool = Field(default=True)

    # Referral tracking
    referred_by_id: int | None = Field(default=None, foreign_key="users.id")

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    last_login_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))

    # Relationships
    vpn_clients: list["VPNClient"] = Relationship(back_populates="user")
    devices: list["UserDevice"] = Relationship(back_populates="user")
    subscriptions: list["Subscription"] = Relationship(back_populates="user")
    referral_code: "ReferralCode" = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"uselist": False},
    )
    referrals_made: list["Referral"] = Relationship(
        back_populates="referrer",
        sa_relationship_kwargs={"foreign_keys": "[Referral.referrer_id]"},
    )
    referral_received: "Referral" = Relationship(
        back_populates="referred",
        sa_relationship_kwargs={
            "foreign_keys": "[Referral.referred_id]",
            "uselist": False,
        },
    )

    @property
    def display_name(self) -> str:
        """Get user's display name."""
        if self.name:
            return self.name
        if self.telegram_username:
            return f"@{self.telegram_username}"
        if self.email:
            return self.email.split("@")[0]
        return f"User {self.id}"

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self.role in (UserRole.ADMIN, UserRole.SUPERADMIN)
# END_BLOCK_USER


# START_BLOCK_USERPROFILE
class UserProfile(SQLModel):
    """User profile data for responses."""
    id: int
    email: str | None
    email_verified: bool
    name: str | None
    avatar_url: str | None
    language: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None
# END_BLOCK_USERPROFILE


# START_BLOCK_USERSTATS
class UserStats(SQLModel):
    """User statistics for dashboard."""
    total_upload_bytes: int = 0
    total_download_bytes: int = 0
    total_sessions: int = 0
    subscription_days_left: int = 0
    has_active_subscription: bool = False
    referrals_count: int = 0
    referral_bonus_days: int = 0
# END_BLOCK_USERSTATS
