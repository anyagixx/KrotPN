# FILE: backend/app/billing/models.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Define database models for billing plans, subscriptions, payments, and response schemas.
#   SCOPE: SQLAlchemy/SQLModel table definitions, enum types, and API response shapes.
#   DEPENDS: M-001 (core), M-002 (users)
#   LINKS: M-004 (billing)
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   PaymentProvider, PaymentStatus, SubscriptionStatus - Enum types for billing state
#   Plan - Subscription plan table with pricing, duration, device_limit
#   Subscription - User subscription table with lifecycle fields
#   Payment - Payment record table with provider integration
#   PlanResponse, SubscriptionResponse, PaymentResponse - API response schemas
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT, MODULE_MAP, and BLOCKS per GRACE governance protocol
#   v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""
Billing models for subscriptions and payments.

CHANGE_SUMMARY
- 2026-03-26: Added explicit complimentary-access fields so internal non-billable clients can stay inside normal subscription state.
- 2026-03-27: Added per-plan device limits for device-bound access control and anti-sharing enforcement.
"""
# <!-- GRACE: module="M-004" entity="Plan, Subscription, Payment" -->

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime
from enum import Enum
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.users.models import User


# START_BLOCK: PaymentProvider enum
class PaymentProvider(str, Enum):
    """Payment provider options."""
    YOOKASSA = "yookassa"
    TINKOFF = "tinkoff"
    MANUAL = "manual"
# END_BLOCK


# START_BLOCK: PaymentStatus enum
class PaymentStatus(str, Enum):
    """Payment status."""
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    REFUNDED = "refunded"
# END_BLOCK


# START_BLOCK: SubscriptionStatus enum
class SubscriptionStatus(str, Enum):
    """Subscription status."""
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELED = "canceled"
# END_BLOCK


# START_BLOCK: Plan table model
class Plan(SQLModel, table=True):
    """Subscription plan."""

    __tablename__ = "plans"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=500)

    # Pricing
    price: float = Field(ge=0)
    currency: str = Field(default="RUB", max_length=3)

    # Duration
    duration_days: int = Field(ge=1, default=30)
    device_limit: int = Field(ge=1, default=1)

    # Features (JSON string)
    features: str | None = Field(default=None)

    # Status
    is_active: bool = Field(default=True)
    is_popular: bool = Field(default=False)
    sort_order: int = Field(default=0)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))

    # Relationships
    subscriptions: list["Subscription"] = Relationship(back_populates="plan")
# END_BLOCK


# START_BLOCK: Subscription table model
class Subscription(SQLModel, table=True):
    """User subscription."""

    __tablename__ = "subscriptions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    plan_id: int | None = Field(default=None, foreign_key="plans.id")

    # Status
    status: SubscriptionStatus = Field(default=SubscriptionStatus.ACTIVE)
    is_active: bool = Field(default=True)

    # Timing
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))

    # Trial
    is_trial: bool = Field(default=False)
    is_complimentary: bool = Field(default=False)
    access_label: str | None = Field(default=None, max_length=100)

    # Recurring
    is_recurring: bool = Field(default=False)
    recurring_payment_id: str | None = Field(default=None, max_length=100)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))

    # Relationships
    user: "User" = Relationship(back_populates="subscriptions")
    plan: Plan | None = Relationship(back_populates="subscriptions")
    payments: list["Payment"] = Relationship(back_populates="subscription")
# END_BLOCK


# START_BLOCK: Payment table model
class Payment(SQLModel, table=True):
    """Payment record."""

    __tablename__ = "payments"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    plan_id: int | None = Field(default=None, foreign_key="plans.id")
    subscription_id: int | None = Field(default=None, foreign_key="subscriptions.id")

    # Amount
    amount: float = Field(ge=0)
    currency: str = Field(default="RUB", max_length=3)

    # Provider
    provider: PaymentProvider = Field(default=PaymentProvider.YOOKASSA)
    status: PaymentStatus = Field(default=PaymentStatus.PENDING)

    # External reference
    external_id: str | None = Field(default=None, max_length=100, index=True)
    payment_url: str | None = Field(default=None, max_length=500)

    # Metadata
    description: str | None = Field(default=None, max_length=255)
    payment_metadata: str | None = Field(default=None)  # JSON

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    paid_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))

    # Relationships
    subscription: Subscription | None = Relationship(back_populates="payments")
# END_BLOCK


# START_BLOCK: PlanResponse schema
class PlanResponse(SQLModel):
    """Plan response for API."""
    id: int
    name: str
    description: str | None
    price: float
    currency: str
    duration_days: int
    device_limit: int
    features: list[str]
    is_popular: bool

    model_config = {"from_attributes": True}
# END_BLOCK


# START_BLOCK: SubscriptionResponse schema
class SubscriptionResponse(SQLModel):
    """Subscription response for API."""
    id: int
    plan_id: int
    plan_name: str
    status: SubscriptionStatus
    is_active: bool
    started_at: datetime
    expires_at: datetime
    days_left: int
    is_trial: bool
    is_complimentary: bool = False
    is_recurring: bool

    model_config = {"from_attributes": True}
# END_BLOCK


# START_BLOCK: PaymentResponse schema
class PaymentResponse(SQLModel):
    """Payment response for API."""
    id: int
    amount: float
    currency: str
    provider: PaymentProvider
    status: PaymentStatus
    payment_url: str | None
    created_at: datetime
    paid_at: datetime | None

    model_config = {"from_attributes": True}
# END_BLOCK
