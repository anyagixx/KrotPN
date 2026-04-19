# FILE: backend/app/core/config.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Application configuration and environment variable parsing with validation
#   SCOPE: Settings model, environment parsing, secret validation, AmneziaWG obfuscation params
#   DEPENDS: none
#   LINKS: M-001 (backend-core), V-M-001
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   Settings - Pydantic BaseSettings model with all environment variables and validators
#   Settings.awg_client_obfuscation_params - Validated deploy-time CLIENT_PROFILE mapping when AWG_CLIENT_* is present
#   Settings.awg_relay_obfuscation_params - Validated deploy-time RELAY_PROFILE mapping when AWG_RELAY_* is present
#   get_settings - lru_cache factory returning validated Settings singleton
#   settings - Module-level cached Settings instance
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v3.0.0 - Added AWG_CLIENT_*/AWG_RELAY_* profile settings while preserving legacy AWG_* compatibility
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""
Application configuration module.
Loads settings from environment variables.

GRACE-lite module contract:
- Owns runtime settings shape for backend and host-coupled integrations.
- Environment variables are the only supported secrets/config source at runtime.
- If docs and defaults disagree, deployed `.env` values and actual code behavior win.
- Changes here can silently affect auth, billing, VPN bootstrap and deployment assumptions.
"""
# <!-- GRACE: module="M-001" contract="config-loading" -->

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


AWG_SETTING_BOUNDS = {
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


# START_BLOCK_SETTINGS_CLASS
class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "KrotPN"
    app_version: str = "2.4.27"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./krotpn.db",
        description="Database connection URL",
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # Security
    secret_key: str = Field(
        default="change-this-secret-key-in-production",
        description="Secret key for JWT signing",
    )
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins",
    )

    # Admin
    admin_email: str | None = None
    admin_password: str | None = None

    # VPN Configuration
    vpn_subnet: str = "10.10.0.0/24"
    vpn_port: int = 51821
    vpn_dns: str = "8.8.8.8, 1.1.1.1"
    vpn_mtu: int = 1360
    vpn_server_public_key: str | None = None
    vpn_server_endpoint: str | None = None
    vpn_server_name: str = "RU Entry Node"
    vpn_server_location: str = "Russia"
    vpn_server_max_clients: int = 500
    vpn_entry_server_public_key: str | None = None
    vpn_entry_server_endpoint: str | None = None
    vpn_entry_server_name: str = "RU Entry Node"
    vpn_entry_server_location: str = "Russia"
    vpn_entry_server_country_code: str = "RU"
    vpn_entry_server_max_clients: int = 500
    vpn_exit_server_public_key: str | None = None
    vpn_exit_server_endpoint: str | None = None
    vpn_exit_server_name: str = "DE Exit Node"
    vpn_exit_server_location: str = "Germany"
    vpn_exit_server_country_code: str = "DE"
    vpn_exit_server_max_clients: int = 500
    vpn_default_route_name: str = "RU -> DE"

    # AmneziaWG Obfuscation Parameters
    # AWG_CLIENT_* is the new deploy-time source of truth. AWG_* stays as a
    # legacy fallback so existing installations do not rotate implicitly.
    awg_client_jc: int | None = None
    awg_client_jmin: int | None = None
    awg_client_jmax: int | None = None
    awg_client_s1: int | None = None
    awg_client_s2: int | None = None
    awg_client_h1: int | None = None
    awg_client_h2: int | None = None
    awg_client_h3: int | None = None
    awg_client_h4: int | None = None
    awg_relay_jc: int | None = None
    awg_relay_jmin: int | None = None
    awg_relay_jmax: int | None = None
    awg_relay_s1: int | None = None
    awg_relay_s2: int | None = None
    awg_relay_h1: int | None = None
    awg_relay_h2: int | None = None
    awg_relay_h3: int | None = None
    awg_relay_h4: int | None = None
    awg_jc: int = 6
    awg_jmin: int = 45
    awg_jmax: int = 150
    awg_s1: int = 90
    awg_s2: int = 100
    awg_h1: int = 100000001
    awg_h2: int = 100000002
    awg_h3: int = 100000003
    awg_h4: int = 100000004

    # Trial
    trial_days: int = 3

    # YooKassa
    yookassa_shop_id: str | None = None
    yookassa_secret_key: str | None = None

    # Tinkoff
    tinkoff_terminal_key: str | None = None
    tinkoff_secret_key: str | None = None

    # Telegram
    telegram_bot_token: str | None = None
    telegram_webhook_url: str | None = None

    # Email (reserved for future use — no email module currently)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    email_from: str | None = None

    # Referral
    referral_bonus_days: int = 7
    referral_min_payment: float = 100.0

    # Frontend
    frontend_url: str = "https://krotpn.com"

    # Data Encryption
    data_encryption_key: str | None = None

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if v == "change-this-secret-key-in-production":
            raise ValueError(
                "SECRET_KEY must be set to a strong random value in production. "
                "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        return v

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        # Ensure async driver is used
        if v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://")
        elif v.startswith("sqlite://"):
            v = v.replace("sqlite://", "sqlite+aiosqlite://")
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def awg_obfuscation_params(self) -> dict:
        """Return client-facing AmneziaWG obfuscation parameters as dict."""
        client_profile = self.awg_client_obfuscation_params
        if client_profile is not None:
            return client_profile

        # Legacy values may be out of the new reference ranges on old hosts.
        # Keep them readable so upgrades do not rotate or invalidate clients.
        return {
            "jc": self.awg_jc,
            "jmin": self.awg_jmin,
            "jmax": self.awg_jmax,
            "s1": self.awg_s1,
            "s2": self.awg_s2,
            "h1": self.awg_h1,
            "h2": self.awg_h2,
            "h3": self.awg_h3,
            "h4": self.awg_h4,
        }

    @property
    def awg_client_obfuscation_params(self) -> dict[str, int] | None:
        """Return validated CLIENT_PROFILE values when AWG_CLIENT_* is configured."""
        return self._explicit_awg_profile("awg_client")

    @property
    def awg_relay_obfuscation_params(self) -> dict[str, int] | None:
        """Return validated RELAY_PROFILE values when AWG_RELAY_* is configured."""
        return self._explicit_awg_profile("awg_relay")

    def _explicit_awg_profile(self, prefix: str) -> dict[str, int] | None:
        values = {
            key: getattr(self, f"{prefix}_{key}")
            for key in AWG_SETTING_BOUNDS
        }
        if all(value is None for value in values.values()):
            return None

        missing = [key for key, value in values.items() if value is None]
        if missing:
            raise ValueError(
                f"{prefix.upper()} profile is incomplete; missing: {', '.join(missing)}"
            )

        typed_values = {key: int(value) for key, value in values.items() if value is not None}
        self._validate_awg_profile_bounds(typed_values, prefix=prefix.upper())
        return typed_values

    def _validate_awg_profile_bounds(self, values: dict[str, int], *, prefix: str) -> None:
        for key, (minimum, maximum) in AWG_SETTING_BOUNDS.items():
            value = values[key]
            if value < minimum or value > maximum:
                raise ValueError(
                    f"{prefix}_{key.upper()}={value} outside approved range {minimum}..{maximum}"
                )
# END_BLOCK_SETTINGS_CLASS


# START_BLOCK_GET_SETTINGS
@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
# END_BLOCK_GET_SETTINGS
