# FILE: backend/app/mtproto/official_secrets.py
# VERSION: 1.0.0
# START_MODULE_CONTRACT
#   PURPOSE: Derive, redact, and synchronize official MTProxy secure secrets for KrotPN users.
#   SCOPE: Per-assignment secret derivation, tg:// link formatting, runtime manifest rendering, and private runtime apply/health calls.
#   DEPENDS: M-001, M-052, M-053
#   LINKS: docs/modules/M-053.xml, docs/modules/M-052.xml, docs/plans/Phase-40.xml
#   ROLE: RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   derive_official_secret - derives one stable official 32-hex MTProxy secret for an assignment
#   build_secure_secret - converts a raw 32-hex official secret to Telegram dd-prefixed secure mode
#   build_official_tg_link - builds an owner-only tg://proxy link for official MTProxy
#   secret_fingerprint - returns a non-secret audit fingerprint
#   MTProxySecretManifestEntry - one runtime manifest row without public link material
#   MTProxySecretManifest - official runtime manifest with redacted safe output
#   MTProxySecretSyncResult - safe result envelope for manifest sync operations
#   InMemoryMTProxySecretAdapter - deterministic adapter for tests and no-runtime local mode
#   HTTPMTProxySecretAdapter - private HTTP adapter for the official MTProxy edge supervisor
#   MTProxySecretSyncService - renders and applies active official MTProxy assignment manifests
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   v1.0.0 - Added official MTProxy secure-secret derivation and runtime manifest sync for Phase-40.
# END_CHANGE_SUMMARY

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol, Sequence
from urllib.parse import urlencode

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.mtproto.models import MTProtoAssignment, MTProtoAssignmentStatus, MTProtoCredentialMode
from app.mtproto.runtime_bridge import (
    MTProtoBridgeFailureCode,
    MTProtoBridgeStatus,
    MTProtoRuntimeHealth,
)


OFFICIAL_SECRET_HEX_LENGTH = 32
SECURE_SECRET_PREFIX = "dd"
DEFAULT_MANIFEST_LIMIT = 5000


class MTProxyManifestApplyReason(str, Enum):
    REPLAY = "replay"
    ISSUE = "issue"
    REISSUE = "reissue"
    REVOKE = "revoke"
    MANUAL = "manual"


# START_BLOCK_NORMALIZE
def _normalize_hex_secret(value: str, *, expected_length: int, field_name: str) -> str:
    normalized = (value or "").strip().lower()
    if len(normalized) != expected_length:
        raise ValueError(f"{field_name} must be {expected_length} hex characters")
    try:
        bytes.fromhex(normalized)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be valid hex") from exc
    return normalized


def _assignment_stability_material(assignment: MTProtoAssignment) -> str:
    if assignment.id is None:
        raise ValueError("assignment id is required before MTProxy secret derivation")
    issued_at = assignment.issued_at or assignment.created_at or datetime.now(UTC)
    return "|".join(
        [
            str(assignment.id),
            str(assignment.user_id),
            assignment.sni,
            assignment.rotation_marker or "",
            issued_at.isoformat(),
        ]
    )


def secret_fingerprint(secret_hex: str) -> str:
    normalized = _normalize_hex_secret(
        secret_hex,
        expected_length=OFFICIAL_SECRET_HEX_LENGTH,
        field_name="secret_hex",
    )
    return hashlib.sha256(bytes.fromhex(normalized)).hexdigest()[:16]
# END_BLOCK_NORMALIZE


# START_CONTRACT: derive_official_secret
#   PURPOSE: Derive one official MTProxy raw 32-hex secret for an assignment without storing it in DB.
#   INPUTS: { base_secret_hex: str - operator secret, secret_salt: str - operator salt, assignment: MTProtoAssignment - persisted assignment }
#   OUTPUTS: { str - raw 32-hex MTProxy secret accepted by official mtproto-proxy -S }
#   SIDE_EFFECTS: emits a fingerprint-only trace log
#   LINKS: M-053, M-052, Phase-40
# END_CONTRACT: derive_official_secret
def derive_official_secret(
    base_secret_hex: str,
    secret_salt: str,
    assignment: MTProtoAssignment,
) -> str:
    # START_BLOCK_DERIVE
    base_key = bytes.fromhex(
        _normalize_hex_secret(
            base_secret_hex,
            expected_length=32,
            field_name="MTPROTO_BASE_SECRET_HEX",
        )
    )
    salt = (secret_salt or "").strip()
    if not salt:
        raise ValueError("MTPROTO_SECRET_SALT is required for official MTProxy secrets")
    material = _assignment_stability_material(assignment)
    digest = hmac.new(base_key, f"{salt}|{material}".encode("utf-8"), hashlib.sha256).hexdigest()
    secret_hex = digest[:OFFICIAL_SECRET_HEX_LENGTH]
    logger.info(
        "[MTProxySecretSync][derive][FINGERPRINT_ONLY] official secret derived",
        extra={
            "assignment_id": assignment.id,
            "user_id": assignment.user_id,
            "secret_fingerprint": secret_fingerprint(secret_hex),
        },
    )
    return secret_hex
    # END_BLOCK_DERIVE


