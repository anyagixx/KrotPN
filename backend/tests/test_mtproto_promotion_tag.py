"""MTProto promotion tag tests.

# FILE: backend/tests/test_mtproto_promotion_tag.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify MTProxy promotion tag validation, masking, storage, and pending-restart semantics
#   SCOPE: Valid/invalid tags, zero fallback, safe admin state, and runtime status without link rotation
#   DEPENDS: M-059, M-001
#   LINKS: V-M-059
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   test_validate_promotion_tag_accepts_hex_and_rejects_malformed_values - Covers parser rules
#   test_promotion_tag_state_masks_full_value_and_marks_pending_restart - Covers DB state/update
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-42 promotion tag tests
# END_CHANGE_SUMMARY
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.mtproto.promotion_tag import (
    MTProtoPromotionTagError,
    get_promotion_tag_state,
    mask_promotion_tag,
    safe_promotion_tag_state,
    update_promotion_tag,
    validate_promotion_tag,
)


# START_BLOCK_PROMOTION_TAG_TESTS
def test_validate_promotion_tag_accepts_hex_and_rejects_malformed_values():
    assert validate_promotion_tag("ABCDEFabcdef12345678901234567890") == "abcdefabcdef12345678901234567890"
    assert validate_promotion_tag("00000000000000000000000000000000") == "00000000000000000000000000000000"
    assert mask_promotion_tag("1234567890abcdef1234567890abcdef") == "1234...cdef"

    for value in ["", " 1234567890abcdef1234567890abcdef", "not-hex", "abc", "g" * 32]:
        with pytest.raises(MTProtoPromotionTagError):
            validate_promotion_tag(value)


@pytest.mark.asyncio
async def test_promotion_tag_state_masks_full_value_and_marks_pending_restart(db_session: AsyncSession):
    settings = Settings(
        secret_key="test-secret-key-with-enough-length",
        mtproto_ad_tag="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    )

    initial = await get_promotion_tag_state(db_session, app_settings=settings)
    initial_payload = safe_promotion_tag_state(initial)
    updated = await update_promotion_tag(
        db_session,
        admin_id=42,
        tag_value="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        confirm=True,
        app_settings=settings,
    )
    payload = safe_promotion_tag_state(updated)

    assert initial_payload["masked_tag"] == "bbbb...bbbb"
    assert payload["masked_tag"] == "aaaa...aaaa"
    assert payload["runtime_status"] == "pending_restart"
    assert payload["pending_restart"] is True
    assert "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" not in str(payload)
    with pytest.raises(MTProtoPromotionTagError):
        await update_promotion_tag(
            db_session,
            admin_id=42,
            tag_value="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            confirm=False,
            app_settings=settings,
        )
# END_BLOCK_PROMOTION_TAG_TESTS
