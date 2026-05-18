"""MTProto personal proxy provisioning.

# FILE: backend/app/mtproto/provisioning.py
# VERSION: 2.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Generate official personal MTProxy assignments and owner-safe payloads
#   SCOPE: SNI identity generation, legacy fake-TLS helper compatibility, official secure secret link assembly,
#          idempotent issue/reissue policy, live official MTProxy manifest apply
#   DEPENDS: M-001 (settings), M-002 (User), M-042 (assignment repository), M-053 (official secret sync)
#   LINKS: M-043, M-053, V-M-043, V-M-053
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MTProtoProvisioningErrorCode, MTProtoProvisioningError - Stable safe failure contract
#   generate_sni - Deterministic wildcard-safe SNI generation
#   derive_fake_tls_secret - Legacy KPprotoN-compatible per-SNI fake-TLS secret derivation
#   build_tg_link - Generic Telegram tg://proxy link assembly
#   MTProtoProvisioningService - Idempotent owner-safe issue/reissue service with live policy activation
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.0.0 - Switched owner payloads to official MTProxy secure dd secrets and manifest sync.
#   LAST_CHANGE: v1.1.0 - Apply issued assignments to the live MTProto runtime before returning activated owner payloads.
#   LAST_CHANGE: v1.0.0 - Added Phase-29 MTProto provisioning core
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

import hashlib
import re
from enum import Enum
from urllib.parse import urlencode

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.mtproto.models import MTProtoAssignment, MTProtoAssignmentStatus, MTProtoCredentialMode
from app.mtproto.official_secrets import (
    MTProxySecretSyncService,
    build_official_tg_link,
    build_secure_secret,
    derive_official_secret,
)
from app.mtproto.repository import MTProtoAssignmentRepository
from app.mtproto.runtime_bridge import MTProtoBridgeStatus
from app.mtproto.schemas import MTProtoProxyPayload
from app.users.models import User


SNI_HASH_LEN = 12
MAX_SNI_COLLISION_ATTEMPTS = 20


# START_BLOCK_PROVISIONING_TYPES
class MTProtoProvisioningErrorCode(str, Enum):
    """Stable MTProto provisioning failure codes."""

    USER_NOT_VERIFIED = "user_not_verified"
    CONFIG_INCOMPLETE = "config_incomplete"
    INVALID_SECRET = "invalid_secret"
    INVALID_SNI = "invalid_sni"
    SNI_COLLISION = "sni_collision"
    REISSUE_REQUIRED = "reissue_required"


class MTProtoProvisioningError(ValueError):
    """Typed safe exception for MTProto provisioning failures."""

    def __init__(self, code: MTProtoProvisioningErrorCode, safe_message: str) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
# END_BLOCK_PROVISIONING_TYPES


# START_CONTRACT: generate_sni
#   PURPOSE: Generate a stable wildcard-safe SNI under the configured base domain
#   INPUTS: user_key: str; base_domain: str; prefix: str; collision_nonce: int
#   OUTPUTS: str
#   SIDE_EFFECTS: none
#   LINKS: M-043, V-M-043
# END_CONTRACT: generate_sni
# START_BLOCK_GENERATE_SNI
def generate_sni(
    user_key: str,
    *,
    base_domain: str,
    prefix: str = "u",
    collision_nonce: int = 0,
) -> str:
    """Generate deterministic SNI using a 12-hex SHA-256 prefix."""
    normalized_domain = _normalize_base_domain(base_domain)
    normalized_prefix = _normalize_sni_prefix(prefix)
    material = f"{user_key}:{collision_nonce}" if collision_nonce else user_key
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:SNI_HASH_LEN]
    label = f"{normalized_prefix}-{digest}" if normalized_prefix else digest
    sni = f"{label}.{normalized_domain}"
    _validate_sni(sni, normalized_domain)
    logger.info(f"[M-043][issue_user_proxy][GENERATE_SNI] sni_prefix={normalized_prefix}")
    return sni
# END_BLOCK_GENERATE_SNI


# START_CONTRACT: derive_fake_tls_secret
#   PURPOSE: Build KPprotoN-compatible fake-TLS secret bound to SNI
#   INPUTS: base_secret_hex: str; secret_salt: str; sni: str
#   OUTPUTS: str
#   SIDE_EFFECTS: none
#   LINKS: M-043, V-M-043
# END_CONTRACT: derive_fake_tls_secret
# START_BLOCK_DERIVE_SECRET
def derive_fake_tls_secret(base_secret_hex: str, secret_salt: str, sni: str) -> str:
    """Derive Telegram fake-TLS hex secret from salt, base secret and SNI."""
    normalized_secret = _normalize_hex_secret(base_secret_hex)
    normalized_salt = _normalize_hex_salt(secret_salt)
    normalized_sni = sni.strip().lower().rstrip(".")
    derived = hashlib.sha256(
        (normalized_salt + normalized_secret + normalized_sni).encode("utf-8")
    ).digest()[:16]
    logger.info(
        f"[M-043][derive_fake_tls_secret][GOLDEN_VECTOR] sni_length={len(normalized_sni)}"
    )
    return "ee" + derived.hex() + normalized_sni.encode("utf-8").hex()
# END_BLOCK_DERIVE_SECRET


# START_CONTRACT: build_tg_link
#   PURPOSE: Assemble owner-safe tg://proxy link from server, port and derived secret
#   INPUTS: server: str; port: int; secret: str
#   OUTPUTS: str
#   SIDE_EFFECTS: none
#   LINKS: M-043, V-M-043
# END_CONTRACT: build_tg_link
# START_BLOCK_BUILD_TG_LINK
def build_tg_link(server: str, port: int, secret: str) -> str:
    """Build a Telegram proxy deep link."""
    query = urlencode({"server": server, "port": str(port), "secret": secret})
    return f"tg://proxy?{query}"
# END_BLOCK_BUILD_TG_LINK


class MTProtoProvisioningService:
    """Issue and reissue personal MTProto proxy payloads."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        app_settings: Settings = settings,
        repository: MTProtoAssignmentRepository | None = None,
    ) -> None:
        self.session = session
        self.settings = app_settings
        self.repository = repository or MTProtoAssignmentRepository(session)

    # START_CONTRACT: issue_user_proxy
    #   PURPOSE: Create or reuse one verified user's canonical MTProto assignment
    #   INPUTS: user: User; reissue: bool
    #   OUTPUTS: MTProtoProxyPayload
    #   SIDE_EFFECTS: writes assignment metadata without persisting raw secrets or tg links
    #   LINKS: M-042, M-043, V-M-043
    # END_CONTRACT: issue_user_proxy
    # START_BLOCK_ISSUE_USER_PROXY
    async def issue_user_proxy(self, user: User, *, reissue: bool = False) -> MTProtoProxyPayload:
        """Issue or reuse an owner-safe MTProto proxy payload."""
        self._ensure_verified_user(user)
        self._ensure_runtime_config()

        user_id = int(user.id)
        existing = await self.repository.get_user_assignment(user_id)
        if existing is not None:
            if self._assignment_requires_reissue(existing) and not reissue:
                logger.warning(
                    "[M-043][issue_user_proxy][REISSUE_REQUIRED] "
                    f"user_id={user_id} assignment_id={existing.id}"
                )
                raise MTProtoProvisioningError(
                    MTProtoProvisioningErrorCode.REISSUE_REQUIRED,
                    "MTProto proxy link must be reissued",
                )
            if not reissue and existing.status == MTProtoAssignmentStatus.ACTIVE:
                logger.info(
                    "[M-043][issue_user_proxy][REUSE_ASSIGNMENT] "
                    f"user_id={user_id} assignment_id={existing.id}"
                )
                await self._apply_runtime_policy(existing)
                return self._payload_from_assignment(existing)
            return await self._reissue_existing(user_id, existing)

        assignment = await self._create_assignment(user_id)
        await self._apply_runtime_policy(assignment)
        return self._payload_from_assignment(assignment)
    # END_BLOCK_ISSUE_USER_PROXY

    # START_BLOCK_ASSIGNMENT_CREATE_REISSUE
    async def _create_assignment(self, user_id: int) -> MTProtoAssignment:
        for collision_nonce in range(MAX_SNI_COLLISION_ATTEMPTS):
            sni = generate_sni(
                f"user:{user_id}",
                base_domain=self.settings.mtproto_base_domain,
                prefix=self.settings.mtproto_sni_prefix,
                collision_nonce=collision_nonce,
            )
            existing_for_sni = await self.repository.get_assignment_by_sni(sni)
            if existing_for_sni is not None and existing_for_sni.user_id != user_id:
                continue
            logger.info(f"[M-043][issue_user_proxy][PERSIST_ASSIGNMENT] user_id={user_id}")
            return await self.repository.save_assignment(
                user_id=user_id,
                sni=sni,
                credential_mode=MTProtoCredentialMode.OFFICIAL_SECURE,
                rotation_marker=self.settings.mtproto_rotation_marker,
            )

        raise MTProtoProvisioningError(
            MTProtoProvisioningErrorCode.SNI_COLLISION,
            "MTProto SNI assignment could not be generated",
        )

    async def _reissue_existing(
        self,
        user_id: int,
        assignment: MTProtoAssignment,
    ) -> MTProtoProxyPayload:
        logger.info(
            "[M-043][issue_user_proxy][PERSIST_ASSIGNMENT] "
            f"user_id={user_id} assignment_id={assignment.id}"
        )
        updated = await self.repository.save_assignment(
            user_id=user_id,
            sni=assignment.sni,
            credential_mode=MTProtoCredentialMode.OFFICIAL_SECURE,
            status=MTProtoAssignmentStatus.ACTIVE,
            rotation_marker=self.settings.mtproto_rotation_marker,
            replace=True,
        )
        await self._apply_runtime_policy(updated)
        return self._payload_from_assignment(updated)
    # END_BLOCK_ASSIGNMENT_CREATE_REISSUE

    # START_BLOCK_APPLY_RUNTIME_POLICY
    async def _apply_runtime_policy(self, assignment: MTProtoAssignment) -> None:
        sync_service = MTProxySecretSyncService(self.session, app_settings=self.settings)
        result = await sync_service.apply_assignment_secret(assignment)
        if result.status == MTProtoBridgeStatus.ACTIVATED:
            return
        logger.warning(
            "[M-043][issue_user_proxy][REISSUE_REQUIRED] "
            f"assignment_id={assignment.id} runtime_status={result.status.value} "
            f"failure_code={result.failure_code.value if result.failure_code else 'unknown'}"
        )
        raise MTProtoProvisioningError(
            MTProtoProvisioningErrorCode.CONFIG_INCOMPLETE,
            "MTProto runtime policy is not ready",
        )
    # END_BLOCK_APPLY_RUNTIME_POLICY

    # START_BLOCK_VALIDATE_PROVISIONING_INPUTS
    def _ensure_verified_user(self, user: User) -> None:
        if user.id is None or not user.is_active or not user.email_verified:
            logger.warning(f"[M-043][issue_user_proxy][REJECT_UNVERIFIED_USER] user_id={user.id}")
            raise MTProtoProvisioningError(
                MTProtoProvisioningErrorCode.USER_NOT_VERIFIED,
                "Verified user is required for MTProto proxy issuance",
            )

    def _ensure_runtime_config(self) -> None:
        if not self.settings.mtproto_base_secret_hex or not self.settings.mtproto_secret_salt:
            raise MTProtoProvisioningError(
                MTProtoProvisioningErrorCode.CONFIG_INCOMPLETE,
                "MTProto provisioning settings are incomplete",
            )
    # END_BLOCK_VALIDATE_PROVISIONING_INPUTS

    # START_BLOCK_BUILD_OWNER_SAFE_PAYLOAD
    def _payload_from_assignment(self, assignment: MTProtoAssignment) -> MTProtoProxyPayload:
        if assignment.credential_mode != MTProtoCredentialMode.OFFICIAL_SECURE:
            logger.warning(
                "[M-043][issue_user_proxy][REISSUE_REQUIRED] "
                f"assignment_id={assignment.id} credential_mode={assignment.credential_mode.value}"
            )
            raise MTProtoProvisioningError(
                MTProtoProvisioningErrorCode.REISSUE_REQUIRED,
                "MTProto proxy link must be reissued",
            )
        logger.info(f"[M-043][issue_user_proxy][DERIVE_SECRET] assignment_id={assignment.id}")
        raw_secret = derive_official_secret(
            self.settings.mtproto_base_secret_hex or "",
            self.settings.mtproto_secret_salt or "",
            assignment,
        )
        secret = build_secure_secret(raw_secret)
        public_server = self.settings.edge_public_domain or self.settings.mtproto_base_domain
        link = build_official_tg_link(public_server, self.settings.mtproto_proxy_port, raw_secret)
        return MTProtoProxyPayload(
            assignment_id=int(assignment.id),
            server=public_server,
            port=self.settings.mtproto_proxy_port,
            secret=secret,
            tg_link=link,
            sni=assignment.sni,
            credential_mode=assignment.credential_mode.value,
            rotation_marker=assignment.rotation_marker,
            reissue_required=False,
        )

    def _assignment_requires_reissue(self, assignment: MTProtoAssignment) -> bool:
        return (
            assignment.rotation_marker != self.settings.mtproto_rotation_marker
            or assignment.status == MTProtoAssignmentStatus.REISSUE_REQUIRED
            or assignment.credential_mode != MTProtoCredentialMode.OFFICIAL_SECURE
        )
    # END_BLOCK_BUILD_OWNER_SAFE_PAYLOAD


