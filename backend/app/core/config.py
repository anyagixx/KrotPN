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
#   get_settings - lru_cache factory returning validated Settings singleton
#   settings - Module-level cached Settings instance
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
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
        default="sqlite+aiosqlite:///./krtpn.db",
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

    # AmneziaWG Obfuscation Parameters (MUST match legacy)
    awg_jc: int = 120
    awg_jmin: int = 50
    awg_jmax: int = 1000
    awg_s1: int = 111
    awg_s2: int = 222
    awg_h1: int = 1
    awg_h2: int = 2
    awg_h3: int = 3
    awg_h4: int = 4

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
    frontend_url: str = "https://krtpn.com"

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
        """Return AmneziaWG obfuscation parameters as dict."""
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
# END_BLOCK_SETTINGS_CLASS


# START_BLOCK_GET_SETTINGS
@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
# END_BLOCK_GET_SETTINGS
