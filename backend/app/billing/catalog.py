# FILE: backend/app/billing/catalog.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Provide the Phase-50 canonical paid tariff catalog for billing, migrations, tests, and UI API serialization.
#   SCOPE: Immutable tariff definitions, slug lookup, and JSON feature serialization helpers.
#   DEPENDS: M-004 (billing models/service), M-068 (paid tariff catalog)
#   LINKS: M-068, V-M-068
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   CanonicalTariff - Immutable tariff definition value object
#   CANONICAL_TARIFFS - Approved KrotPN tariff matrix
#   CANONICAL_TARIFF_SLUGS - Stable storefront slug set
#   canonical_tariff_by_slug - Lookup one approved tariff by slug
#   is_canonical_tariff_slug - Checks whether one slug belongs to the approved matrix
#   tariff_features_json - Serializes tariff feature text for Plan.features
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v1.0.0 - Added Phase-50 canonical three-plan paid tariff matrix.
# END_CHANGE_SUMMARY

from __future__ import annotations

import json
from dataclasses import dataclass


# START_BLOCK: canonical_tariff_contract
@dataclass(frozen=True)
class CanonicalTariff:
    """Approved paid storefront tariff definition."""

    slug: str
    name: str
    description: str
    price: float
    currency: str
    duration_days: int
    device_limit: int
    features: tuple[str, ...]
    is_popular: bool
    sort_order: int


CANONICAL_TARIFFS: tuple[CanonicalTariff, ...] = (
    CanonicalTariff(
        slug="krotpn-1",
        name="KrotPN 1",
        description="Персональный тариф для одного устройства.",
        price=369.0,
        currency="RUB",
        duration_days=30,
        device_limit=1,
        features=(
            "1 устройство",
            "AmneziaWG Full Tunnel",
            "Персональный Telegram MTProto proxy",
            "Личный кабинет и QR/.conf",
        ),
        is_popular=False,
        sort_order=10,
    ),
    CanonicalTariff(
        slug="krotpn-6",
        name="KrotPN 6",
        description="Оптимальный тариф для нескольких устройств.",
        price=693.0,
        currency="RUB",
        duration_days=30,
        device_limit=6,
        features=(
            "До 6 устройств",
            "AmneziaWG Full Tunnel",
            "Персональный Telegram MTProto proxy",
            "Удобно для семьи и рабочих устройств",
        ),
        is_popular=True,
        sort_order=20,
    ),
    CanonicalTariff(
        slug="krotpn-9",
        name="KrotPN 9",
        description="Максимальный стандартный тариф KrotPN.",
        price=936.0,
        currency="RUB",
        duration_days=30,
        device_limit=9,
        features=(
            "До 9 устройств",
            "AmneziaWG Full Tunnel",
            "Персональный Telegram MTProto proxy",
            "Максимальный лимит стандартной линейки",
        ),
        is_popular=False,
        sort_order=30,
    ),
)

CANONICAL_TARIFF_SLUGS: tuple[str, ...] = tuple(tariff.slug for tariff in CANONICAL_TARIFFS)
_TARIFF_BY_SLUG = {tariff.slug: tariff for tariff in CANONICAL_TARIFFS}
# END_BLOCK: canonical_tariff_contract


# START_BLOCK: canonical_tariff_helpers
def canonical_tariff_by_slug(slug: str) -> CanonicalTariff | None:
    """Return one canonical tariff definition by stable slug."""
    return _TARIFF_BY_SLUG.get(slug)


def is_canonical_tariff_slug(slug: str | None) -> bool:
    """Return whether a slug belongs to the approved paid tariff matrix."""
    return bool(slug and slug in _TARIFF_BY_SLUG)


def tariff_features_json(tariff: CanonicalTariff) -> str:
    """Serialize tariff features using deterministic UTF-8-safe JSON."""
    return json.dumps(list(tariff.features), ensure_ascii=False)
# END_BLOCK: canonical_tariff_helpers
