"""MTProto provisioning core tests.

# FILE: backend/tests/test_mtproto_provisioning.py
# VERSION: 1.1.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify deterministic owner-safe MTProto proxy provisioning
#   SCOPE: SNI generation, KPprotoN fake-TLS vectors, idempotent issuance,
#          reissue, and verified-user guard
#   DEPENDS: M-043, M-042, M-001, M-002
#   LINKS: V-M-043, V-M-042, V-M-001
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   test_generate_sni_is_stable_and_under_base_domain - Covers stable SNI generation
#   test_derive_fake_tls_secret_matches_kpproton_vector - Covers fake-TLS derivation
#   test_issue_user_proxy_is_idempotent_and_owner_safe - Covers owner payload assembly
#   test_issue_user_proxy_rejects_unverified_user_without_assignment - Covers verified gate
#   test_rotation_marker_requires_explicit_reissue - Covers reissue-required policy
#   test_blank_mtproto_secrets_are_treated_as_missing_config - Covers blank env normalization
#   test_incomplete_runtime_config_is_rejected - Covers safe config failure
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.1.0 - Added regression coverage for blank MTProto env values from fresh deploys
#   LAST_CHANGE: v1.0.0 - Added Phase-29 provisioning tests
# END_CHANGE_SUMMARY
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.mtproto.models import MTProtoAssignment
from app.mtproto.service import (
    MTProtoProvisioningError,
    MTProtoProvisioningErrorCode,
    MTProtoProvisioningService,
    derive_fake_tls_secret,
    generate_sni,
)
from app.users.models import User


BASE_SECRET = "0123456789abcdef0123456789abcdef"
SECRET_SALT = "abcdef0123456789abcdef0123456789"


# START_BLOCK_FIXTURES
def _settings(**overrides) -> Settings:
    values = {
        "secret_key": "test-secret-key-with-enough-length",
        "mtproto_base_domain": "krotpn.xyz",
        "mtproto_proxy_port": 443,
        "mtproto_base_secret_hex": BASE_SECRET,
        "mtproto_secret_salt": SECRET_SALT,
        "mtproto_sni_prefix": "u",
        "mtproto_rotation_marker": "v1",
    }
    values.update(overrides)
    return Settings(**values)


async def _create_user(
    db_session: AsyncSession,
    email: str,
    *,
    email_verified: bool = True,
    is_active: bool = True,
) -> User:
    user = User(email=email, email_verified=email_verified, is_active=is_active)
    db_session.add(user)
    await db_session.flush()
    return user


async def _assignment_count(db_session: AsyncSession) -> int:
    result = await db_session.execute(select(func.count()).select_from(MTProtoAssignment))
    return int(result.scalar_one())
# END_BLOCK_FIXTURES


# START_BLOCK_PROVISIONING_TESTS
def test_generate_sni_is_stable_and_under_base_domain():
    first = generate_sni("user:42", base_domain="*.KROTPN.XYZ.", prefix="u")
    second = generate_sni("user:42", base_domain="krotpn.xyz", prefix="u")
    collision_fallback = generate_sni(
        "user:42",
        base_domain="krotpn.xyz",
        prefix="u",
        collision_nonce=1,
    )

    assert first == second
    assert first.endswith(".krotpn.xyz")
    assert first.startswith("u-")
    assert len(first.split(".")[0]) == len("u-") + 12
    assert collision_fallback != first


def test_derive_fake_tls_secret_matches_kpproton_vector():
    assert derive_fake_tls_secret(BASE_SECRET, SECRET_SALT, "alice.example.com") == (
        "eeec1cbe1e438427a47d6fb25343e844f7"
        "616c6963652e6578616d706c652e636f6d"
    )


@pytest.mark.asyncio
async def test_issue_user_proxy_is_idempotent_and_owner_safe(db_session: AsyncSession):
    user = await _create_user(db_session, "verified-mtproto@example.com")
    service = MTProtoProvisioningService(db_session, app_settings=_settings())

    first = await service.issue_user_proxy(user)
    second = await service.issue_user_proxy(user)

    assert second == first
    assert first.server == first.sni
    assert first.server.endswith(".krotpn.xyz")
    assert first.port == 443
    assert first.secret.startswith("ee")
    assert first.secret.endswith(first.sni.encode("utf-8").hex())
    assert first.tg_link.startswith("tg://proxy?")
    assert first.tg_link.count(BASE_SECRET) == 0
    assert await _assignment_count(db_session) == 1


@pytest.mark.asyncio
async def test_issue_user_proxy_rejects_unverified_user_without_assignment(
    db_session: AsyncSession,
):
    user = await _create_user(
        db_session,
        "unverified-mtproto@example.com",
        email_verified=False,
    )
    service = MTProtoProvisioningService(db_session, app_settings=_settings())

    with pytest.raises(MTProtoProvisioningError) as exc:
        await service.issue_user_proxy(user)

    assert exc.value.code == MTProtoProvisioningErrorCode.USER_NOT_VERIFIED
    assert await _assignment_count(db_session) == 0


@pytest.mark.asyncio
async def test_rotation_marker_requires_explicit_reissue(db_session: AsyncSession):
    user = await _create_user(db_session, "reissue-mtproto@example.com")
    v1_service = MTProtoProvisioningService(db_session, app_settings=_settings())
    first = await v1_service.issue_user_proxy(user)

    v2_service = MTProtoProvisioningService(
        db_session,
        app_settings=_settings(mtproto_rotation_marker="v2"),
    )
    with pytest.raises(MTProtoProvisioningError) as exc:
        await v2_service.issue_user_proxy(user)

    assert exc.value.code == MTProtoProvisioningErrorCode.REISSUE_REQUIRED

    reissued = await v2_service.issue_user_proxy(user, reissue=True)

    assert reissued.assignment_id == first.assignment_id
    assert reissued.server == first.server
    assert reissued.rotation_marker == "v2"
    assert await _assignment_count(db_session) == 1


@pytest.mark.asyncio
async def test_blank_mtproto_secrets_are_treated_as_missing_config(
    db_session: AsyncSession,
):
    user = await _create_user(db_session, "blank-config-mtproto@example.com")
    settings = _settings(mtproto_base_secret_hex="", mtproto_secret_salt="   ")
    service = MTProtoProvisioningService(db_session, app_settings=settings)

    assert settings.mtproto_base_secret_hex is None
    assert settings.mtproto_secret_salt is None

    with pytest.raises(MTProtoProvisioningError) as exc:
        await service.issue_user_proxy(user)

    assert exc.value.code == MTProtoProvisioningErrorCode.CONFIG_INCOMPLETE
    assert await _assignment_count(db_session) == 0


@pytest.mark.asyncio
async def test_incomplete_runtime_config_is_rejected(db_session: AsyncSession):
    user = await _create_user(db_session, "missing-config-mtproto@example.com")
    service = MTProtoProvisioningService(
        db_session,
        app_settings=_settings(mtproto_base_secret_hex=None, mtproto_secret_salt=None),
    )

    with pytest.raises(MTProtoProvisioningError) as exc:
        await service.issue_user_proxy(user)

    assert exc.value.code == MTProtoProvisioningErrorCode.CONFIG_INCOMPLETE
    assert await _assignment_count(db_session) == 0
# END_BLOCK_PROVISIONING_TESTS