# START_CONTRACT: build_secure_secret
#   PURPOSE: Convert raw official MTProxy secret into Telegram secure dd mode.
#   INPUTS: { secret_hex: str - raw 32-hex official MTProxy secret }
#   OUTPUTS: { str - dd-prefixed Telegram client secret }
#   SIDE_EFFECTS: none
#   LINKS: M-053, Phase-40
# END_CONTRACT: build_secure_secret
def build_secure_secret(secret_hex: str) -> str:
    # START_BLOCK_BUILD_SECURE_SECRET
    normalized = _normalize_hex_secret(
        secret_hex,
        expected_length=OFFICIAL_SECRET_HEX_LENGTH,
        field_name="secret_hex",
    )
    return f"{SECURE_SECRET_PREFIX}{normalized}"
    # END_BLOCK_BUILD_SECURE_SECRET


# START_CONTRACT: build_official_tg_link
#   PURPOSE: Build owner-only Telegram proxy link for official MTProxy secure mode.
#   INPUTS: { server: str - public proxy hostname, port: int - public proxy port, secret_hex: str - raw official secret }
#   OUTPUTS: { str - tg://proxy URL with dd-prefixed secret }
#   SIDE_EFFECTS: none
#   LINKS: M-053, Phase-40
# END_CONTRACT: build_official_tg_link
def build_official_tg_link(server: str, port: int, secret_hex: str) -> str:
    # START_BLOCK_BUILD_TG_LINK
    if not server or not server.strip():
        raise ValueError("server is required")
    if not (1 <= int(port) <= 65535):
        raise ValueError("port must be between 1 and 65535")
    query = urlencode(
        {
            "server": server.strip(),
            "port": str(int(port)),
            "secret": build_secure_secret(secret_hex),
        }
    )
    return f"tg://proxy?{query}"
    # END_BLOCK_BUILD_TG_LINK


@dataclass(frozen=True)
class MTProxySecretManifestEntry:
    assignment_id: int
    user_id: int
    sni: str
    secret_hex: str
    secret_fingerprint: str

    # START_BLOCK_ENTRY_SERIALIZE
    @classmethod
    def from_assignment(
        cls,
        assignment: MTProtoAssignment,
        *,
        app_settings: Settings,
    ) -> "MTProxySecretManifestEntry":
        if assignment.id is None:
            raise ValueError("assignment id is required for manifest rendering")
        secret_hex = derive_official_secret(
            app_settings.mtproto_base_secret_hex,
            app_settings.mtproto_secret_salt,
            assignment,
        )
        return cls(
            assignment_id=assignment.id,
            user_id=assignment.user_id,
            sni=assignment.sni,
            secret_hex=secret_hex,
            secret_fingerprint=secret_fingerprint(secret_hex),
        )

    def to_runtime_dict(self) -> dict[str, Any]:
        return {
            "assignment_id": self.assignment_id,
            "user_id": self.user_id,
            "sni": self.sni,
            "secret_hex": self.secret_hex,
            "secret_fingerprint": self.secret_fingerprint,
        }

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "assignment_id": self.assignment_id,
            "user_id": self.user_id,
            "sni": self.sni,
            "secret_fingerprint": self.secret_fingerprint,
        }
    # END_BLOCK_ENTRY_SERIALIZE


