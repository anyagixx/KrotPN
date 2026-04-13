"""
User service for business logic.

# FILE: backend/app/users/service.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: User creation, authentication, Telegram identity linkage, profile mutation, and stats
#   SCOPE: All business logic for user lifecycle: registration, auth, password management, role updates, stats aggregation
#   DEPENDS: M-001 (core config, security), M-002 (users models/schemas), SQLAlchemy AsyncSession
#   LINKS: M-002 (users), M-004 (billing.Subscription), M-005 (vpn.VPNClient), M-006 (referrals)
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   UserService - Main service class for all user operations
#     get_by_id, get_by_email, get_by_telegram_id - identity lookups
#     build_internal_user_email, resolve_internal_user - internal user helpers
#     create_user, create_user_telegram - registration
#     authenticate_email - credential verification
#     update_user, change_password, set_password - profile mutations
#     verify_email, deactivate_user, activate_user, update_role - admin ops
#     get_user_stats - dashboard statistics aggregation
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: 2026-04-06 - Added full GRACE MODULE_CONTRACT, MODULE_MAP, BLOCK markers per GRACE governance protocol
#   PREVIOUS: 2026-03-26 - Added internal-user resolution helpers for manual non-billable client issuance
# END_CHANGE_SUMMARY

GRACE-lite module contract:
- Owns user creation, authentication, Telegram identity linkage and profile mutation.
- `email` and `telegram_id` are identity keys; duplicate creation must remain impossible.
- Registration side effects such as trial creation and VPN provisioning are orchestrated by router-level flows.
- Changes here affect every auth path in user frontend, admin frontend and Telegram bot.

CHANGE_SUMMARY
- 2026-03-26: Added internal-user resolution helpers for manual non-billable client issuance.
"""
# <!-- GRACE: module="M-002" contract="user-service" -->

from datetime import datetime, timezone, timezone
import re
from typing import Any

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.users.models import User, UserRole
from app.users.schemas import UserCreate, UserCreateTelegram, UserUpdate


