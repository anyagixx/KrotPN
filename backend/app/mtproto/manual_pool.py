"""Manual external MTProto proxy pool and delivery selector.

# FILE: backend/app/mtproto/manual_pool.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Manage admin-supplied external MTProto proxies and select owner delivery mode without touching KrotPN runtime provisioning
#   SCOPE: External proxy validation, encrypted secret storage, redacted admin serialization,
#          singleton delivery-mode settings, and owner-only manual proxy response construction
#   DEPENDS: M-001 (security/config), M-002 (users), M-043/M-045 (MTProto owner contract), M-082
#   LINKS: M-082, V-M-082, Phase-80
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MTProtoManualProxyPoolError - Safe service exception for admin/API mapping
#   build_manual_tg_link / build_manual_browser_link - Telegram link builders for owner responses
#   MTProtoManualProxyPoolService - Admin pool CRUD, delivery-mode selection, and owner manual payload
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-80 manual external MTProto proxy pool service.
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import re
from datetime import datetime, timezone
from urllib.parse import urlencode

from loguru import logger
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.core.security import decrypt_data, encrypt_data
from app.mtproto.models import (
    MTProtoDeliveryMode,
    MTProtoDeliverySettings,
    MTProtoManualExternalProxy,
    MTProtoManualProxyStatus,
)
from app.mtproto.schemas import (
    MTProtoOwnerProxyResponse,
    MTProtoOwnerProxyStatus,
    MTProtoProxySource,
)
from app.users.models import User


HEX_SECRET_RE = re.compile(r"^[0-9a-f]+$")
DOMAIN_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class MTProtoManualProxyPoolError(ValueError):
    """Safe service exception for manual proxy pool operations."""

    def __init__(self, message: str, *, not_found: bool = False) -> None:
        super().__init__(message)
        self.safe_message = message
        self.not_found = not_found


# START_CONTRACT: build_manual_tg_link
#   PURPOSE: Build a Telegram app deep link for an owner-visible manual external proxy
#   INPUTS: server: str; port: int; secret: str
#   OUTPUTS: str
#   SIDE_EFFECTS: none
#   LINKS: M-082, V-M-082
# END_CONTRACT: build_manual_tg_link
# START_BLOCK_MANUAL_LINK_BUILDERS
def build_manual_tg_link(server: str, port: int, secret: str) -> str:
    """Build a tg://proxy link for Telegram app clients."""
    query = urlencode({"server": server, "port": str(port), "secret": secret})
    return f"tg://proxy?{query}"


def build_manual_browser_link(server: str, port: int, secret: str) -> str:
    """Build a https://t.me/proxy link for browsers and copy flows."""
    query = urlencode({"server": server, "port": str(port), "secret": secret})
    return f"https://t.me/proxy?{query}"
# END_BLOCK_MANUAL_LINK_BUILDERS


