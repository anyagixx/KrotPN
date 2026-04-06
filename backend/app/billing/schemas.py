# FILE: backend/app/billing/schemas.py
# VERSION: 1.0.0
# ROLE: TYPES
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Define request and response payloads for billing plan, subscription, payment and admin mutation APIs.
#   SCOPE: API-layer validation only; business rules and side effects remain in BillingService and routers.
#   DEPENDS: M-001, M-004 (billing models enums)
#   LINKS: M-004 (billing)
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   PlanCreate - Validates admin plan creation payloads, including device_limit
#   PlanUpdate - Validates partial admin plan updates, including device_limit changes
#   SubscribeRequest - Validates user plan purchase intent and payment provider choice
#   SubscriptionStatusResponse - Returns compact subscription-state payload
#   PaymentCreateRequest - Validates explicit payment creation requests
#   PaymentWebhookYooKassa - Documents YooKassa webhook payload shape
#   PaymentHistoryResponse - Returns paged payment-history payload
#   AdminSubscriptionUpdate - Validates admin-side subscription mutations
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT, MODULE_MAP, and BLOCKS per GRACE governance protocol
#   v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""
Billing schemas for API requests and responses.

MODULE_CONTRACT
- PURPOSE: Define request and response payloads for billing plan, subscription, payment and admin mutation APIs.
- SCOPE: API-layer validation only; business rules and side effects remain in BillingService and routers.
- DEPENDS: M-004 billing models enums and shared SQLModel validation layer.
- LINKS: V-M-004, V-M-021.

MODULE_MAP
- PlanCreate: Validates admin plan creation payloads, including device_limit.
- PlanUpdate: Validates partial admin plan updates, including device_limit changes.
- SubscribeRequest: Validates user plan purchase intent and payment provider choice.
- SubscriptionStatusResponse: Returns compact subscription-state payload.
- PaymentCreateRequest: Validates explicit payment creation requests.
- PaymentWebhookYooKassa: Documents YooKassa webhook payload shape.
- PaymentHistoryResponse: Returns paged payment-history payload.
- AdminSubscriptionUpdate: Validates admin-side subscription mutations.

CHANGE_SUMMARY
- 2026-03-27: Added device_limit to plan create and update schemas so plan slot limits can be managed through the API.
"""
# <!-- GRACE: module="M-004" contract="billing-schemas" -->

from datetime import datetime

from pydantic import Field

from sqlmodel import SQLModel
from app.billing.models import PaymentProvider, PaymentStatus, SubscriptionStatus


# START_BLOCK: PlanCreate schema
class PlanCreate(SQLModel):
    """Schema for creating a plan."""
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    price: float = Field(..., ge=0)
    currency: str = Field(default="RUB", max_length=3)
    duration_days: int = Field(..., ge=1)
    device_limit: int = Field(default=1, ge=1)
    features: list[str] = Field(default=[])
    is_popular: bool = False
    sort_order: int = 0
# END_BLOCK


# START_BLOCK: PlanUpdate schema
class PlanUpdate(SQLModel):
    """Schema for updating a plan."""
    name: str | None = None
    description: str | None = None
    price: float | None = None
    duration_days: int | None = None
    device_limit: int | None = Field(default=None, ge=1)
    features: list[str] | None = None
    is_active: bool | None = None
    is_popular: bool | None = None
    sort_order: int | None = None
# END_BLOCK


# START_BLOCK: SubscribeRequest schema
class SubscribeRequest(SQLModel):
    """Request to create a subscription."""
    plan_id: int
    provider: PaymentProvider = Field(default=PaymentProvider.YOOKASSA)
# END_BLOCK


# START_BLOCK: SubscriptionStatusResponse schema
class SubscriptionStatusResponse(SQLModel):
    """Subscription status response."""
    has_subscription: bool
    is_active: bool
    is_trial: bool
    plan_name: str | None
    days_left: int
    expires_at: datetime | None
    is_recurring: bool
# END_BLOCK


# START_BLOCK: PaymentCreateRequest schema
class PaymentCreateRequest(SQLModel):
    """Request to create a payment."""
    plan_id: int
    return_url: str | None = None
# END_BLOCK


# START_BLOCK: PaymentWebhookYooKassa schema
class PaymentWebhookYooKassa(SQLModel):
    """YooKassa webhook payload."""
    type: str
    event: str
    object: dict
# END_BLOCK


# START_BLOCK: PaymentHistoryResponse schema
class PaymentHistoryResponse(SQLModel):
    """Payment history response."""
    items: list
    total: int
# END_BLOCK


# START_BLOCK: AdminSubscriptionUpdate schema
class AdminSubscriptionUpdate(SQLModel):
    """Admin update for subscription."""
    status: SubscriptionStatus | None = None
    is_active: bool | None = None
    expires_at: datetime | None = None
    is_recurring: bool | None = None
# END_BLOCK