@dataclass(frozen=True)
class MTProxySecretManifest:
    entries: tuple[MTProxySecretManifestEntry, ...]
    generated_at: datetime

    # START_BLOCK_MANIFEST_SERIALIZE
    @property
    def active_count(self) -> int:
        return len(self.entries)

    @property
    def manifest_fingerprint(self) -> str:
        material = "|".join(entry.secret_fingerprint for entry in self.entries)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]

    def to_runtime_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "active_count": self.active_count,
            "manifest_fingerprint": self.manifest_fingerprint,
            "secrets": [entry.to_runtime_dict() for entry in self.entries],
        }

    def to_safe_dict(self) -> dict[str, Any]:
        logger.info(
            "[MTProxySecretSync][manifest][REDACTED_COUNT] official manifest rendered",
            extra={
                "active_count": self.active_count,
                "manifest_fingerprint": self.manifest_fingerprint,
            },
        )
        return {
            "generated_at": self.generated_at.isoformat(),
            "active_count": self.active_count,
            "manifest_fingerprint": self.manifest_fingerprint,
            "secrets": [entry.to_safe_dict() for entry in self.entries],
        }
    # END_BLOCK_MANIFEST_SERIALIZE


@dataclass(frozen=True)
class MTProxySecretSyncResult:
    status: MTProtoBridgeStatus
    active_count: int
    manifest_fingerprint: str | None
    assignment_id: int | None = None
    failure_code: MTProtoBridgeFailureCode | None = None
    safe_message: str | None = None
    applied_at: datetime | None = None

    # START_BLOCK_RESULT_SERIALIZE
    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "active_count": self.active_count,
            "manifest_fingerprint": self.manifest_fingerprint,
            "assignment_id": self.assignment_id,
            "failure_code": self.failure_code.value if self.failure_code else None,
            "message": self.safe_message,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
        }
    # END_BLOCK_RESULT_SERIALIZE


class MTProxySecretAdapter(Protocol):
    # START_BLOCK_ADAPTER_PROTOCOL
    async def apply_manifest(self, manifest: MTProxySecretManifest) -> MTProxySecretSyncResult:
        ...

    async def health(self) -> MTProtoRuntimeHealth:
        ...
    # END_BLOCK_ADAPTER_PROTOCOL


class InMemoryMTProxySecretAdapter:
    """Local deterministic adapter used when no private official runtime endpoint is configured."""

    # START_BLOCK_IN_MEMORY_ADAPTER
    def __init__(self) -> None:
        self.applied_manifest: MTProxySecretManifest | None = None

    async def apply_manifest(self, manifest: MTProxySecretManifest) -> MTProxySecretSyncResult:
        self.applied_manifest = manifest
        logger.info(
            "[MTProxySecretSync][apply][FINGERPRINT_CHANGED] manifest accepted by in-memory adapter",
            extra={
                "active_count": manifest.active_count,
                "manifest_fingerprint": manifest.manifest_fingerprint,
            },
        )
        return MTProxySecretSyncResult(
            status=MTProtoBridgeStatus.ACTIVATED,
            active_count=manifest.active_count,
            manifest_fingerprint=manifest.manifest_fingerprint,
            applied_at=datetime.now(UTC),
        )

    async def health(self) -> MTProtoRuntimeHealth:
        count = self.applied_manifest.active_count if self.applied_manifest else 0
        return MTProtoRuntimeHealth(
            status=MTProtoBridgeStatus.HEALTHY,
            adapter_name=f"in-memory-official-mtproxy:{count}",
            last_success_at=datetime.now(UTC),
        )
    # END_BLOCK_IN_MEMORY_ADAPTER


