"""
User schemas for API requests and responses.

# FILE: backend/app/users/schemas.py
# VERSION: 1.0.0
# ROLE: TYPES
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: Define request and response payloads for user auth, profile, admin, and stats APIs
#   SCOPE: API-layer validation only; business rules remain in UserService and routers
#   DEPENDS: M-002 (users models - UserRole), Pydantic, SQLModel
#   LINKS: M-002 (users), M-001 (backend-core)
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   UserBase - Base user fields for inheritance
#   UserCreate - Email/password registration schema with referral_code
#   UserCreateTelegram - Telegram OAuth registration schema
#   UserUpdate - Profile update schema
#   UserChangePassword - Password change request
#   UserLogin - Email/password login request
#   PasswordResetRequest, PasswordResetConfirm, PasswordResetResponse - Password recovery payloads
#   PendingRegistrationResponse - Safe check-email response for verified registration
#   EmailVerificationRequest - One-time email verification token request
#   Token - JWT token response
#   TokenRefresh - Token refresh request
#   UserResponse - User data in responses with from_user factory
#   UserWithStats - User with nested statistics
#   UserStatsResponse - User statistics fields
#   UserListResponse - Paginated admin user list
#   UserAdminUpdate - Admin user mutation schema
#   UserAdminResponse - Extended user info for admin panel
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: 2026-06-01 - Added Phase-44 strong-password and password recovery schemas
#   LAST_CHANGE: 2026-05-13 - Added Phase-28 pending registration and verify-email schemas
#   LAST_CHANGE: 2026-04-06 - Added full GRACE MODULE_CONTRACT, MODULE_MAP, BLOCK markers per GRACE governance protocol
# END_CHANGE_SUMMARY
"""
# <!-- GRACE: module="M-002" contract="user-schemas" -->

from datetime import datetime

from pydantic import EmailStr, Field, field_validator
from sqlmodel import SQLModel

from app.users.models import UserRole
from app.users.password_policy import validate_password_strength


# Base schemas
class UserBase(SQLModel):
    """Base user schema."""
    email: EmailStr | None = None
    name: str | None = Field(default=None, max_length=100)
    language: str = Field(default="ru", max_length=5)


# START_BLOCK_USERCREATE
class UserCreate(UserBase):
    """Schema for user registration."""
    password: str = Field(..., min_length=10, max_length=100)
    referral_code: str | None = Field(default=None, max_length=20)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)
# END_BLOCK_USERCREATE


# START_BLOCK_USERCREATETELEGRAM
class UserCreateTelegram(SQLModel):
    """Schema for Telegram OAuth registration."""
    telegram_id: int
    telegram_username: str | None = None
    name: str | None = None
    auth_date: int | None = None
    auth_hash: str | None = Field(default=None, alias="hash")
    referral_code: str | None = None

    model_config = {
        "populate_by_name": True,
    }
# END_BLOCK_USERCREATETELEGRAM


class UserUpdate(SQLModel):
    """Schema for updating user profile."""
    name: str | None = Field(default=None, max_length=100)
    language: str | None = Field(default=None, max_length=5)
    avatar_url: str | None = Field(default=None, max_length=500)


class UserChangePassword(SQLModel):
    """Schema for password change."""
    current_password: str
    new_password: str = Field(..., min_length=10, max_length=100)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


class UserLogin(SQLModel):
    """Schema for user login."""
    email: EmailStr
    password: str


# START_BLOCK_PASSWORD_RESET_SCHEMAS
class PasswordResetRequest(SQLModel):
    """Schema for requesting a password reset email."""
    email: EmailStr


class PasswordResetConfirm(SQLModel):
    """Schema for consuming a one-time password reset token."""
    token: str = Field(..., min_length=16, max_length=512)
    new_password: str = Field(..., min_length=10, max_length=100)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


class PasswordResetResponse(SQLModel):
    """Safe password reset response."""
    status: str
    message: str
# END_BLOCK_PASSWORD_RESET_SCHEMAS


# START_BLOCK_VERIFIED_REGISTRATION_SCHEMAS
class PendingRegistrationResponse(SQLModel):
    """Safe response returned after registration email is queued."""
    email: EmailStr
    status: str
    expires_at: datetime
    delivery_status: str
    message: str = "verification_email_sent"


class EmailVerificationRequest(SQLModel):
    """Schema for consuming a one-time email verification token."""
    token: str = Field(..., min_length=16, max_length=512)
# END_BLOCK_VERIFIED_REGISTRATION_SCHEMAS


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
# START_BLOCK_USERRESPONSE
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

    @classmethod
    def from_user(cls, user: "User") -> "UserResponse":
        from app.users.models import User
        return cls(
            id=user.id, email=user.email, email_verified=user.email_verified,
            telegram_id=user.telegram_id, telegram_username=user.telegram_username,
            name=user.name, display_name=user.display_name, avatar_url=user.avatar_url,
            language=user.language, role=user.role, is_active=user.is_active,
            created_at=user.created_at, last_login_at=user.last_login_at,
        )
# END_BLOCK_USERRESPONSE


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


# START_BLOCK_USERLISTRESPONSE
class UserListResponse(SQLModel):
    """Paginated user list for admin."""
    items: list[UserResponse]
    total: int
    page: int
    per_page: int
    pages: int
# END_BLOCK_USERLISTRESPONSE


# Admin schemas
# START_BLOCK_USERADMINUPDATE
class UserAdminUpdate(SQLModel):
    """Schema for admin to update user."""
    name: str | None = None
    email: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    language: str | None = None
# END_BLOCK_USERADMINUPDATE


# START_BLOCK_USERADMINRESPONSE
class UserAdminResponse(UserResponse):
    """Extended user info for admin."""
    referred_by_id: int | None
    subscription_count: int = 0
    active_subscription_id: int | None = None
# END_BLOCK_USERADMINRESPONSE

# Update forward references
UserWithStats.model_rebuild()