class MTProtoManualProxyPoolService:
    """Manage manual external MTProto pool rows and delivery selection."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        app_settings: Settings = settings,
    ) -> None:
        self.session = session
        self.settings = app_settings

    # START_CONTRACT: get_delivery_settings
    #   PURPOSE: Load or create the singleton delivery settings row with automatic mode by default
    #   INPUTS: none
    #   OUTPUTS: MTProtoDeliverySettings
    #   SIDE_EFFECTS: inserts singleton row when absent
    #   LINKS: M-082, V-M-082
    # END_CONTRACT: get_delivery_settings
    # START_BLOCK_DELIVERY_SETTINGS
    async def get_delivery_settings(self) -> MTProtoDeliverySettings:
        """Return singleton delivery settings; default is automatic."""
        settings_row = await self.session.get(MTProtoDeliverySettings, 1)
        if settings_row is not None:
            return settings_row

        settings_row = MTProtoDeliverySettings(
            id=1,
            mode=MTProtoDeliveryMode.AUTOMATIC,
        )
        self.session.add(settings_row)
        await self.session.flush()
        await self.session.refresh(settings_row)
        logger.info("[M-082][manual_proxy_delivery][MODE_DEFAULT] mode=automatic")
        return settings_row

    async def delivery_mode_state(self) -> dict[str, object]:
        """Return redacted admin state for the current delivery mode."""
        settings_row = await self.get_delivery_settings()
        active_proxy = await self._get_active_manual_proxy(settings_row)
        payload = {
            "mode": settings_row.mode.value,
            "active_manual_proxy_id": settings_row.active_manual_proxy_id,
            "active_manual_proxy": self.serialize_manual_proxy(active_proxy) if active_proxy else None,
            "automatic_telemetry_available": True,
            "manual_telemetry_available": False,
            "telemetry_available": settings_row.mode == MTProtoDeliveryMode.AUTOMATIC,
            "promotion_tag_scope": "krotpn_auto_runtime_only",
            "updated_by_admin_id": settings_row.updated_by_admin_id,
            "updated_at": settings_row.updated_at,
        }
        logger.info(
            "[M-082][manual_proxy_delivery][MODE_STATE] "
            f"mode={payload['mode']} active_manual_proxy_id={payload['active_manual_proxy_id']}"
        )
        return payload

    async def set_delivery_mode(
        self,
        *,
        mode: MTProtoDeliveryMode,
        admin_id: int,
        confirm: bool,
    ) -> dict[str, object]:
        """Update owner delivery mode after explicit confirmation."""
        if not confirm:
            raise MTProtoManualProxyPoolError("Explicit MTProto delivery mode confirmation required")

        settings_row = await self.get_delivery_settings()
        if mode == MTProtoDeliveryMode.MANUAL_EXTERNAL:
            active_proxy = await self._get_active_manual_proxy(settings_row)
            if active_proxy is None:
                raise MTProtoManualProxyPoolError("Manual external mode requires one active manual proxy")

        now = _utc_now()
        settings_row.mode = mode
        settings_row.updated_by_admin_id = admin_id
        settings_row.updated_at = now
        await self.session.flush()
        logger.info(
            "[M-082][manual_proxy_delivery][MODE_UPDATED] "
            f"mode={mode.value} admin_id={admin_id}"
        )
        return await self.delivery_mode_state()
    # END_BLOCK_DELIVERY_SETTINGS

    # START_CONTRACT: list_manual_proxies
    #   PURPOSE: Return redacted manual external proxy rows for admin UI
    #   INPUTS: search/status/offset/limit filters
    #   OUTPUTS: dict with items/total/offset/limit
    #   SIDE_EFFECTS: none
    #   LINKS: M-082, V-M-082
    # END_CONTRACT: list_manual_proxies
    # START_BLOCK_MANUAL_PROXY_CRUD
    async def list_manual_proxies(
        self,
        *,
        search: str = "",
        status_filter: MTProtoManualProxyStatus | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, object]:
        """Return redacted manual proxy rows."""
        conditions = []
        search_value = search.strip().lower()
        if search_value:
            needle = f"%{search_value}%"
            conditions.append(
                or_(
                    func.lower(MTProtoManualExternalProxy.name).like(needle),
                    func.lower(MTProtoManualExternalProxy.server).like(needle),
                    func.lower(MTProtoManualExternalProxy.secret_fingerprint).like(needle),
                )
            )
        if status_filter is not None:
            conditions.append(MTProtoManualExternalProxy.status == status_filter)

        safe_offset = max(offset, 0)
        safe_limit = min(max(limit, 1), 500)
        total = int(
            (
                await self.session.execute(
                    select(func.count(MTProtoManualExternalProxy.id)).where(*conditions)
                )
            ).scalar()
            or 0
        )
        result = await self.session.execute(
            select(MTProtoManualExternalProxy)
            .where(*conditions)
            .order_by(
                MTProtoManualExternalProxy.status.asc(),
                MTProtoManualExternalProxy.priority.asc(),
                MTProtoManualExternalProxy.updated_at.desc(),
                MTProtoManualExternalProxy.id.desc(),
            )
            .offset(safe_offset)
            .limit(safe_limit)
        )
        items = [self.serialize_manual_proxy(row) for row in result.scalars().all()]
        logger.info(
            "[M-082][manual_proxy_pool][LIST_REDACTED] "
            f"returned={len(items)} total={total} status={status_filter.value if status_filter else 'all'}"
        )
        return {"items": items, "total": total, "offset": safe_offset, "limit": safe_limit}

    async def create_manual_proxy(
        self,
        *,
        name: str,
        server: str,
        port: int,
        secret: str,
        admin_id: int,
        priority: int = 100,
        notes: str | None = None,
    ) -> MTProtoManualExternalProxy:
        """Create a ready manual external proxy row with encrypted secret."""
        normalized_name = _normalize_name(name)
        normalized_server = _normalize_server(server)
        normalized_port = _normalize_port(port)
        normalized_secret = _normalize_secret(secret)
        now = _utc_now()
        row = MTProtoManualExternalProxy(
            name=normalized_name,
            server=normalized_server,
            port=normalized_port,
            secret_enc=encrypt_data(normalized_secret),
            secret_fingerprint=self._fingerprint_secret(normalized_secret),
            status=MTProtoManualProxyStatus.READY,
            priority=priority,
            notes=_normalize_notes(notes),
            verified_at=now,
            created_by_admin_id=admin_id,
            updated_by_admin_id=admin_id,
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        logger.info(
            "[M-082][manual_proxy_pool][CREATE_ENCRYPTED] "
            f"proxy_id={row.id} admin_id={admin_id} fingerprint={row.secret_fingerprint[:12]}"
        )
        return row

    async def update_manual_proxy(
        self,
        proxy_id: int,
        *,
        admin_id: int,
        name: str | None = None,
        server: str | None = None,
        port: int | None = None,
        secret: str | None = None,
        priority: int | None = None,
        notes: str | None = None,
    ) -> MTProtoManualExternalProxy:
        """Update a manual proxy row without exposing the stored secret."""
        row = await self.get_manual_proxy(proxy_id)
        if name is not None:
            row.name = _normalize_name(name)
        if server is not None:
            row.server = _normalize_server(server)
        if port is not None:
            row.port = _normalize_port(port)
        if secret is not None:
            normalized_secret = _normalize_secret(secret)
            row.secret_enc = encrypt_data(normalized_secret)
            row.secret_fingerprint = self._fingerprint_secret(normalized_secret)
            row.verified_at = _utc_now()
        if priority is not None:
            row.priority = int(priority)
        if notes is not None:
            row.notes = _normalize_notes(notes)
        row.updated_by_admin_id = admin_id
        row.updated_at = _utc_now()
        await self.session.flush()
        await self.session.refresh(row)
        logger.info(
            "[M-082][manual_proxy_pool][UPDATE_REDACTED] "
            f"proxy_id={row.id} admin_id={admin_id}"
        )
        return row

    async def activate_manual_proxy(
        self,
        proxy_id: int,
        *,
        admin_id: int,
        confirm: bool,
    ) -> MTProtoManualExternalProxy:
        """Mark exactly one manual proxy as active and select it in delivery settings."""
        if not confirm:
            raise MTProtoManualProxyPoolError("Explicit manual proxy activation confirmation required")

        row = await self.get_manual_proxy(proxy_id)
        if row.status == MTProtoManualProxyStatus.DISABLED:
            row.status = MTProtoManualProxyStatus.READY

        result = await self.session.execute(
            select(MTProtoManualExternalProxy).where(
                MTProtoManualExternalProxy.status == MTProtoManualProxyStatus.ACTIVE,
                MTProtoManualExternalProxy.id != row.id,
            )
        )
        now = _utc_now()
        for active_row in result.scalars().all():
            active_row.status = MTProtoManualProxyStatus.READY
            active_row.updated_at = now
            active_row.updated_by_admin_id = admin_id

        row.status = MTProtoManualProxyStatus.ACTIVE
        row.updated_at = now
        row.updated_by_admin_id = admin_id
        settings_row = await self.get_delivery_settings()
        settings_row.active_manual_proxy_id = int(row.id)
        settings_row.updated_at = now
        settings_row.updated_by_admin_id = admin_id
        await self.session.flush()
        await self.session.refresh(row)
        logger.info(
            "[M-082][manual_proxy_pool][ACTIVATE_SINGLETON] "
            f"proxy_id={row.id} admin_id={admin_id}"
        )
        return row

    async def disable_manual_proxy(
        self,
        proxy_id: int,
        *,
        admin_id: int,
        confirm: bool,
    ) -> MTProtoManualExternalProxy:
        """Disable one manual proxy and clear active selection if needed."""
        if not confirm:
            raise MTProtoManualProxyPoolError("Explicit manual proxy disable confirmation required")

        row = await self.get_manual_proxy(proxy_id)
        row.status = MTProtoManualProxyStatus.DISABLED
        row.updated_at = _utc_now()
        row.updated_by_admin_id = admin_id
        settings_row = await self.get_delivery_settings()
        if settings_row.active_manual_proxy_id == row.id:
            settings_row.active_manual_proxy_id = None
            settings_row.updated_at = row.updated_at
            settings_row.updated_by_admin_id = admin_id
        await self.session.flush()
        await self.session.refresh(row)
        logger.info(
            "[M-082][manual_proxy_pool][DISABLE_MANUAL] "
            f"proxy_id={row.id} admin_id={admin_id}"
        )
        return row

    async def get_manual_proxy(self, proxy_id: int) -> MTProtoManualExternalProxy:
        """Load one manual proxy or raise a safe not-found error."""
        row = await self.session.get(MTProtoManualExternalProxy, proxy_id)
        if row is None:
            raise MTProtoManualProxyPoolError("Manual MTProto proxy not found", not_found=True)
        return row
    # END_BLOCK_MANUAL_PROXY_CRUD

    # START_CONTRACT: owner_response_for_current_mode
    #   PURPOSE: Return a manual owner response when delivery mode is manual_external; otherwise defer to automatic provisioning
    #   INPUTS: user: User
    #   OUTPUTS: MTProtoOwnerProxyResponse | None
    #   SIDE_EFFECTS: decrypts selected manual secret only for owner response construction; does not create automatic assignments
    #   LINKS: M-045, M-082, V-M-082
    # END_CONTRACT: owner_response_for_current_mode
    # START_BLOCK_OWNER_DELIVERY_SELECTOR
    async def owner_response_for_current_mode(self, user: User) -> MTProtoOwnerProxyResponse | None:
        """Return manual external owner response or None when automatic mode is active."""
        settings_row = await self.get_delivery_settings()
        if settings_row.mode == MTProtoDeliveryMode.AUTOMATIC:
            logger.info("[M-082][manual_proxy_delivery][AUTOMATIC_PASSTHROUGH]")
            return None

        if not user.email_verified:
            return MTProtoOwnerProxyResponse(
                status=MTProtoOwnerProxyStatus.UNVERIFIED,
                safe_message="Подтвердите email, чтобы получить Telegram proxy.",
                action_required="verify_email",
                source=MTProtoProxySource.MANUAL_EXTERNAL,
                telemetry_available=False,
            )

        active_proxy = await self._get_active_manual_proxy(settings_row)
        if active_proxy is None:
            logger.warning("[M-082][manual_proxy_delivery][MANUAL_MISSING_ACTIVE]")
            return MTProtoOwnerProxyResponse(
                status=MTProtoOwnerProxyStatus.PENDING,
                safe_message="Telegram proxy готовится. Попробуйте позже.",
                action_required="wait",
                source=MTProtoProxySource.MANUAL_EXTERNAL,
                telemetry_available=False,
            )

        secret = decrypt_data(active_proxy.secret_enc)
        tg_link = build_manual_tg_link(active_proxy.server, active_proxy.port, secret)
        browser_link = build_manual_browser_link(active_proxy.server, active_proxy.port, secret)
        logger.info(
            "[M-082][manual_proxy_delivery][OWNER_MANUAL_RESPONSE] "
            f"user_id={user.id} proxy_id={active_proxy.id}"
        )
        return MTProtoOwnerProxyResponse(
            status=MTProtoOwnerProxyStatus.ACTIVATED,
            safe_message="Manual external MTProto proxy is ready",
            action_required=None,
            assignment_id=None,
            server=active_proxy.server,
            port=active_proxy.port,
            secret=secret,
            tg_link=tg_link,
            browser_link=browser_link,
            sni=active_proxy.server,
            credential_mode=MTProtoProxySource.MANUAL_EXTERNAL.value,
            rotation_marker=MTProtoProxySource.MANUAL_EXTERNAL.value,
            reissue_required=False,
            source=MTProtoProxySource.MANUAL_EXTERNAL,
            telemetry_available=False,
            manual_proxy_name=active_proxy.name,
        )
    # END_BLOCK_OWNER_DELIVERY_SELECTOR

    # START_BLOCK_SERIALIZATION_AND_HELPERS
    def serialize_manual_proxy(self, row: MTProtoManualExternalProxy | None) -> dict[str, object] | None:
        """Return admin-safe manual proxy data without raw secret or Telegram links."""
        if row is None:
            return None
        return {
            "id": row.id,
            "name": row.name,
            "server": row.server,
            "port": row.port,
            "status": row.status.value,
            "priority": row.priority,
            "notes": row.notes,
            "secret_fingerprint": row.secret_fingerprint,
            "secret_label": f"fingerprint:{row.secret_fingerprint[:12]}",
            "verified_at": row.verified_at,
            "created_by_admin_id": row.created_by_admin_id,
            "updated_by_admin_id": row.updated_by_admin_id,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "telemetry_available": False,
            "promotion_tag_scope": "external_proxy_configured_outside_krotpn",
        }

    async def _get_active_manual_proxy(
        self,
        settings_row: MTProtoDeliverySettings,
    ) -> MTProtoManualExternalProxy | None:
        if settings_row.active_manual_proxy_id is not None:
            row = await self.session.get(MTProtoManualExternalProxy, settings_row.active_manual_proxy_id)
            if row is not None and row.status == MTProtoManualProxyStatus.ACTIVE:
                return row

        result = await self.session.execute(
            select(MTProtoManualExternalProxy)
            .where(MTProtoManualExternalProxy.status == MTProtoManualProxyStatus.ACTIVE)
            .order_by(MTProtoManualExternalProxy.priority.asc(), MTProtoManualExternalProxy.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _fingerprint_secret(self, secret: str) -> str:
        key = self.settings.secret_key.encode("utf-8")
        return hmac.new(key, secret.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    # END_BLOCK_SERIALIZATION_AND_HELPERS


# START_BLOCK_VALIDATION_HELPERS
def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_name(value: str) -> str:
    normalized = value.strip()
    if not 1 <= len(normalized) <= 120:
        raise MTProtoManualProxyPoolError("Manual MTProto proxy name must be 1-120 characters")
    return normalized


def _normalize_notes(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized[:1000]


def _normalize_port(value: int) -> int:
    port = int(value)
    if port < 1 or port > 65535:
        raise MTProtoManualProxyPoolError("Manual MTProto proxy port must be 1-65535")
    return port


def _normalize_secret(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise MTProtoManualProxyPoolError("Manual MTProto proxy secret is required")
    if not HEX_SECRET_RE.fullmatch(normalized):
        raise MTProtoManualProxyPoolError("Manual MTProto proxy secret must be hex only")
    if len(normalized) < 32 or len(normalized) > 512 or len(normalized) % 2:
        raise MTProtoManualProxyPoolError("Manual MTProto proxy secret must be even-length hex between 32 and 512 characters")
    return normalized


def _normalize_server(value: str) -> str:
    normalized = value.strip().lower().rstrip(".")
    if not normalized:
        raise MTProtoManualProxyPoolError("Manual MTProto proxy server is required")
    if any(marker in normalized for marker in ("://", "/", "\\", "?", "#", "@")):
        raise MTProtoManualProxyPoolError("Manual MTProto proxy server must be a bare host without scheme, path, or port")
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        labels = normalized.split(".")
        if len(labels) < 2 or any(not DOMAIN_LABEL_RE.fullmatch(label) for label in labels):
            raise MTProtoManualProxyPoolError("Manual MTProto proxy server must be a valid DNS name or IP address")
        return normalized

    if address.is_unspecified or address.is_multicast or address.is_loopback or address.is_link_local:
        raise MTProtoManualProxyPoolError("Manual MTProto proxy server IP must be publicly reachable")
    return str(address)
# END_BLOCK_VALIDATION_HELPERS