# START_BLOCK_VALIDATION_HELPERS
def _normalize_base_domain(base_domain: str) -> str:
    normalized = base_domain.strip().lower().lstrip("*.").rstrip(".")
    if not normalized or "/" in normalized or ":" in normalized:
        raise MTProtoProvisioningError(
            MTProtoProvisioningErrorCode.INVALID_SNI,
            "MTProto base domain is invalid",
        )
    return normalized


def _normalize_sni_prefix(prefix: str) -> str:
    normalized = prefix.strip().lower().strip("-")
    if normalized and not re.fullmatch(r"[a-z0-9-]{1,24}", normalized):
        raise MTProtoProvisioningError(
            MTProtoProvisioningErrorCode.INVALID_SNI,
            "MTProto SNI prefix is invalid",
        )
    return normalized


def _validate_sni(sni: str, base_domain: str) -> None:
    if not sni.endswith(f".{base_domain}"):
        raise MTProtoProvisioningError(
            MTProtoProvisioningErrorCode.INVALID_SNI,
            "MTProto SNI must be under the configured base domain",
        )
    if len(sni) > 253:
        raise MTProtoProvisioningError(
            MTProtoProvisioningErrorCode.INVALID_SNI,
            "MTProto SNI is too long",
        )
    for label in sni.split("."):
        if len(label) > 63 or not re.fullmatch(r"[a-z0-9-]+", label):
            raise MTProtoProvisioningError(
                MTProtoProvisioningErrorCode.INVALID_SNI,
                "MTProto SNI contains an invalid DNS label",
            )


def _normalize_hex_secret(secret_hex: str) -> str:
    normalized = secret_hex.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{32}", normalized):
        raise MTProtoProvisioningError(
            MTProtoProvisioningErrorCode.INVALID_SECRET,
            "MTProto base secret must be 32 hex characters",
        )
    return normalized


def _normalize_hex_salt(secret_salt: str) -> str:
    normalized = secret_salt.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{32}", normalized):
        raise MTProtoProvisioningError(
            MTProtoProvisioningErrorCode.INVALID_SECRET,
            "MTProto secret salt must be 32 hex characters",
        )
    return normalized
# END_BLOCK_VALIDATION_HELPERS
