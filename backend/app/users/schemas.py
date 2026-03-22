"""
User schemas for API requests and responses.
"""
# <!-- GRACE: module="M-002" contract="user-schemas" -->

from datetime import datetime

from pydantic import EmailStr, Field, field_validator
from sqlmodel import SQLModel

from app.users.models import UserRole


# Base schemas
class UserBase(SQLModel):
    """Base user schema."""
    email: EmailStr | None = None
    name: str | None = Field(default=None, max_length=100)
    language: str = Field(default="ru", max_length=5)


class UserCreate(UserBase):
    """Schema for user registration."""
    password: str = Field(..., min_length=8, max_length=100)
    referral_code: str | None = Field(default=None, max_length=20)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserCreateTelegram(SQLModel):
    """Schema for Telegram OAuth registration."""
    telegram_id: int
    telegram_username: str | None = None
    name: str | None = None
    referral_code: str | None = None


class UserUpdate(SQLModel):
    """Schema for updating user profile."""
    name: str | None = Field(default=None, max_length=100)
    language: str | None = Field(default=None, max_length=5)
    avatar_url: str | None = Field(default=None, max_length=500)


class UserChangePassword(SQLModel):
    """Schema for password change."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)


class UserLogin(SQLModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class Token(SQLModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenRefresh(SQLModel):
    """Schema for token refresh."""
    refresh_token: str


# Response schemas
class UserResponse(SQLModel):
    """User data in responses."""
    id: int
    email: str | None
    email_verified: bool
    telegram_id: int | None
    telegram_username: str | None
    name: str | None
    display_name: str
    avatar_url: str | None
    language: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None

    model_config = {"from_attributes": True}


class UserWithStats(UserResponse):
    """User with statistics."""
    stats: "UserStatsResponse"


class UserStatsResponse(SQLModel):
    """User statistics response."""
    total_upload_bytes: int = 0
    total_download_bytes: int = 0
    subscription_days_left: int = 0
    has_active_subscription: bool = False
    referrals_count: int = 0
    referral_bonus_days: int = 0


class UserListResponse(SQLModel):
    """Paginated user list for admin."""
    items: list[UserResponse]
    total: int
    page: int
    per_page: int
    pages: int


# Admin schemas
class UserAdminUpdate(SQLModel):
    """Schema for admin to update user."""
    name: str | None = None
    email: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    language: str | None = None


class UserAdminResponse(UserResponse):
    """Extended user info for admin."""
    referred_by_id: int | None
    subscription_count: int = 0
    active_subscription_id: int | None = None

# Update forward references
UserWithStats.model_rebuild()