class HTTPMTProxySecretAdapter:
    # START_BLOCK_HTTP_ADAPTER
    def __init__(
        self,
        *,
        base_url: str,
        policy_token: str,
        timeout: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.policy_token = policy_token
        self.timeout = timeout
        self.client = client

    def _headers(self) -> dict[str, str]:
        return {"x-krotpn-mtproto-token": self.policy_token}

    async def apply_manifest(self, manifest: MTProxySecretManifest) -> MTProxySecretSyncResult:
        payload = manifest.to_runtime_dict()
        logger.info(
            "[MTProxySecretSync][apply][FINGERPRINT_CHANGED] applying official secret manifest",
            extra={
                "active_count": manifest.active_count,
                "manifest_fingerprint": manifest.manifest_fingerprint,
                "policy_url_configured": True,
            },
        )
        try:
            if self.client is None:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/secrets/apply",
                        json=payload,
                        headers=self._headers(),
                    )
            else:
                response = await self.client.post(
                    f"{self.base_url}/secrets/apply",
                    json=payload,
                    headers=self._headers(),
                )
            response.raise_for_status()
            return MTProxySecretSyncResult(
                status=MTProtoBridgeStatus.ACTIVATED,
                active_count=manifest.active_count,
                manifest_fingerprint=manifest.manifest_fingerprint,
                applied_at=datetime.now(UTC),
            )
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "[MTProxySecretSync][degraded][RETRYABLE] failed to apply official manifest",
                extra={
                    "active_count": manifest.active_count,
                    "manifest_fingerprint": manifest.manifest_fingerprint,
                    "error_type": type(exc).__name__,
                },
            )
            return MTProxySecretSyncResult(
                status=MTProtoBridgeStatus.DEGRADED,
                active_count=manifest.active_count,
                manifest_fingerprint=manifest.manifest_fingerprint,
                failure_code=MTProtoBridgeFailureCode.BRIDGE_UNAVAILABLE,
                safe_message="official MTProxy runtime did not accept manifest",
            )

    async def health(self) -> MTProtoRuntimeHealth:
        try:
            if self.client is None:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(f"{self.base_url}/health", headers=self._headers())
            else:
                response = await self.client.get(f"{self.base_url}/health", headers=self._headers())
            response.raise_for_status()
            data = response.json()
            status_value = data.get("status", MTProtoBridgeStatus.HEALTHY.value)
            return MTProtoRuntimeHealth(
                status=MTProtoBridgeStatus(status_value),
                adapter_name="official-mtproxy-http",
                last_success_at=datetime.now(UTC),
            )
        except (httpx.HTTPError, ValueError, TypeError):
            return MTProtoRuntimeHealth(
                status=MTProtoBridgeStatus.DEGRADED,
                adapter_name="official-mtproxy-http",
                last_failure_code=MTProtoBridgeFailureCode.BRIDGE_UNAVAILABLE,
            )
    # END_BLOCK_HTTP_ADAPTER


# START_BLOCK_ADAPTER_FACTORY
def build_default_secret_adapter(app_settings: Settings) -> MTProxySecretAdapter:
    if app_settings.mtproto_runtime_policy_url and app_settings.mtproto_runtime_token:
        return HTTPMTProxySecretAdapter(
            base_url=str(app_settings.mtproto_runtime_policy_url),
            policy_token=app_settings.mtproto_runtime_token,
            timeout=float(app_settings.mtproto_runtime_timeout_seconds),
        )
    return InMemoryMTProxySecretAdapter()
# END_BLOCK_ADAPTER_FACTORY


