# FILE: backend/app/vpn/obfuscation.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: AmneziaWG stealth obfuscation profile generation, parsing, validation, and rendering
#   SCOPE: Bounded profile helpers for deploy scripts and backend client config parity checks
#   DEPENDS: stdlib (dataclasses, pathlib, re, secrets)
#   LINKS: M-030 (awg-stealth-obfuscation), V-M-030
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   AWGObfuscationProfile - Immutable typed profile for Jc/Jmin/Jmax/S1/S2/H1-H4
#   AWGProfileError - Validation or parsing failure for one profile
#   AWGProfileMismatchError - Raised when two endpoint profiles differ
#   generate_awg_profile - Generate a profile inside approved AmnezWG reference ranges
#   parse_awg_profile_text - Parse AWG config text into a validated profile
#   parse_awg_profile_file - Parse an AWG config file when it exists
#   profile_from_mapping - Build a validated profile from env/settings mappings
#   render_awg_profile - Render AWG interface lines for configs
#   render_awg_profile_env - Render env lines with a caller-provided prefix
#   validate_awg_profile_pair - Enforce endpoint profile parity before service restart
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v3.0.0 - Added bounded AmneziaWG stealth profile contract for deploy/backend parity
# END_CHANGE_SUMMARY
#
"""AmneziaWG stealth obfuscation profile helpers."""

from dataclasses import dataclass
from pathlib import Path
import re
import secrets
from collections.abc import Callable, Mapping


AWG_KEY_ORDER = ("jc", "jmin", "jmax", "s1", "s2", "h1", "h2", "h3", "h4")
AWG_CONFIG_KEY_MAP = {
    "Jc": "jc",
    "Jmin": "jmin",
    "Jmax": "jmax",
    "S1": "s1",
    "S2": "s2",
    "H1": "h1",
    "H2": "h2",
    "H3": "h3",
    "H4": "h4",
}
AWG_PROFILE_BOUNDS = {
    "jc": (4, 8),
    "jmin": (40, 50),
    "jmax": (100, 200),
    "s1": (15, 150),
    "s2": (15, 150),
    "h1": (100000000, 2147483647),
    "h2": (100000000, 2147483647),
    "h3": (100000000, 2147483647),
    "h4": (100000000, 2147483647),
}
AWG_PROFILE_LINE_RE = re.compile(r"^\s*(Jc|Jmin|Jmax|S1|S2|H1|H2|H3|H4)\s*=\s*(\d+)\s*(?:#.*)?$")


class AWGProfileError(ValueError):
    """Raised when an AWG obfuscation profile is incomplete or invalid."""


class AWGProfileMismatchError(AWGProfileError):
    """Raised when two AWG endpoints do not use the same obfuscation profile."""


# START_BLOCK: AWGObfuscationProfile
@dataclass(frozen=True)
class AWGObfuscationProfile:
    """Validated AmneziaWG stealth parameters shared by both endpoints of one link."""

    jc: int
    jmin: int
    jmax: int
    s1: int
    s2: int
    h1: int
    h2: int
    h3: int
    h4: int

    def __post_init__(self) -> None:
        for key, (minimum, maximum) in AWG_PROFILE_BOUNDS.items():
            value = getattr(self, key)
            if value < minimum or value > maximum:
                raise AWGProfileError(
                    f"{key}={value} is outside approved range {minimum}..{maximum}"
                )

    def as_dict(self) -> dict[str, int]:
        """Return profile values in the legacy lowercase shape used by settings."""
        return {key: getattr(self, key) for key in AWG_KEY_ORDER}

    def as_config_lines(self) -> list[str]:
        """Return profile lines in AWG config key order."""
        return [
            f"{config_key} = {getattr(self, attr)}"
            for config_key, attr in AWG_CONFIG_KEY_MAP.items()
        ]

    def as_env_lines(self, prefix: str) -> list[str]:
        """Return profile values as environment variables."""
        normalized_prefix = prefix.upper()
        return [
            f"{normalized_prefix}{key.upper()}={getattr(self, key)}"
            for key in AWG_KEY_ORDER
        ]

    def summary(self) -> str:
        """Return a non-secret, compact summary for logs."""
        return f"jc={self.jc} jmin={self.jmin} jmax={self.jmax}"
