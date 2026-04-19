# FILE: backend/tests/test_deploy_awg_obfuscation_static.py
# VERSION: 1.0.0
# ROLE: TEST
# MAP_MODE: LOCALS
# START_MODULE_CONTRACT
#   PURPOSE: Static verification for deploy-time AWG stealth profile wiring
#   SCOPE: Ensure deploy scripts use generated/preserved profiles and no legacy hardcoded values
#   DEPENDS: M-012 (deploy-surface), M-030 (awg-stealth-obfuscation)
#   LINKS: V-M-030
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   test_deploy_scripts_do_not_render_legacy_hardcoded_profiles - Blocks old Jc/Jmax examples
#   test_deploy_scripts_generate_and_preserve_client_and_relay_profiles - Checks helper wiring
#   test_deploy_env_exports_client_relay_and_legacy_compat_values - Checks backend .env propagation
#   test_awg_helper_has_bounds_preservation_and_parity_markers - Checks shell helper contracts
#   test_awg_helper_aborts_on_any_invalid_or_missing_profile_key - Checks shell failure behavior
# END_MODULE_MAP

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_deploy_scripts_do_not_render_legacy_hardcoded_profiles():
    combined = "\n".join(
        [
            read("deploy/deploy-on-server.sh"),
            read("deploy/deploy-all.sh"),
        ]
    )

    assert "Jc = 120" not in combined
    assert "Jmax = 1000" not in combined
    assert "AWG_JC=120" not in combined
    assert "AWG_JMAX=1000" not in combined


def test_deploy_scripts_generate_and_preserve_client_and_relay_profiles():
    deploy_on_server = read("deploy/deploy-on-server.sh")
    deploy_all = read("deploy/deploy-all.sh")

    for script in (deploy_on_server, deploy_all):
        assert "source \"${SCRIPT_DIR}/lib/awg-obfuscation.sh\"" in script
        assert "awg_profile_ensure CLIENT_" in script
        assert "awg_profile_ensure RELAY_" in script
        assert "STEALTH_ROTATE" in script
        assert "$(awg_profile_lines CLIENT_)" in script
        assert "$(awg_profile_lines RELAY_)" in script


def test_deploy_env_exports_client_relay_and_legacy_compat_values():
    combined = "\n".join(
        [
            read("deploy/deploy-on-server.sh"),
            read("deploy/deploy-all.sh"),
        ]
    )

    assert '$(awg_profile_env_lines CLIENT_ "AWG_CLIENT_")' in combined
    assert '$(awg_profile_env_lines RELAY_ "AWG_RELAY_")' in combined
    assert '$(awg_profile_env_lines CLIENT_ "AWG_")' in combined


def test_awg_helper_has_bounds_preservation_and_parity_markers():
    helper = read("deploy/lib/awg-obfuscation.sh")

    assert "awg_profile_validate_one \"$prefix\" JC 4 8 || return 1" in helper
    assert "awg_profile_validate_one \"$prefix\" JMAX 100 200 || return 1" in helper
    assert "awg_profile_validate_one \"$prefix\" H4 100000000 2147483647 || return 1" in helper
    assert "AWG_PROFILE_GENERATED" in helper
    assert "AWG_PROFILE_PRESERVED" in helper
    assert "AWG_PROFILE_PARITY_OK" in helper
    assert "AWG_PROFILE_MISMATCH" in helper
    assert "WG_QUICK_USERSPACE_IMPLEMENTATION=/usr/local/bin/amneziawg-go" in helper
    assert "NOTRACK" in helper


def test_awg_helper_aborts_on_any_invalid_or_missing_profile_key(tmp_path):
    invalid_jc = subprocess.run(
        [
            "bash",
            "-c",
            (
                "source deploy/lib/awg-obfuscation.sh; "
                "TEST_JC=99 TEST_JMIN=45 TEST_JMAX=150 TEST_S1=90 TEST_S2=100 "
                "TEST_H1=100000001 TEST_H2=100000002 TEST_H3=100000003 TEST_H4=100000004; "
                "awg_profile_validate TEST_"
            ),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert invalid_jc.returncode != 0
    assert "AWG_PROFILE_MISMATCH" in invalid_jc.stderr

    missing_jc_file = tmp_path / "missing-jc.conf"
    missing_jc_file.write_text(
        "\n".join(
            [
                "[Interface]",
                "Jmin = 45",
                "Jmax = 150",
                "S1 = 90",
                "S2 = 100",
                "H1 = 100000001",
                "H2 = 100000002",
                "H3 = 100000003",
                "H4 = 100000004",
            ]
        ),
        encoding="utf-8",
    )

    missing_jc = subprocess.run(
        [
            "bash",
            "-c",
            f"source deploy/lib/awg-obfuscation.sh; awg_profile_load TEST_ {missing_jc_file}",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert missing_jc.returncode != 0
    assert "missing Jc" in missing_jc.stderr
