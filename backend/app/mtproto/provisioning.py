"""MTProto personal proxy provisioning.

# FILE: backend/app/mtproto/provisioning.py
# VERSION: 2.2.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Generate KPprotoN personal fake-TLS assignments and owner-safe payloads with CTA hostnames
#   SCOPE: CTA SNI identity generation, legacy SNI preservation, per-SNI fake-TLS secret derivation,
#          Telegram link assembly, idempotent issue/reissue policy, live KPprotoN policy apply
#   DEPENDS: M-001 (settings), M-002 (User), M-042 (assignment repository), M-044 (runtime bridge)
#   LINKS: M-043, M-044, M-065, V-M-043, V-M-044, V-M-065
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MTProtoProvisioningErrorCode, MTProtoProvisioningError - Stable safe failure contract
#   MTPROTO_CTA_PREFIXES - Fixed marketing CTA prefix allow-list for new assignments
#   shorten_public_user_id - Derive a non-raw 7-hex public user suffix
#   select_cta_prefix - Validate explicit prefixes or choose a stable pseudo-random CTA prefix
#   generate_cta_sni - Build wildcard-safe CTA SNI for newly issued assignments
#   generate_sni - Legacy deterministic wildcard-safe SNI generation helper
#   derive_fake_tls_secret - Legacy KPprotoN-compatible per-SNI fake-TLS secret derivation
#   build_tg_link - Generic Telegram tg://proxy link assembly
#   MTProtoProvisioningService - Idempotent owner-safe issue/reissue service with live policy activation
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.2.0 - Added Phase-47 CTA subdomain SNI generation for new MTProto assignments.
#   LAST_CHANGE: v2.1.0 - Restored KPprotoN derived-per-SNI fake-TLS issuance as the production path.
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
from app.mtproto.repository import MTProtoAssignmentRepository
from app.mtproto.runtime_bridge import MTProtoBridgeStatus, MTProtoRuntimeBridge
from app.mtproto.schemas import MTProtoProxyPayload
from app.users.models import User


SNI_HASH_LEN = 12
PUBLIC_SHORT_ID_LEN = 7
MAX_SNI_COLLISION_ATTEMPTS = 20
MTPROTO_CTA_PREFIXES: tuple[str, ...] = (
    "kupi-vpn",
    "vpn-tut",
    "beri-vpn",
    "bez-blokirovok",
    "hochu-bystree",
    "krot-vpn",
)
CTA_PREFIX_HASH_SALT = "krotpn-mtproto-cta-prefix"
PUBLIC_ID_HASH_SALT = "krotpn-mtproto-public-id"


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


# START_CONTRACT: shorten_public_user_id
#   PURPOSE: Derive a compact public 7-hex user suffix without exposing numeric IDs
#   INPUTS: user_key: str|int; collision_nonce: int
#   OUTPUTS: str
#   SIDE_EFFECTS: none
#   LINKS: M-065, V-M-065
# END_CONTRACT: shorten_public_user_id
# START_BLOCK_CTA_PUBLIC_ID
def shorten_public_user_id(user_key: str | int, *, collision_nonce: int = 0) -> str:
    """Return a public 7-hex suffix for CTA MTProto hostnames."""
    if collision_nonce < 0:
        raise MTProtoProvisioningError(
            MTProtoProvisioningErrorCode.INVALID_SNI,
            "MTProto SNI collision nonce is invalid",
        )

    normalized_key = _normalize_public_user_key(user_key)
    compact_hex = normalized_key.replace("-", "")
    if (
        collision_nonce == 0
        and not normalized_key.isdigit()
        and re.fullmatch(r"[0-9a-f]+", compact_hex)
        and len(compact_hex) >= PUBLIC_SHORT_ID_LEN
    ):
        return compact_hex[:PUBLIC_SHORT_ID_LEN]

    material = f"{PUBLIC_ID_HASH_SALT}:{normalized_key}:{collision_nonce}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:PUBLIC_SHORT_ID_LEN]
# END_BLOCK_CTA_PUBLIC_ID


# START_CONTRACT: select_cta_prefix
#   PURPOSE: Select an approved CTA prefix either explicitly or by stable pseudo-random rotation
#   INPUTS: user_key: str|int; explicit_prefix: str|None
#   OUTPUTS: str
#   SIDE_EFFECTS: none
#   LINKS: M-065, V-M-065
# END_CONTRACT: select_cta_prefix
# START_BLOCK_CTA_PREFIX_SELECTION
def select_cta_prefix(user_key: str | int, *, explicit_prefix: str | None = None) -> str:
    """Return an approved CTA prefix for a user-bound MTProto hostname."""
    if explicit_prefix is not None:
        return _validate_cta_prefix(explicit_prefix)

    normalized_key = _normalize_public_user_key(user_key)
    digest = hashlib.sha256(
        f"{CTA_PREFIX_HASH_SALT}:{normalized_key}".encode("utf-8")
    ).hexdigest()
    index = int(digest[:8], 16) % len(MTPROTO_CTA_PREFIXES)
    return MTPROTO_CTA_PREFIXES[index]
# END_BLOCK_CTA_PREFIX_SELECTION


# START_CONTRACT: generate_cta_sni
#   PURPOSE: Generate a wildcard-safe CTA SNI under the configured base domain
#   INPUTS: user_key: str|int; base_domain: str; prefix: str|None; collision_nonce: int
#   OUTPUTS: str
#   SIDE_EFFECTS: secret-free log markers
#   LINKS: M-065, M-043, V-M-065
# END_CONTRACT: generate_cta_sni
# START_BLOCK_GENERATE_CTA_SNI
def generate_cta_sni(
    user_key: str | int,
    *,
    base_domain: str,
    prefix: str | None = None,
    collision_nonce: int = 0,
) -> str:
    """Generate a CTA hostname like kupi-vpn-4bb40fa.krotpn.xyz."""
    normalized_domain = _normalize_base_domain(base_domain)
    selected_prefix = select_cta_prefix(user_key, explicit_prefix=prefix)
    public_short_id = shorten_public_user_id(user_key, collision_nonce=collision_nonce)
    label = f"{selected_prefix}-{public_short_id}"
    sni = f"{label}.{normalized_domain}"
    _validate_cta_sni(sni, normalized_domain)
    logger.info(
        "[M-065][generate_cta_sni][CTA_PREFIX] "
        f"prefix={selected_prefix} collision_nonce={collision_nonce}"
    )
    logger.info(
        "[M-065][generate_cta_sni][PUBLIC_SHORT_ID] "
        f"public_short_id={public_short_id}"
    )
    logger.info(f"[M-043][issue_user_proxy][GENERATE_SNI] sni_prefix={selected_prefix}")
    return sni
# END_BLOCK_GENERATE_CTA_SNI


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
    async def issue_user_proxy(
        self,
        user: User,
        *,
        reissue: bool = False,
        cta_prefix: str | None = None,
    ) -> MTProtoProxyPayload:
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
                if _is_legacy_u_sni(existing.sni, self.settings.mtproto_base_domain):
                    logger.info(
                        "[M-065][phase47_mtproto_cta_links][LEGACY_PRESERVE] "
                        f"user_id={user_id} assignment_id={existing.id}"
                    )
                await self._apply_runtime_policy(existing)
                return self._payload_from_assignment(existing)
            return await self._reissue_existing(user_id, existing)

        assignment = await self._create_assignment(user_id, cta_prefix=cta_prefix)
        await self._apply_runtime_policy(assignment)
        return self._payload_from_assignment(assignment)
    # END_BLOCK_ISSUE_USER_PROXY

    # START_BLOCK_ASSIGNMENT_CREATE_REISSUE
    async def _create_assignment(
        self,
        user_id: int,
        *,
        cta_prefix: str | None = None,
    ) -> MTProtoAssignment:
        for collision_nonce in range(MAX_SNI_COLLISION_ATTEMPTS):
            sni = generate_cta_sni(
                str(user_id),
                base_domain=self.settings.mtproto_base_domain,
                prefix=cta_prefix,
                collision_nonce=collision_nonce,
            )
            existing_for_sni = await self.repository.get_assignment_by_sni(sni)
            if existing_for_sni is not None and existing_for_sni.user_id != user_id:
                continue
            logger.info(
                "[M-065][issue_user_proxy][CTA_ASSIGNMENT] "
                f"user_id={user_id} sni={sni}"
            )
            logger.info(f"[M-043][issue_user_proxy][PERSIST_ASSIGNMENT] user_id={user_id}")
            return await self.repository.save_assignment(
                user_id=user_id,
                sni=sni,
                credential_mode=MTProtoCredentialMode.DERIVED_PER_SNI,
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
            credential_mode=MTProtoCredentialMode.DERIVED_PER_SNI,
            status=MTProtoAssignmentStatus.ACTIVE,
            rotation_marker=self.settings.mtproto_rotation_marker,
            replace=True,
        )
        await self._apply_runtime_policy(updated)
        return self._payload_from_assignment(updated)
    # END_BLOCK_ASSIGNMENT_CREATE_REISSUE

    # START_BLOCK_APPLY_RUNTIME_POLICY
    async def _apply_runtime_policy(self, assignment: MTProtoAssignment) -> None:
        bridge = MTProtoRuntimeBridge(self.session)
        result = await bridge.apply_domain_policy(assignment)
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
        if assignment.credential_mode != MTProtoCredentialMode.DERIVED_PER_SNI:
            logger.warning(
                "[M-043][issue_user_proxy][REISSUE_REQUIRED] "
                f"assignment_id={assignment.id} credential_mode={assignment.credential_mode.value}"
            )
            raise MTProtoProvisioningError(
                MTProtoProvisioningErrorCode.REISSUE_REQUIRED,
                "MTProto proxy link must be reissued",
            )
        logger.info(f"[M-043][issue_user_proxy][DERIVE_SECRET] assignment_id={assignment.id}")
        secret = derive_fake_tls_secret(
            self.settings.mtproto_base_secret_hex or "",
            self.settings.mtproto_secret_salt or "",
            assignment.sni,
        )
        link = build_tg_link(assignment.sni, self.settings.mtproto_proxy_port, secret)
        return MTProtoProxyPayload(
            assignment_id=int(assignment.id),
            server=assignment.sni,
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
            or assignment.credential_mode != MTProtoCredentialMode.DERIVED_PER_SNI
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


def _normalize_public_user_key(user_key: str | int) -> str:
    normalized = str(user_key).strip().lower()
    if not normalized:
        raise MTProtoProvisioningError(
            MTProtoProvisioningErrorCode.INVALID_SNI,
            "MTProto public user key is invalid",
        )
    return normalized


def _validate_cta_prefix(prefix: str) -> str:
    if prefix not in MTPROTO_CTA_PREFIXES:
        raise MTProtoProvisioningError(
            MTProtoProvisioningErrorCode.INVALID_SNI,
            "MTProto CTA prefix is not allowed",
        )
    return prefix


def _validate_cta_sni(sni: str, base_domain: str) -> None:
    _validate_sni(sni, base_domain)
    suffix = f".{base_domain}"
    label = sni[: -len(suffix)]
    if "." in label or not label:
        raise MTProtoProvisioningError(
            MTProtoProvisioningErrorCode.INVALID_SNI,
            "MTProto CTA SNI must use one wildcard label",
        )

    matching_prefix = None
    for allowed_prefix in MTPROTO_CTA_PREFIXES:
        if label.startswith(f"{allowed_prefix}-"):
            matching_prefix = allowed_prefix
            break
    public_part = label[len(matching_prefix) + 1 :] if matching_prefix else ""
    if matching_prefix is None or not re.fullmatch(r"[0-9a-f]{7}", public_part):
        raise MTProtoProvisioningError(
            MTProtoProvisioningErrorCode.INVALID_SNI,
            "MTProto CTA SNI label is invalid",
        )


def _is_legacy_u_sni(sni: str, base_domain: str) -> bool:
    normalized_domain = _normalize_base_domain(base_domain)
    suffix = f".{normalized_domain}"
    normalized_sni = sni.strip().lower().rstrip(".")
    if not normalized_sni.endswith(suffix):
        return False
    label = normalized_sni[: -len(suffix)]
    return re.fullmatch(r"u-[0-9a-f]{12}", label) is not None


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
