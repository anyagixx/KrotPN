"""MTProto provisioning core tests.

# FILE: backend/tests/test_mtproto_provisioning.py
# VERSION: 2.2.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify deterministic owner-safe KPprotoN fake-TLS provisioning with CTA hostnames
#   SCOPE: CTA SNI generation, legacy SNI preservation, KPprotoN fake-TLS vectors,
#          derived-per-SNI issuance, runtime policy activation, reissue, and verified-user guard
#   DEPENDS: M-043, M-044, M-042, M-001, M-002, M-065
#   LINKS: V-M-043, V-M-044, V-M-042, V-M-001, V-M-065
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   test_generate_sni_is_stable_and_under_base_domain - Covers stable SNI generation
#   test_cta_prefix_allow_list_is_fixed - Covers Phase-47 CTA prefix contract
#   test_public_short_id_derivation_hashes_numeric_ids - Covers public 7-hex suffix derivation
#   test_generate_cta_sni_validates_prefix_and_single_label - Covers CTA SNI validation and explicit prefix support
#   test_derive_fake_tls_secret_matches_kpproton_vector - Covers fake-TLS derivation
#   test_fake_tls_link_helper_builds_owner_link - Covers KPprotoN fake-TLS link formatting
#   test_issue_user_proxy_is_idempotent_and_owner_safe - Covers owner payload assembly
#   test_issue_user_proxy_accepts_explicit_cta_prefix - Covers explicit CTA prefix issuance
#   test_issue_user_proxy_preserves_existing_legacy_u_assignment - Covers no automatic mass reissue
#   test_issue_user_proxy_rejects_unverified_user_without_assignment - Covers verified gate
#   test_rotation_marker_requires_explicit_reissue - Covers reissue-required policy
#   test_blank_mtproto_secrets_are_treated_as_missing_config - Covers blank env normalization
#   test_incomplete_runtime_config_is_rejected - Covers safe config failure
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.2.0 - Added Phase-47 CTA SNI generation and legacy assignment preservation coverage.
#   LAST_CHANGE: v2.1.0 - Restored KPprotoN derived-per-SNI fake-TLS provisioning coverage.
#   LAST_CHANGE: v2.0.0 - Updated provisioning coverage for official MTProxy dd secrets.
#   LAST_CHANGE: v1.1.0 - Added regression coverage for blank MTProto env values from fresh deploys
#   LAST_CHANGE: v1.0.0 - Added Phase-29 provisioning tests
# END_CHANGE_SUMMARY
"""