# START_BLOCK_USERSERVICE
class UserService:
    """Service for user operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        """Get user by ID."""
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        result = await self.session.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    def build_internal_user_email(self, identity: str) -> str:
        """Build a deterministic local-only email for internal manual users."""
        normalized = re.sub(r"[^a-z0-9]+", "-", identity.strip().lower()).strip("-")
        if not normalized:
            raise ValueError("Internal identity cannot be empty")
        return f"internal+{normalized}@local.krotpn"

    # START_BLOCK_RESOLVE_INTERNAL_USER
    async def resolve_internal_user(
        self,
        identity: str,
        *,
        display_name: str | None = None,
    ) -> User:
        """Find or create the canonical user row for a manual internal client."""
        email = self.build_internal_user_email(identity)
        existing = await self.get_by_email(email)
        if existing is not None:
            if display_name and not existing.name:
                existing.name = display_name
                existing.updated_at = datetime.now(timezone.utc)
                await self.session.flush()
                await self.session.refresh(existing)
            logger.info(
                "[VPN][manual][VPN_INTERNAL_USER_RESOLVED] "
                f"internal_identity={identity} user_id={existing.id} reused=true"
            )
            return existing

        now = datetime.now(timezone.utc)
        user = User(
            email=email,
            email_verified=True,
            password_hash=None,
            name=display_name or identity,
            language="ru",
            role=UserRole.USER,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        logger.info(
            "[VPN][manual][VPN_INTERNAL_USER_RESOLVED] "
            f"internal_identity={identity} user_id={user.id} reused=false"
        )
        return user
    # END_BLOCK_RESOLVE_INTERNAL_USER

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Get user by Telegram ID."""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    # START_BLOCK_CREATE_USER
    async def create_user(
        self,
        data: UserCreate,
        referral_code: str | None = None,
    ) -> User:
        """
        Create a new user with email/password.

        Args:
            data: User creation data
            referral_code: Optional referral code for bonus

        Returns:
            Created user
        """
        # Identity creation must stay deterministic: uniqueness checks first,
        # then user row creation, then downstream side effects outside this method.
        # Check if email already exists
        if data.email:
            existing = await self.get_by_email(data.email)
            if existing:
                raise ValueError("User with this email already exists")

        # Create user
        user = User(
            email=data.email.lower() if data.email else None,
            password_hash=hash_password(data.password) if data.password else None,
            name=data.name,
            language=data.language,
            role=UserRole.USER,
        )

        # Handle referral
        if referral_code:
            referrer = await self._get_user_by_referral_code(referral_code)
            if referrer:
                user.referred_by_id = referrer.id

        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)

        return user
    # END_BLOCK_CREATE_USER

    # START_BLOCK_CREATE_USER_TELEGRAM
    async def create_user_telegram(
        self,
        data: UserCreateTelegram,
        referral_code: str | None = None,
    ) -> User:
        """
        Create a new user via Telegram OAuth.

        Args:
            data: Telegram user data
            referral_code: Optional referral code

        Returns:
            Created user
        """
        # Check if telegram_id already exists
        existing = await self.get_by_telegram_id(data.telegram_id)
        if existing:
            # Update existing user
            if data.telegram_username:
                existing.telegram_username = data.telegram_username
            if data.name:
                existing.name = data.name
            existing.last_login_at = datetime.now(timezone.utc)
            await self.session.flush()
            return existing

        # Create new user
        user = User(
            telegram_id=data.telegram_id,
            telegram_username=data.telegram_username,
            name=data.name or data.telegram_username,
            language="ru",  # Default for Telegram users
            role=UserRole.USER,
        )

        # Handle referral
        if referral_code:
            referrer = await self._get_user_by_referral_code(referral_code)
            if referrer:
                user.referred_by_id = referrer.id

        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)

        return user
    # END_BLOCK_CREATE_USER_TELEGRAM

    # START_BLOCK_AUTHENTICATE_EMAIL
    async def authenticate_email(self, email: str, password: str) -> User | None:
        """
        Authenticate user with email and password.

        Returns user if credentials are valid, None otherwise.
        """
        user = await self.get_by_email(email)
        if user is None or user.password_hash is None:
            return None

        if not verify_password(password, user.password_hash):
            return None

        # Update last login
        user.last_login_at = datetime.now(timezone.utc)
        await self.session.flush()

        return user
    # END_BLOCK_AUTHENTICATE_EMAIL

    async def update_user(self, user: User, data: UserUpdate) -> User:
        """Update user profile."""
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        user.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    # START_BLOCK_CHANGE_PASSWORD
    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> bool:
        """
        Change user password.

        Returns True if successful, False if current password is wrong.
        """
        if user.password_hash is None:
            # User registered via Telegram, set password
            user.password_hash = hash_password(new_password)
            await self.session.flush()
            return True

        if not verify_password(current_password, user.password_hash):
            return False

        user.password_hash = hash_password(new_password)
        await self.session.flush()
        return True
    # END_BLOCK_CHANGE_PASSWORD

    async def set_password(self, user: User, password: str) -> None:
        """Set password for user (for password reset)."""
        user.password_hash = hash_password(password)
        await self.session.flush()

    async def verify_email(self, user: User) -> None:
        """Mark user email as verified."""
        user.email_verified = True
        await self.session.flush()

    async def deactivate_user(self, user: User) -> None:
        """Deactivate user account."""
        user.is_active = False
        await self.session.flush()

    async def activate_user(self, user: User) -> None:
        """Activate user account."""
        user.is_active = True
        await self.session.flush()

    async def update_role(self, user: User, role: UserRole) -> None:
        """Update user role."""
        user.role = role
        await self.session.flush()

    # START_BLOCK_GET_USER_BY_REFERRAL_CODE
    async def _get_user_by_referral_code(self, code: str) -> User | None:
        """Get user by referral code."""
        from app.referrals.models import ReferralCode

        result = await self.session.execute(
            select(User)
            .join(ReferralCode)
            .where(ReferralCode.code == code)
            .options(selectinload(User.referral_code))
        )
        return result.scalar_one_or_none()
    # END_BLOCK_GET_USER_BY_REFERRAL_CODE

    # START_BLOCK_GET_USER_STATS
    async def get_user_stats(self, user: User) -> dict[str, Any]:
        """Get user statistics."""
        from app.billing.models import Subscription
        from app.referrals.models import Referral
        from app.vpn.models import VPNClient

        # Get active subscription
        now = datetime.now(timezone.utc)
        active_sub_result = await self.session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user.id,
                Subscription.is_active == True,
                Subscription.expires_at > now,
            )
            .order_by(Subscription.expires_at.desc())
        )
        active_sub = active_sub_result.scalar_one_or_none()

        # Get total traffic
        traffic_result = await self.session.execute(
            select(
                func.sum(VPNClient.total_upload_bytes).label("upload"),
                func.sum(VPNClient.total_download_bytes).label("download"),
            ).where(VPNClient.user_id == user.id)
        )
        traffic = traffic_result.one()

        # Get referral stats
        referral_result = await self.session.execute(
            select(func.count(Referral.id)).where(
                Referral.referrer_id == user.id,
                Referral.bonus_given == True,
            )
        )
        referrals_count = referral_result.scalar() or 0

        # Calculate bonus days
        bonus_days = referrals_count * settings.referral_bonus_days

        return {
            "total_upload_bytes": traffic.upload or 0,
            "total_download_bytes": traffic.download or 0,
            "subscription_days_left": (
                (active_sub.expires_at - now).days if active_sub else 0
            ),
            "has_active_subscription": active_sub is not None,
            "referrals_count": referrals_count,
            "referral_bonus_days": bonus_days,
        }
    # END_BLOCK_GET_USER_STATS
# END_BLOCK_USERSERVICE
