"""
Billing schemas for API requests and responses.
"""
# <!-- GRACE: module="M-004" contract="billing-schemas" -->

from datetime import datetime

from pydantic import Field

from sqlmodel import SQLModel
from app.billing.models import PaymentProvider, PaymentStatus, SubscriptionStatus


class PlanCreate(SQLModel):
    """Schema for creating a plan."""
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    price: float = Field(..., ge=0)
    currency: str = Field(default="RUB", max_length=3)
    duration_days: int = Field(..., ge=1)
    features: list[str] = Field(default=[])
    is_popular: bool = False
    sort_order: int = 0


class PlanUpdate(SQLModel):
    """Schema for updating a plan."""
    name: str | None = None
    description: str | None = None
    price: float | None = None
    duration_days: int | None = None
    features: list[str] | None = None
    is_active: bool | None = None
    is_popular: bool | None = None
    sort_order: int | None = None


class SubscribeRequest(SQLModel):
    """Request to create a subscription."""
    plan_id: int
    provider: PaymentProvider = Field(default=PaymentProvider.YOOKASSA)


class SubscriptionStatusResponse(SQLModel):
    """Subscription status response."""
    has_subscription: bool
    is_active: bool
    is_trial: bool
    plan_name: str | None
    days_left: int
    expires_at: datetime | None
    is_recurring: bool


class PaymentCreateRequest(SQLModel):
    """Request to create a payment."""
    plan_id: int
    return_url: str | None = None


class PaymentWebhookYooKassa(SQLModel):
    """YooKassa webhook payload."""
    type: str
    event: str
    object: dict


class PaymentHistoryResponse(SQLModel):
    """Payment history response."""
    items: list
    total: int


class AdminSubscriptionUpdate(SQLModel):
    """Admin update for subscription."""
    status: SubscriptionStatus | None = None
    is_active: bool | None = None
    expires_at: datetime | None = None
    is_recurring: bool | None = None
