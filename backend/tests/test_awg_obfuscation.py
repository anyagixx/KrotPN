# FILE: backend/tests/test_awg_obfuscation.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Verify bounded AmneziaWG stealth profile helpers
#   SCOPE: Generation bounds, parsing/rendering, env rendering, and parity mismatch detection
#   DEPENDS: M-030 (awg-stealth-obfuscation)
#   LINKS: V-M-030
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   test_generate_awg_profile_uses_approved_bounds - Deterministic lower-bound generation
#   test_parse_render_and_env_round_trip - Config and env render preserve values
#   test_validate_awg_profile_pair_rejects_mismatch - Endpoint parity failures raise
#   test_profile_from_mapping_rejects_out_of_range_values - Invalid profiles are rejected
# END_MODULE_MAP

import pytest

from app.vpn.obfuscation import (
    AWGObfuscationProfile,
    AWGProfileError,
    AWGProfileMismatchError,
    generate_awg_profile,
    parse_awg_profile_text,
    profile_from_mapping,
    render_awg_profile,
    render_awg_profile_env,
    validate_awg_profile_pair,
)


def test_generate_awg_profile_uses_approved_bounds():
    profile = generate_awg_profile(lambda minimum, maximum: minimum)

    assert profile.as_dict() == {
        "jc": 4,
        "jmin": 40,
        "jmax": 100,
        "s1": 15,
        "s2": 15,
        "h1": 100000000,
        "h2": 100000000,
        "h3": 100000000,
        "h4": 100000000,
    }


def test_parse_render_and_env_round_trip():
    profile = AWGObfuscationProfile(
        jc=6,
        jmin=45,
        jmax=150,
        s1=88,
        s2=99,
        h1=100000001,
        h2=100000002,
        h3=100000003,
        h4=100000004,
    )

    rendered = render_awg_profile(profile)
    parsed = parse_awg_profile_text(f"[Interface]\n{rendered}\n")

    assert parsed == profile
    assert "Jc = 6" in rendered
    assert "AWG_CLIENT_JMAX=150" in render_awg_profile_env(profile, "AWG_CLIENT_")


def test_validate_awg_profile_pair_rejects_mismatch():
    expected = generate_awg_profile(lambda minimum, maximum: minimum)
    actual = generate_awg_profile(lambda minimum, maximum: maximum)

    with pytest.raises(AWGProfileMismatchError):
        validate_awg_profile_pair(expected, actual, label="relay")


def test_profile_from_mapping_rejects_out_of_range_values():
    with pytest.raises(AWGProfileError):
        profile_from_mapping(
            {
                "jc": 120,
                "jmin": 50,
                "jmax": 1000,
                "s1": 111,
                "s2": 222,
                "h1": 1,
                "h2": 2,
                "h3": 3,
                "h4": 4,
            }
        )