import re

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.mtproto.models import MTProtoAssignment, MTProtoAssignmentStatus, MTProtoCredentialMode
from app.mtproto.service import (
    MTPROTO_CTA_PREFIXES,
    MTProtoProvisioningError,
    MTProtoProvisioningErrorCode,
    MTProtoProvisioningService,
    build_tg_link,
    derive_fake_tls_secret,
    generate_cta_sni,
    generate_sni,
    select_cta_prefix,
    shorten_public_user_id,
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


def test_cta_prefix_allow_list_is_fixed():
    assert MTPROTO_CTA_PREFIXES == (
        "kupi-vpn",
        "vpn-tut",
        "beri-vpn",
        "bez-blokirovok",
        "hochu-bystree",
        "krot-vpn",
    )


def test_public_short_id_derivation_hashes_numeric_ids():
    assert shorten_public_user_id("4bb40fa4b428") == "4bb40fa"
    assert shorten_public_user_id("4bb40fa4-b428-4fff-8333-abcdefabcdef") == "4bb40fa"

    numeric_suffix = shorten_public_user_id("1234567")
    repeated_suffix = shorten_public_user_id(1234567)
    collision_suffix = shorten_public_user_id("1234567", collision_nonce=1)

    assert numeric_suffix == repeated_suffix
    assert numeric_suffix != "1234567"
    assert re.fullmatch(r"[0-9a-f]{7}", numeric_suffix)
    assert re.fullmatch(r"[0-9a-f]{7}", collision_suffix)
    assert collision_suffix != numeric_suffix


def test_generate_cta_sni_validates_prefix_and_single_label():
    sni = generate_cta_sni(
        "4bb40fa4b428",
        base_domain="*.KROTPN.XYZ.",
        prefix="krot-vpn",
    )
    collision_sni = generate_cta_sni(
        "4bb40fa4b428",
        base_domain="krotpn.xyz",
        prefix="krot-vpn",
        collision_nonce=1,
    )
    stable_prefix = select_cta_prefix("42")

    assert sni == "krot-vpn-4bb40fa.krotpn.xyz"
    assert collision_sni.endswith(".krotpn.xyz")
    assert collision_sni.startswith("krot-vpn-")
    assert collision_sni != sni
    assert stable_prefix in MTPROTO_CTA_PREFIXES
    assert select_cta_prefix("42") == stable_prefix

    for invalid_prefix in ("KROT-VPN", "custom", "vpn.tut", "../vpn", "krot-vpn "):
        with pytest.raises(MTProtoProvisioningError) as exc:
            generate_cta_sni("4bb40fa4b428", base_domain="krotpn.xyz", prefix=invalid_prefix)
        assert exc.value.code == MTProtoProvisioningErrorCode.INVALID_SNI


def test_derive_fake_tls_secret_matches_kpproton_vector():
    assert derive_fake_tls_secret(BASE_SECRET, SECRET_SALT, "alice.example.com") == (
        "eeec1cbe1e438427a47d6fb25343e844f7"
        "616c6963652e6578616d706c652e636f6d"
    )


@pytest.mark.asyncio
async def test_fake_tls_link_helper_builds_owner_link(db_session: AsyncSession):
    user = await _create_user(db_session, "faketls-helper-mtproto@example.com")
    assignment = MTProtoAssignment(
        user_id=int(user.id),
        sni="u-helper11111.krotpn.xyz",
        credential_mode=MTProtoCredentialMode.DERIVED_PER_SNI,
        status=MTProtoAssignmentStatus.ACTIVE,
    )
    db_session.add(assignment)
    await db_session.flush()
    await db_session.refresh(assignment)

    secret = derive_fake_tls_secret(BASE_SECRET, SECRET_SALT, assignment.sni)
    link = build_tg_link(assignment.sni, 443, secret)

    assert secret.startswith("ee")
    assert assignment.sni.encode("utf-8").hex() in secret
    assert link == f"tg://proxy?server={assignment.sni}&port=443&secret={secret}"
    assert BASE_SECRET not in link
    assert SECRET_SALT not in link


@pytest.mark.asyncio
async def test_issue_user_proxy_is_idempotent_and_owner_safe(db_session: AsyncSession):
    user = await _create_user(db_session, "verified-mtproto@example.com")
    service = MTProtoProvisioningService(db_session, app_settings=_settings())

    first = await service.issue_user_proxy(user)
    second = await service.issue_user_proxy(user)

    assert second == first
    assert first.server == first.sni
    assert first.sni.endswith(".krotpn.xyz")
    assert not first.sni.startswith("u-")
    assert any(first.sni.startswith(f"{prefix}-") for prefix in MTPROTO_CTA_PREFIXES)
    assert re.fullmatch(r"[0-9a-f]{7}", first.sni.split(".")[0].rsplit("-", 1)[1])
    assert first.port == 443
    assert first.secret.startswith("ee")
    assert first.sni.encode("utf-8").hex() in first.secret
    assert first.credential_mode == "derived_per_sni"
    assert first.tg_link.startswith("tg://proxy?")
    assert first.tg_link.count(BASE_SECRET) == 0
    assert first.tg_link.count(SECRET_SALT) == 0
    assert first.secret in first.tg_link
    assert await _assignment_count(db_session) == 1


@pytest.mark.asyncio
async def test_issue_user_proxy_accepts_explicit_cta_prefix(db_session: AsyncSession):
    user = await _create_user(db_session, "explicit-cta-mtproto@example.com")
    service = MTProtoProvisioningService(db_session, app_settings=_settings())

    payload = await service.issue_user_proxy(user, cta_prefix="krot-vpn")

    assert payload.server.startswith("krot-vpn-")
    assert payload.server.endswith(".krotpn.xyz")
    assert payload.server.encode("utf-8").hex() in payload.secret
    assert f"server={payload.server}" in payload.tg_link
    assert payload.secret in payload.tg_link
    assert await _assignment_count(db_session) == 1


@pytest.mark.asyncio
async def test_issue_user_proxy_preserves_existing_legacy_u_assignment(
    db_session: AsyncSession,
):
    user = await _create_user(db_session, "legacy-u-mtproto@example.com")
    assignment = MTProtoAssignment(
        user_id=int(user.id),
        sni="u-abcdef123456.krotpn.xyz",
        credential_mode=MTProtoCredentialMode.DERIVED_PER_SNI,
        status=MTProtoAssignmentStatus.ACTIVE,
        rotation_marker="v1",
    )
    db_session.add(assignment)
    await db_session.flush()
    await db_session.refresh(assignment)
    service = MTProtoProvisioningService(db_session, app_settings=_settings())

    payload = await service.issue_user_proxy(user)

    assert payload.assignment_id == assignment.id
    assert payload.server == "u-abcdef123456.krotpn.xyz"
    assert payload.sni == assignment.sni
    assert payload.secret.startswith("ee")
    assert payload.sni.encode("utf-8").hex() in payload.secret
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
    assert reissued.secret == first.secret
    assert reissued.rotation_marker == "v2"
    assert await _assignment_count(db_session) == 1


@pytest.mark.asyncio
async def test_official_secure_assignment_requires_explicit_reissue(
    db_session: AsyncSession,
):
    user = await _create_user(db_session, "official-stale-mtproto@example.com")
    assignment = MTProtoAssignment(
        user_id=int(user.id),
        sni="u-stale111111.krotpn.xyz",
        credential_mode=MTProtoCredentialMode.OFFICIAL_SECURE,
        status=MTProtoAssignmentStatus.ACTIVE,
        rotation_marker="v1",
    )
    db_session.add(assignment)
    await db_session.flush()

    service = MTProtoProvisioningService(db_session, app_settings=_settings())
    with pytest.raises(MTProtoProvisioningError) as exc:
        await service.issue_user_proxy(user)

    assert exc.value.code == MTProtoProvisioningErrorCode.REISSUE_REQUIRED

    reissued = await service.issue_user_proxy(user, reissue=True)

    assert reissued.assignment_id == assignment.id
    assert reissued.server == assignment.sni
    assert reissued.secret.startswith("ee")
    assert reissued.credential_mode == "derived_per_sni"
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
