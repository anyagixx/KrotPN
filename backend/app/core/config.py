# FILE: backend/app/core/config.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Application configuration and environment variable parsing with validation
#   SCOPE: Settings model, environment parsing, secret validation, VPN network settings,
#          AmneziaWG params, anti-abuse, email verification, MTProto knobs, and edge domain/TLS/SNI-router settings
#   DEPENDS: M-032 (vpn-network-addressing-capacity)
#   LINKS: M-001 (backend-core), M-032, V-M-001, V-M-032
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   Settings - Pydantic BaseSettings model with all environment variables and validators
#   Settings.vpn_network - Resolved client/relay subnet configuration with capacity validation
#   Settings.awg_client_obfuscation_params - CLIENT_PROFILE mapping
#   Settings.awg_relay_obfuscation_params - RELAY_PROFILE mapping
#   Settings.anti_abuse_* - Observe/auto-rotate and endpoint-history thresholds
#   Settings.email_verification_* - Provider, TTL, URL and domain guard settings
#   Settings.mtproto_* - Personal MTProto proxy provisioning, private policy API, and live runtime bridge settings
#   Settings.edge_* - krotpn.xyz canonical domain, TLS path, shared 443, and DE-backed SNI-router contract
#   get_settings - lru_cache factory returning validated Settings singleton
#   settings - Module-level cached Settings instance
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v3.8.0 - Added Phase-42 MTProxy promotion tag setting validation.
#   LAST_CHANGE: v3.7.0 - Allow Phase-38 private DE MTProto policy targets and edge SNI-router settings.
#   LAST_CHANGE: v3.6.0 - Added Phase-37 MTProto runtime policy bridge URL and token validation.
#   LAST_CHANGE: v3.5.2 - Added Phase-36 Resend API URL, sender, and key format validation.
#   LAST_CHANGE: v3.5.1 - Treat blank optional MTProto secrets as unset so backend can degrade instead of crash.
#   LAST_CHANGE: v3.5.0 - Added Phase-32 krotpn.xyz domain TLS edge settings
#   LAST_CHANGE: v3.4.0 - Added Phase-29 MTProto provisioning settings
#   LAST_CHANGE: v3.3.0 - Added Phase-27 email verification provider, TTL and domain guard settings
#   LAST_CHANGE: v3.2.0 - Added configurable VPN client/relay subnet and capacity profile settings
#   LAST_CHANGE: v3.1.0 - Added anti-abuse mode, scan interval, history, ping-pong and cooldown settings
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
import ipaddress
import json
import re
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.vpn_network import (
    DEFAULT_VPN_CLIENT_SUBNET,
    DEFAULT_VPN_RELAY_SUBNET,
    VPNNetworkSettings,
    build_vpn_network_settings,
)


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

    # Anti-abuse / shared-config detection
    anti_abuse_mode: Literal["disabled", "observe", "auto_rotate"] = "observe"
    anti_abuse_scan_interval_seconds: int = Field(default=30, ge=5)
    anti_abuse_history_window_seconds: int = Field(default=300, ge=30)
    anti_abuse_history_ttl_seconds: int = Field(default=900, ge=60)
    anti_abuse_pingpong_window_seconds: int = Field(default=180, ge=30)
    anti_abuse_pingpong_min_alternations: int = Field(default=4, ge=4)
    anti_abuse_unique_ip_threshold: int = Field(default=4, ge=3)
    anti_abuse_enforcement_cooldown_seconds: int = Field(default=900, ge=60)

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
    # VPN_SUBNET is the legacy backend allocation knob. VPN_CLIENT_SUBNET is
    # preferred for new deployments; both are preserved to keep old .env files
    # upgrade-safe.
    vpn_subnet: str = DEFAULT_VPN_CLIENT_SUBNET
    vpn_client_subnet: str | None = None
    vpn_client_gateway: str | None = None
    vpn_relay_subnet: str = DEFAULT_VPN_RELAY_SUBNET
    vpn_relay_de_address: str | None = None
    vpn_relay_ru_address: str | None = None
    vpn_capacity_profile: int = Field(default=0, ge=0)
    vpn_network_rotate: bool = False
    vpn_port: int = 51821
    vpn_dns: str = "8.8.8.8, 1.1.1.1"
    vpn_mtu: int = 1360
    vpn_server_public_key: str | None = None
    vpn_server_endpoint: str | None = None
    vpn_server_name: str = "RU Entry Node"
    vpn_server_location: str = "Russia"
    vpn_server_max_clients: int = 1000
    vpn_entry_server_public_key: str | None = None
    vpn_entry_server_endpoint: str | None = None
    vpn_entry_server_name: str = "RU Entry Node"
    vpn_entry_server_location: str = "Russia"
    vpn_entry_server_country_code: str = "RU"
    vpn_entry_server_max_clients: int = 1000
    vpn_exit_server_public_key: str | None = None
    vpn_exit_server_endpoint: str | None = None
    vpn_exit_server_name: str = "DE Exit Node"
    vpn_exit_server_location: str = "Germany"
    vpn_exit_server_country_code: str = "DE"
    vpn_exit_server_max_clients: int = 1000
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

    # Email verification
    email_provider: Literal["disabled", "resend", "smtp"] = "disabled"
    email_verification_token_ttl_minutes: int = Field(default=30, ge=5, le=1440)
    email_verification_url_base: str | None = None
    email_provider_timeout_seconds: float = Field(default=10.0, ge=1.0, le=60.0)
    email_allowed_domains: Annotated[list[str], NoDecode] = Field(default_factory=list)
    email_blocked_domains: Annotated[list[str], NoDecode] = Field(default_factory=list)
    email_disposable_domain_guard_enabled: bool = True
    email_disposable_domains: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "10minutemail.com",
            "guerrillamail.com",
            "mailinator.com",
            "sharklasers.com",
            "temp-mail.org",
            "tempmail.com",
            "throwawaymail.com",
            "yopmail.com",
        ]
    )
    email_dns_check_enabled: bool = True
    resend_api_key: str | None = None
    resend_api_url: str = "https://api.resend.com/emails"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    email_from: str | None = None

    # MTProto personal proxy provisioning
    mtproto_base_domain: str = "krotpn.xyz"
    mtproto_proxy_port: int = Field(default=443, ge=1, le=65535)
    mtproto_base_secret_hex: str | None = None
    mtproto_secret_salt: str | None = None
    mtproto_sni_prefix: str = Field(default="u", min_length=1, max_length=24)
    mtproto_rotation_marker: str = Field(default="v1", min_length=1, max_length=64)
    mtproto_runtime_policy_url: str | None = None
    mtproto_runtime_token: str | None = None
    mtproto_runtime_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
    mtproto_policy_bind_ip: str = "127.0.0.1"
    mtproto_ad_tag: str = "00000000000000000000000000000000"

    # Public domain/TLS edge contract
    edge_public_domain: str = "krotpn.xyz"
    edge_canonical_host: str = "krotpn.xyz"
    edge_tls_certificate_path: str = "/etc/nginx/ssl/server.crt"
    edge_tls_certificate_key_path: str = "/etc/nginx/ssl/server.key"
    edge_tls_certificate_mode: Literal["operator-wildcard", "self-signed-dev"] = (
        "operator-wildcard"
    )
    edge_shared_443_enabled: bool = False
    edge_mtproto_mode: Literal["disabled", "local-ru", "de-backed"] = "de-backed"
    edge_mtproto_de_target_host: str | None = None
    edge_mtproto_de_target_port: int = Field(default=443, ge=1, le=65535)
    sni_router_conf_path: str = "./deploy/haproxy.runtime.cfg"

    # Referral
    referral_bonus_days: int = 7
    referral_min_payment: float = 100.0

    # Frontend
    frontend_url: str = "https://krotpn.xyz"

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

    @field_validator(
        "email_allowed_domains",
        "email_blocked_domains",
        "email_disposable_domains",
        mode="before",
    )
    @classmethod
    def parse_email_domain_list(cls, v: object) -> list[str]:
        """Parse comma-separated domain settings into normalized lower-case domains."""
        if v is None:
            return []
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith("["):
                try:
                    decoded = json.loads(stripped)
                    raw_items = decoded if isinstance(decoded, list) else [decoded]
                except json.JSONDecodeError:
                    raw_items = v.replace("\n", ",").split(",")
            else:
                raw_items = v.replace("\n", ",").split(",")
        else:
            raw_items = list(v) if isinstance(v, (list, tuple, set)) else [v]

        domains: list[str] = []
        for item in raw_items:
            domain = str(item).strip().lower().lstrip("@")
            if not domain:
                continue
            domains.append(domain.rstrip("."))
        return domains

    @field_validator("resend_api_key")
    @classmethod
    def validate_resend_api_key(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalized = v.strip()
        if not normalized:
            return None
        if not re.fullmatch(r"[-A-Za-z0-9._:=+/]{10,512}", normalized):
            raise ValueError("RESEND_API_KEY contains unsupported characters")
        return normalized

    @field_validator("resend_api_url")
    @classmethod
    def validate_resend_api_url(cls, v: str) -> str:
        normalized = v.strip()
        if normalized != "https://api.resend.com/emails":
            raise ValueError("RESEND_API_URL must be https://api.resend.com/emails")
        return normalized

    @field_validator("email_from")
    @classmethod
    def validate_email_from(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalized = v.strip().lower()
        if not normalized:
            return None
        if not re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", normalized):
            raise ValueError("EMAIL_FROM must be a valid sender email address")
        return normalized

    @field_validator("mtproto_base_domain")
    @classmethod
    def validate_mtproto_base_domain(cls, v: str) -> str:
        normalized = v.strip().lower().removeprefix("https://").removeprefix("http://")
        normalized = normalized.lstrip("*.").rstrip(".")
        if not normalized or "/" in normalized or ":" in normalized:
            raise ValueError("MTPROTO_BASE_DOMAIN must be a bare DNS domain")
        labels = normalized.split(".")
        if len(labels) < 2 or any(not label for label in labels):
            raise ValueError("MTPROTO_BASE_DOMAIN must contain at least two DNS labels")
        return normalized

    @field_validator("mtproto_base_secret_hex")
    @classmethod
    def validate_mtproto_base_secret_hex(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalized = v.strip().lower()
        if not normalized:
            return None
        if not re.fullmatch(r"[0-9a-f]{32}", normalized):
            raise ValueError("MTPROTO_BASE_SECRET_HEX must be exactly 32 hex characters")
        return normalized

    @field_validator("mtproto_secret_salt")
    @classmethod
    def validate_mtproto_secret_salt(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalized = v.strip().lower()
        if not normalized:
            return None
        if not re.fullmatch(r"[0-9a-f]{32}", normalized):
            raise ValueError("MTPROTO_SECRET_SALT must be exactly 32 hex characters")
        return normalized

    @field_validator("mtproto_sni_prefix")
    @classmethod
    def validate_mtproto_sni_prefix(cls, v: str) -> str:
        normalized = v.strip().lower().strip("-")
        if not re.fullmatch(r"[a-z0-9-]{1,24}", normalized):
            raise ValueError("MTPROTO_SNI_PREFIX must be a DNS label fragment")
        return normalized

    @field_validator("mtproto_rotation_marker")
    @classmethod
    def validate_mtproto_rotation_marker(cls, v: str) -> str:
        normalized = v.strip()
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", normalized):
            raise ValueError("MTPROTO_ROTATION_MARKER must be a safe opaque marker")
        return normalized

    @field_validator("mtproto_runtime_policy_url")
    @classmethod
    def validate_mtproto_runtime_policy_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalized = v.strip().rstrip("/")
        if not normalized:
            return None
        parsed = urlparse(normalized)
        if parsed.scheme != "http":
            raise ValueError(
                "MTPROTO_RUNTIME_POLICY_URL must use http for the private policy API"
            )
        hostname = parsed.hostname
        if not hostname or not cls._is_private_policy_host(hostname):
            raise ValueError(
                "MTPROTO_RUNTIME_POLICY_URL must target localhost or a private policy IP"
            )
        if not parsed.port or parsed.port < 1 or parsed.port > 65535:
            raise ValueError("MTPROTO_RUNTIME_POLICY_URL must include a valid policy port")
        if not parsed.path.startswith("/krotpn/mtproto/policy"):
            raise ValueError("MTPROTO_RUNTIME_POLICY_URL must target /krotpn/mtproto/policy")
        return normalized

    @field_validator("mtproto_policy_bind_ip")
    @classmethod
    def validate_mtproto_policy_bind_ip(cls, v: str) -> str:
        normalized = v.strip()
        try:
            address = ipaddress.ip_address(normalized)
        except ValueError as exc:
            raise ValueError("MTPROTO_POLICY_BIND_IP must be an IP address") from exc
        if address.is_unspecified or address.is_multicast:
            raise ValueError("MTPROTO_POLICY_BIND_IP must not be public wildcard or multicast")
        if not (address.is_loopback or address.is_private or address.is_link_local):
            raise ValueError("MTPROTO_POLICY_BIND_IP must be loopback or private")
        return str(address)

    @field_validator("mtproto_runtime_token")
    @classmethod
    def validate_mtproto_runtime_token(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalized = v.strip()
        if not normalized:
            return None
        if not re.fullmatch(r"[-A-Za-z0-9._~+/=]{24,512}", normalized):
            raise ValueError("MTPROTO_RUNTIME_TOKEN contains unsupported characters")
        return normalized

    @field_validator("mtproto_ad_tag")
    @classmethod
    def validate_mtproto_ad_tag(cls, v: str) -> str:
        if v != v.strip():
            raise ValueError("MTPROTO_AD_TAG must not contain surrounding whitespace")
        normalized = v.lower()
        if not re.fullmatch(r"[0-9a-f]{32}", normalized):
            raise ValueError("MTPROTO_AD_TAG must be exactly 32 hex characters")
        return normalized

    @field_validator("edge_public_domain", "edge_canonical_host")
    @classmethod
    def validate_edge_domain(cls, v: str) -> str:
        normalized = v.strip().lower().removeprefix("https://").removeprefix("http://")
        normalized = normalized.lstrip("*.").rstrip(".")
        if not normalized or "/" in normalized or ":" in normalized:
            raise ValueError("EDGE domain values must be bare DNS names")
        labels = normalized.split(".")
        if len(labels) < 2 or any(not label for label in labels):
            raise ValueError("EDGE domain values must contain at least two DNS labels")
        if any(not re.fullmatch(r"[a-z0-9-]{1,63}", label) for label in labels):
            raise ValueError("EDGE domain labels must be DNS-safe")
        return normalized

    @field_validator("edge_tls_certificate_path", "edge_tls_certificate_key_path")
    @classmethod
    def validate_edge_tls_path(cls, v: str) -> str:
        normalized = v.strip()
        if not normalized.startswith("/") or ".." in normalized or "\n" in normalized:
            raise ValueError("EDGE TLS paths must be absolute safe paths")
        return normalized

    @field_validator("edge_mtproto_de_target_host")
    @classmethod
    def validate_edge_mtproto_de_target_host(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalized = v.strip().lower().removeprefix("https://").removeprefix("http://")
        normalized = normalized.rstrip(".")
        if not normalized:
            return None
        if "/" in normalized or ":" in normalized or "\n" in normalized:
            raise ValueError("EDGE_MTPROTO_DE_TARGET_HOST must be a bare host or IP")
        try:
            address = ipaddress.ip_address(normalized)
        except ValueError:
            labels = normalized.split(".")
            if len(labels) < 2 or any(not label for label in labels):
                raise ValueError("EDGE_MTPROTO_DE_TARGET_HOST must be a DNS name or IP")
            if any(not re.fullmatch(r"[a-z0-9-]{1,63}", label) for label in labels):
                raise ValueError("EDGE_MTPROTO_DE_TARGET_HOST labels must be DNS-safe")
            return normalized
        if address.is_unspecified or address.is_multicast:
            raise ValueError("EDGE_MTPROTO_DE_TARGET_HOST must not be wildcard or multicast")
        return str(address)

    @field_validator("sni_router_conf_path")
    @classmethod
    def validate_sni_router_conf_path(cls, v: str) -> str:
        normalized = v.strip()
        if not normalized or ".." in normalized or "\n" in normalized:
            raise ValueError("SNI_ROUTER_CONF_PATH must be a safe relative or absolute path")
        if not (normalized.startswith("./") or normalized.startswith("/")):
            raise ValueError("SNI_ROUTER_CONF_PATH must start with ./ or /")
        return normalized

    @staticmethod
    def _is_private_policy_host(hostname: str) -> bool:
        if hostname == "localhost":
            return True
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            return False
        if address.is_unspecified or address.is_multicast:
            return False
        return address.is_loopback or address.is_private or address.is_link_local

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def edge_https_url(self) -> str:
        """Return the canonical public HTTPS origin for the production edge."""
        return f"https://{self.edge_canonical_host}"

    @property
    def edge_wildcard_domain(self) -> str:
        """Return the wildcard DNS name expected in the trusted edge certificate."""
        return f"*.{self.edge_public_domain}"

    @property
    def active_vpn_client_subnet(self) -> str:
        """Return the active client subnet with VPN_CLIENT_SUBNET preferred over legacy VPN_SUBNET."""
        return self.vpn_client_subnet or self.vpn_subnet

    @property
    def vpn_network(self) -> VPNNetworkSettings:
        """Return resolved VPN client/relay network settings."""
        return build_vpn_network_settings(
            client_subnet=self.active_vpn_client_subnet,
            client_gateway=self.vpn_client_gateway,
            relay_subnet=self.vpn_relay_subnet,
            relay_de_address=self.vpn_relay_de_address,
            relay_ru_address=self.vpn_relay_ru_address,
            capacity_profile=self.vpn_capacity_profile,
            rotate_enabled=self.vpn_network_rotate,
        )

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
