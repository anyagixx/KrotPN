# FILE: backend/app/billing/__init__.py
# VERSION: 1.0.0
# ROLE: BARREL
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: Plans, subscriptions, payments, and webhook processing with YooKassa integration
#   SCOPE: Plan CRUD, subscription lifecycle, payment creation, webhook handling, plan limits
#   DEPENDS: M-001 (backend-core)
#   LINKS: M-004 (billing), V-M-004
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   Plan, Subscription, Payment - Database models for billing entities
#   CANONICAL_TARIFFS, CANONICAL_TARIFF_SLUGS - Phase-50 paid tariff catalog exports
#   PlanCreate, PlanUpdate, SubscribeRequest - Request/Response schemas
#   BillingService - Subscription lifecycle, webhook processing, plan limit checks
#   YooKassaClient, yookassa_client - Payment provider integration
#   billing_router, admin_billing_router - FastAPI routers for user and admin billing operations
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v3.2.0 - Exported Phase-50 canonical paid tariff catalog.
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""Billing module exports."""
from app.billing.models import (
    Plan,
    Subscription,
    SubscriptionStatus,
    Payment,
    PaymentProvider,
    PaymentStatus,
    PlanResponse,
    SubscriptionResponse,
    PaymentResponse,
)
from app.billing.catalog import CANONICAL_TARIFFS, CANONICAL_TARIFF_SLUGS
from app.billing.schemas import (
    PlanCreate,
    PlanUpdate,
    SubscribeRequest,
    SubscriptionStatusResponse,
    PaymentCreateRequest,
    PaymentHistoryResponse,
)
from app.billing.service import BillingService
from app.billing.yookassa import YooKassaClient, yookassa_client
from app.billing.router import router as billing_router
from app.billing.router import admin_router as admin_billing_router

__all__ = [
    # Models
    "Plan",
    "Subscription",
    "SubscriptionStatus",
    "Payment",
    "PaymentProvider",
    "PaymentStatus",
    "PlanResponse",
    "SubscriptionResponse",
    "PaymentResponse",
    "CANONICAL_TARIFFS",
    "CANONICAL_TARIFF_SLUGS",
    # Schemas
    "PlanCreate",
    "PlanUpdate",
    "SubscribeRequest",
    "SubscriptionStatusResponse",
    "PaymentCreateRequest",
    "PaymentHistoryResponse",
    # Service
    "BillingService",
    # YooKassa
    "YooKassaClient",
    "yookassa_client",
    # Routers
    "billing_router",
    "admin_billing_router",
]
