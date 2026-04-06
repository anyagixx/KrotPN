# FILE: backend/app/billing/yookassa.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: YooKassa payment API integration -- create, query, cancel payments, webhook signature verification, recurring payments.
#   SCOPE: HTTP client wrapper around YooKassa REST API with auth, idempotency keys, and error handling.
#   DEPENDS: M-001 (config), M-004 (billing models)
#   LINKS: M-004 (billing)
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   YooKassaClient - Client class for all YooKassa API operations
#   create_payment, get_payment, cancel_payment, create_recurring_payment - Payment CRUD
#   verify_webhook_signature - Webhook signature verification
#   yookassa_client - Global singleton instance
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT, MODULE_MAP, and BLOCKS per GRACE governance protocol
#   v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""
YooKassa payment integration.
"""
# <!-- GRACE: module="M-004" contract="yookassa-integration" -->

import uuid
from typing import Any

import httpx
from loguru import logger

from app.core.config import settings


# START_BLOCK: YooKassaClient class
class YooKassaClient:
    """Client for YooKassa API."""

    BASE_URL = "https://api.yookassa.ru/v3"

    def __init__(
        self,
        shop_id: str | None = None,
        secret_key: str | None = None,
    ):
        self.shop_id = shop_id or settings.yookassa_shop_id
        self.secret_key = secret_key or settings.yookassa_secret_key

        if not self.shop_id or not self.secret_key:
            logger.warning("[YOOKASSA] Credentials not configured")

    @property
    def auth(self) -> tuple[str, str]:
        """Get auth tuple for HTTP Basic Auth."""
        return (self.shop_id, self.secret_key)

    def _generate_idempotency_key(self) -> str:
        """Generate unique idempotency key."""
        return str(uuid.uuid4())

    # START_BLOCK: create_payment
    async def create_payment(
        self,
        amount: float,
        currency: str = "RUB",
        description: str = "VPN Subscription",
        return_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a payment in YooKassa.

        Args:
            amount: Payment amount
            currency: Currency code (RUB)
            description: Payment description
            return_url: URL to redirect after payment
            metadata: Additional metadata

        Returns:
            Payment object from YooKassa
        """
        if not self.shop_id or not self.secret_key:
            raise ValueError("YooKassa credentials not configured")

        payload = {
            "amount": {
                "value": f"{amount:.2f}",
                "currency": currency,
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url or settings.telegram_webhook_url or "https://krotvpn.com",
            },
            "capture": True,
            "description": description,
            "metadata": metadata or {},
        }

        headers = {
            "Idempotence-Key": self._generate_idempotency_key(),
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/payments",
                json=payload,
                headers=headers,
                auth=self.auth,
                timeout=30.0,
            )

            if response.status_code not in (200, 201):
                logger.error(f"[YOOKASSA] Create payment failed: {response.text}")
                raise Exception(f"YooKassa error: {response.status_code}")

            data = response.json()
            logger.info(f"[YOOKASSA] Payment created: {data.get('id')}")
            return data
    # END_BLOCK

    # START_BLOCK: get_payment
    async def get_payment(self, payment_id: str) -> dict[str, Any]:
        """
        Get payment status from YooKassa.

        Args:
            payment_id: YooKassa payment ID

        Returns:
            Payment object
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/payments/{payment_id}",
                auth=self.auth,
                timeout=30.0,
            )

            if response.status_code != 200:
                raise Exception(f"YooKassa error: {response.status_code}")

            return response.json()
    # END_BLOCK

    # START_BLOCK: cancel_payment
    async def cancel_payment(self, payment_id: str) -> dict[str, Any]:
        """
        Cancel a pending payment.

        Args:
            payment_id: YooKassa payment ID

        Returns:
            Canceled payment object
        """
        headers = {
            "Idempotence-Key": self._generate_idempotency_key(),
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/payments/{payment_id}/cancel",
                headers=headers,
                auth=self.auth,
                timeout=30.0,
            )

            if response.status_code not in (200, 201):
                raise Exception(f"YooKassa error: {response.status_code}")

            return response.json()
    # END_BLOCK

    # START_BLOCK: create_recurring_payment
    async def create_recurring_payment(
        self,
        amount: float,
        payment_method_id: str,
        description: str = "VPN Subscription Renewal",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a recurring payment using saved payment method.

        Args:
            amount: Payment amount
            payment_method_id: Saved payment method ID
            description: Payment description
            metadata: Additional metadata

        Returns:
            Payment object
        """
        payload = {
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "RUB",
            },
            "capture": True,
            "payment_method_id": payment_method_id,
            "description": description,
            "metadata": metadata or {},
        }

        headers = {
            "Idempotence-Key": self._generate_idempotency_key(),
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/payments",
                json=payload,
                headers=headers,
                auth=self.auth,
                timeout=30.0,
            )

            if response.status_code not in (200, 201):
                raise Exception(f"YooKassa error: {response.status_code}")

            return response.json()
    # END_BLOCK

    # START_BLOCK: verify_webhook_signature
    def verify_webhook_signature(
        self,
        body: bytes,
        signature: str,
    ) -> bool:
        """
        Verify YooKassa webhook signature.

        Args:
            body: Raw request body
            signature: Signature from header

        Returns:
            True if signature is valid
        """
        import hmac
        import hashlib

        if not self.secret_key:
            return False

        expected = hmac.new(
            self.secret_key.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)
    # END_BLOCK
# END_BLOCK


# Global client
yookassa_client = YooKassaClient()