class MTProxySecretSyncService:
    # START_BLOCK_SYNC_SERVICE_INIT
    def __init__(
        self,
        session: AsyncSession,
        *,
        app_settings: Settings = settings,
        adapter: MTProxySecretAdapter | None = None,
        manifest_limit: int = DEFAULT_MANIFEST_LIMIT,
    ) -> None:
        self.session = session
        self.settings = app_settings
        self.adapter = adapter or build_default_secret_adapter(app_settings)
        self.manifest_limit = manifest_limit
    # END_BLOCK_SYNC_SERVICE_INIT

    # START_CONTRACT: render_active_manifest
    #   PURPOSE: Render active official MTProxy assignments as a redaction-safe runtime manifest.
    #   INPUTS: {}
    #   OUTPUTS: { MTProxySecretManifest - active official assignments and raw runtime secrets }
    #   SIDE_EFFECTS: emits redacted manifest-count trace
    #   LINKS: M-053, M-052, Phase-40
    # END_CONTRACT: render_active_manifest
    async def render_active_manifest(self) -> MTProxySecretManifest:
        # START_BLOCK_RENDER_ACTIVE
        result = await self.session.execute(
            select(MTProtoAssignment)
            .where(MTProtoAssignment.status == MTProtoAssignmentStatus.ACTIVE)
            .where(MTProtoAssignment.credential_mode == MTProtoCredentialMode.OFFICIAL_SECURE)
            .order_by(MTProtoAssignment.id.asc())
            .limit(self.manifest_limit)
        )
        assignments: Sequence[MTProtoAssignment] = result.scalars().all()
        entries = tuple(
            MTProxySecretManifestEntry.from_assignment(
                assignment,
                app_settings=self.settings,
            )
            for assignment in assignments
        )
        manifest = MTProxySecretManifest(entries=entries, generated_at=datetime.now(UTC))
        manifest.to_safe_dict()
        return manifest
        # END_BLOCK_RENDER_ACTIVE

    # START_CONTRACT: apply_active_manifest
    #   PURPOSE: Apply the full active official MTProxy secret manifest to runtime.
    #   INPUTS: { reason: MTProxyManifestApplyReason|str - audit reason, assignment_id: int|None - triggering assignment }
    #   OUTPUTS: { MTProxySecretSyncResult - safe sync result without raw secrets }
    #   SIDE_EFFECTS: updates private official MTProxy runtime manifest
    #   LINKS: M-053, M-052, Phase-40
    # END_CONTRACT: apply_active_manifest
    async def apply_active_manifest(
        self,
        *,
        reason: MTProxyManifestApplyReason | str = MTProxyManifestApplyReason.MANUAL,
        assignment_id: int | None = None,
    ) -> MTProxySecretSyncResult:
        # START_BLOCK_APPLY_ACTIVE
        manifest = await self.render_active_manifest()
        result = await self.adapter.apply_manifest(manifest)
        logger.info(
            "[MTProxySecretSync][replay][ACTIVE_COUNT] official manifest apply completed",
            extra={
                "reason": reason.value if isinstance(reason, MTProxyManifestApplyReason) else reason,
                "assignment_id": assignment_id,
                "active_count": result.active_count,
                "status": result.status.value,
                "manifest_fingerprint": result.manifest_fingerprint,
            },
        )
        return MTProxySecretSyncResult(
            status=result.status,
            active_count=result.active_count,
            manifest_fingerprint=result.manifest_fingerprint,
            assignment_id=assignment_id,
            failure_code=result.failure_code,
            safe_message=result.safe_message,
            applied_at=result.applied_at,
        )
        # END_BLOCK_APPLY_ACTIVE

    async def apply_assignment_secret(self, assignment: MTProtoAssignment) -> MTProxySecretSyncResult:
        # START_BLOCK_APPLY_ASSIGNMENT
        return await self.apply_active_manifest(
            reason=MTProxyManifestApplyReason.ISSUE,
            assignment_id=assignment.id,
        )
        # END_BLOCK_APPLY_ASSIGNMENT

    async def reissue_assignment_secret(self, assignment: MTProtoAssignment) -> MTProxySecretSyncResult:
        # START_BLOCK_REISSUE_ASSIGNMENT
        result = await self.apply_active_manifest(
            reason=MTProxyManifestApplyReason.REISSUE,
            assignment_id=assignment.id,
        )
        logger.info(
            "[MTProxySecretSync][reissue][ROTATED_ONE] official assignment secret rotated",
            extra={
                "assignment_id": assignment.id,
                "status": result.status.value,
                "manifest_fingerprint": result.manifest_fingerprint,
            },
        )
        return result
        # END_BLOCK_REISSUE_ASSIGNMENT

    async def revoke_assignment_secret(self, assignment: MTProtoAssignment) -> MTProxySecretSyncResult:
        # START_BLOCK_REVOKE_ASSIGNMENT
        result = await self.apply_active_manifest(
            reason=MTProxyManifestApplyReason.REVOKE,
            assignment_id=assignment.id,
        )
        logger.info(
            "[MTProxySecretSync][revoke][ASSIGNMENT_ONLY] official assignment secret revoked",
            extra={
                "assignment_id": assignment.id,
                "status": result.status.value,
                "manifest_fingerprint": result.manifest_fingerprint,
            },
        )
        if result.status == MTProtoBridgeStatus.ACTIVATED:
            return MTProxySecretSyncResult(
                status=MTProtoBridgeStatus.REVOKED,
                active_count=result.active_count,
                manifest_fingerprint=result.manifest_fingerprint,
                assignment_id=result.assignment_id,
                failure_code=result.failure_code,
                safe_message=result.safe_message,
                applied_at=result.applied_at,
            )
        return result
        # END_BLOCK_REVOKE_ASSIGNMENT

    async def runtime_health(self) -> MTProtoRuntimeHealth:
        # START_BLOCK_RUNTIME_HEALTH
        return await self.adapter.health()
        # END_BLOCK_RUNTIME_HEALTH