# END_BLOCK: AWGObfuscationProfile


# START_BLOCK: generate_awg_profile
def generate_awg_profile(
    random_source: Callable[[int, int], int] | None = None,
) -> AWGObfuscationProfile:
    """Generate a bounded AmneziaWG stealth profile from approved ranges."""
    if random_source is None:
        random_source = _secure_randint

    values = {
        key: random_source(minimum, maximum)
        for key, (minimum, maximum) in AWG_PROFILE_BOUNDS.items()
    }
    return AWGObfuscationProfile(**values)
# END_BLOCK: generate_awg_profile


# START_BLOCK: profile_from_mapping
def profile_from_mapping(mapping: Mapping[str, int | str | None]) -> AWGObfuscationProfile:
    """Build and validate a profile from lowercase or AWG-style mapping keys."""
    values: dict[str, int] = {}
    for key in AWG_KEY_ORDER:
        raw_value = mapping.get(key)
        if raw_value is None:
            raw_value = mapping.get(key.upper())
        if raw_value is None:
            raw_value = mapping.get(_config_key_for_attr(key))
        if raw_value is None:
            raise AWGProfileError(f"missing AWG profile value: {key}")
        try:
            values[key] = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise AWGProfileError(f"invalid AWG profile value for {key}") from exc

    return AWGObfuscationProfile(**values)
# END_BLOCK: profile_from_mapping


# START_BLOCK: parse_awg_profile_text
def parse_awg_profile_text(text: str) -> AWGObfuscationProfile:
    """Parse AWG config text into a validated stealth profile."""
    values: dict[str, int] = {}
    for line in text.splitlines():
        match = AWG_PROFILE_LINE_RE.match(line)
        if not match:
            continue

        config_key, value = match.groups()
        values[AWG_CONFIG_KEY_MAP[config_key]] = int(value)

    missing = [key for key in AWG_KEY_ORDER if key not in values]
    if missing:
        raise AWGProfileError(f"missing AWG profile values: {', '.join(missing)}")

    return AWGObfuscationProfile(**values)
# END_BLOCK: parse_awg_profile_text


# START_BLOCK: parse_awg_profile_file
def parse_awg_profile_file(path: str | Path) -> AWGObfuscationProfile | None:
    """Parse an AWG profile file when it exists; return None for absent files."""
    profile_path = Path(path)
    if not profile_path.exists():
        return None
    return parse_awg_profile_text(profile_path.read_text(encoding="utf-8"))
# END_BLOCK: parse_awg_profile_file


# START_BLOCK: render_awg_profile
def render_awg_profile(profile: AWGObfuscationProfile) -> str:
    """Render AWG profile lines for an interface config."""
    return "\n".join(profile.as_config_lines())
# END_BLOCK: render_awg_profile


# START_BLOCK: render_awg_profile_env
def render_awg_profile_env(profile: AWGObfuscationProfile, prefix: str = "AWG_CLIENT_") -> str:
    """Render AWG profile lines for dotenv output."""
    return "\n".join(profile.as_env_lines(prefix))
# END_BLOCK: render_awg_profile_env


# START_BLOCK: validate_awg_profile_pair
def validate_awg_profile_pair(
    expected: AWGObfuscationProfile,
    actual: AWGObfuscationProfile,
    *,
    label: str = "AWG profile",
) -> None:
    """Raise if two endpoints for one AWG link do not share identical parameters."""
    if expected != actual:
        raise AWGProfileMismatchError(f"{label} mismatch")
# END_BLOCK: validate_awg_profile_pair


def _secure_randint(minimum: int, maximum: int) -> int:
    return minimum + secrets.randbelow(maximum - minimum + 1)


def _config_key_for_attr(attr: str) -> str:
    for config_key, mapped_attr in AWG_CONFIG_KEY_MAP.items():
        if mapped_attr == attr:
            return config_key
    raise AWGProfileError(f"unknown AWG profile key: {attr}")
