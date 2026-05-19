"""MTProto promotion tag control.

# FILE: backend/app/mtproto/promotion_tag.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Validate, store, mask, and report Telegram MTProxy promotion tag state safely
#   SCOPE: 32-hex tag validation, redacted admin state, audit-safe updates, and pending-restart runtime semantics
#   DEPENDS: M-001 (DB/config), M-047 (admin MTProto ops), M-059 (promotion tag control)
#   LINKS: M-059, V-M-059
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MTProtoPromotionTagState - Stored promotion tag control row
#   MTProtoPromotionTagError - Safe validation/update exception
#   validate_promotion_tag - Accept exact 32-hex tag or zero fallback
#   mask_promotion_tag - Return masked tag representation for API/UI/audit
#   get_promotion_tag_state - Load or initialize safe tag state
#   update_promotion_tag - Confirm, validate, store, and return masked runtime state
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-42 MTProxyBot promotion tag control
# END_CHANGE_SUMMARY
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re

from loguru import logger
from sqlalchemy import Column, DateTime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Field, SQLModel, select

from app.core.config import Settings, settings


ZERO_PROMOTION_TAG = "00000000000000000000000000000000"


# START_BLOCK_PROMOTION_TAG_TYPES
class MTProtoPromotionTagError(ValueError):
    """Safe promotion tag error; message never contains the submitted tag."""


class MTProtoPromotionTagState(SQLModel, table=True):
    """Single-row storage for operator-managed MTProxy promotion tag."""

    __tablename__ = "mtproto_promotion_tag_state"

    id: int | None = Field(default=None, primary_key=True)
    tag_value: str = Field(default=ZERO_PROMOTION_TAG, max_length=32)
    tag_masked: str = Field(default="0000...0000", max_length=20)
    tag_hash: str = Field(default="", max_length=64)
    source: str = Field(default="env", max_length=40)
    runtime_status: str = Field(default="applied", max_length=40)
    pending_restart: bool = Field(default=False, index=True)
    updated_by_admin_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
# END_BLOCK_PROMOTION_TAG_TYPES


# START_BLOCK_PROMOTION_TAG_HELPERS
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def validate_promotion_tag(value: str | None) -> str:
    """Validate an exact Telegram MTProxy promotion tag."""
    logger.info("[M-059][validate_promotion_tag][VALIDATE_TAG] started")
    if value is None:
        raise MTProtoPromotionTagError("Promotion tag is required")
    if value != value.strip():
        raise MTProtoPromotionTagError("Promotion tag must not contain surrounding whitespace")
    normalized = value.lower()
    if not re.fullmatch(r"[0-9a-f]{32}", normalized):
        raise MTProtoPromotionTagError("Promotion tag must be exactly 32 lowercase or uppercase hex characters")
    return normalized


def mask_promotion_tag(value: str | None) -> str:
    """Return an audit/API/UI safe tag representation."""
    try:
        normalized = validate_promotion_tag(value)
    except MTProtoPromotionTagError:
        return "invalid"
    return f"{normalized[:4]}...{normalized[-4:]}"


def _hash_tag(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _settings_tag(app_settings: Settings) -> str:
    raw_value = getattr(app_settings, "mtproto_ad_tag", ZERO_PROMOTION_TAG)
    return validate_promotion_tag(raw_value or ZERO_PROMOTION_TAG)


def _apply_promotion_tag(
    tag_value: str,
    *,
    app_settings: Settings,
) -> tuple[str, bool]:
    settings_value = _settings_tag(app_settings)
    if tag_value == settings_value:
        runtime_status = "applied"
        pending_restart = False
    else:
        runtime_status = "pending_restart"
        pending_restart = True
    logger.info(
        "[M-059][apply_promotion_tag][RUNTIME_STATE] "
        f"status={runtime_status} pending_restart={pending_restart}"
    )
    return runtime_status, pending_restart


def safe_promotion_tag_state(row: MTProtoPromotionTagState) -> dict[str, object]:
    """Return admin-safe promotion tag state."""
    payload = {
        "masked_tag": row.tag_masked,
        "source": row.source,
        "runtime_status": row.runtime_status,
        "pending_restart": row.pending_restart,
        "updated_by_admin_id": row.updated_by_admin_id,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    logger.info(
        "[M-059][promotion_tag_state][REDACTED_STATE] "
        f"status={row.runtime_status} pending_restart={row.pending_restart}"
    )
    return payload
# END_BLOCK_PROMOTION_TAG_HELPERS


# START_CONTRACT: get_promotion_tag_state
#   PURPOSE: Load or initialize masked promotion tag state
#   INPUTS: session: AsyncSession; app_settings: Settings
#   OUTPUTS: MTProtoPromotionTagState
#   SIDE_EFFECTS: May insert the singleton state row from validated env fallback
#   LINKS: M-059, V-M-059
# END_CONTRACT: get_promotion_tag_state
# START_BLOCK_GET_PROMOTION_TAG_STATE
async def get_promotion_tag_state(
    session: AsyncSession,
    *,
    app_settings: Settings = settings,
) -> MTProtoPromotionTagState:
    """Load the singleton promotion tag state, initializing from env if needed."""
    result = await session.execute(select(MTProtoPromotionTagState).where(MTProtoPromotionTagState.id == 1))
    row = result.scalar_one_or_none()
    if row is not None:
        return row

    tag_value = _settings_tag(app_settings)
    runtime_status, pending_restart = _apply_promotion_tag(tag_value, app_settings=app_settings)
    row = MTProtoPromotionTagState(
        id=1,
        tag_value=tag_value,
        tag_masked=mask_promotion_tag(tag_value),
        tag_hash=_hash_tag(tag_value),
        source="env",
        runtime_status=runtime_status,
        pending_restart=pending_restart,
    )
    session.add(row)
    await session.flush()
    return row
# END_BLOCK_GET_PROMOTION_TAG_STATE


# START_CONTRACT: update_promotion_tag
#   PURPOSE: Validate and store a new promotion tag after explicit admin confirmation
#   INPUTS: session, admin_id, tag_value, confirm, app_settings
#   OUTPUTS: MTProtoPromotionTagState
#   SIDE_EFFECTS: DB write and redacted log marker, no proxy link rotation
#   LINKS: M-059, V-M-059
# END_CONTRACT: update_promotion_tag
# START_BLOCK_UPDATE_PROMOTION_TAG
async def update_promotion_tag(
    session: AsyncSession,
    *,
    admin_id: int,
    tag_value: str | None,
    confirm: bool,
    app_settings: Settings = settings,
) -> MTProtoPromotionTagState:
    """Validate and store a new tag without exposing the full value."""
    if not confirm:
        raise MTProtoPromotionTagError("Explicit promotion tag confirmation required")
    normalized = validate_promotion_tag(tag_value)
    row = await get_promotion_tag_state(session, app_settings=app_settings)
    runtime_status, pending_restart = _apply_promotion_tag(normalized, app_settings=app_settings)
    row.tag_value = normalized
    row.tag_masked = mask_promotion_tag(normalized)
    row.tag_hash = _hash_tag(normalized)
    row.source = "admin"
    row.runtime_status = runtime_status
    row.pending_restart = pending_restart
    row.updated_by_admin_id = admin_id
    row.updated_at = _utcnow()
    logger.info(
        "[M-059][update_promotion_tag][AUDIT_UPDATE] "
        f"admin_id={admin_id} status={runtime_status} pending_restart={pending_restart}"
    )
    await session.flush()
    return row
# END_BLOCK_UPDATE_PROMOTION_TAG
