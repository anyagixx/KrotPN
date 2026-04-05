"""
User models for authentication and profile management.
"""
# <!-- GRACE: module="M-002" entity="User" -->

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.billing.models import Subscription
    from app.devices.models import UserDevice
    from app.referrals.models import Referral, ReferralCode
    from app.vpn.models import VPNClient


class UserRole(str, Enum):
    """User roles for authorization."""
    USER = "user"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


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
    last_login_at: datetime | None = Field(default=None)
    
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


class UserStats(SQLModel):
    """User statistics for dashboard."""
    total_upload_bytes: int = 0
    total_download_bytes: int = 0
    total_sessions: int = 0
    subscription_days_left: int = 0
    has_active_subscription: bool = False
    referrals_count: int = 0
    referral_bonus_days: int = 0
