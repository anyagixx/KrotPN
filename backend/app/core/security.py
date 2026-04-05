"""
Security module for authentication and authorization.
Handles JWT tokens, password hashing, and encryption.
"""
# <!-- GRACE: module="M-001" contract="authentication" -->

from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from loguru import logger
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# Data encryption (for sensitive data like VPN private keys)
_fernet: Fernet | None = None

# Redis connection for token blacklist (lazy init)
_redis_client: Any = None


def _get_redis():
    """Get or create Redis client for token blacklist."""
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as redis
            _redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
            )
        except Exception as e:
            logger.warning(f"[SECURITY] Redis unavailable for token blacklist: {e}")
            _redis_client = None
    return _redis_client


async def blacklist_token(token: str, expires_in_seconds: int | None = None) -> None:
    """Add a token to the blacklist so it cannot be reused."""
    r = _get_redis()
    if r is None:
        return
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        exp = payload.get("exp")
        if exp and expires_in_seconds is None:
            expires_in_seconds = max(0, int(exp) - int(datetime.now(timezone.utc).timestamp()))
        key = f"token:blacklist:{token}"
        await r.setex(key, expires_in_seconds or 3600, "1")
    except Exception as e:
        logger.warning(f"[SECURITY] Failed to blacklist token: {e}")


async def is_token_blacklisted(token: str) -> bool:
    """Check if a token has been blacklisted."""
    r = _get_redis()
    if r is None:
        return False
    try:
        return await r.exists(f"token:blacklist:{token}") > 0
    except Exception as e:
        logger.warning(f"[SECURITY] Failed to check token blacklist: {e}")
        return False


def get_fernet() -> Fernet:
    """Get Fernet instance for data encryption."""
    global _fernet
    if _fernet is None:
        if not settings.data_encryption_key:
            raise RuntimeError(
                "DATA_ENCRYPTION_KEY must be set in environment. "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        _fernet = Fernet(settings.data_encryption_key.encode())
    return _fernet


def encrypt_data(data: str) -> str:
    """Encrypt sensitive data."""
    return get_fernet().encrypt(data.encode()).decode()


def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data."""
    return get_fernet().decrypt(encrypted_data.encode()).decode()


def hash_password(password: str) -> str:
    """Hash a password using pbkdf2_sha256."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
    extra_data: dict[str, Any] | None = None,
) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "type": "access",
    }
    if extra_data:
        to_encode.update(extra_data)

    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


def create_refresh_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT refresh token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expire_days
        )

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "type": "refresh",
    }

    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


def verify_token(token: str, expected_type: str = "access") -> str | None:
    """
    Verify a JWT token and return the subject (user ID).
    Returns None if token is invalid or expired.
    """
    payload = decode_token(token)
    if payload is None:
        return None

    if payload.get("type") != expected_type:
        return None

    return payload.get("sub")


async def verify_token_with_blacklist(token: str, expected_type: str = "access") -> str | None:
    """
    Verify a JWT token and check it is not blacklisted.
    Returns the subject (user ID) or None.
    """
    if await is_token_blacklisted(token):
        return None
    return verify_token(token, expected_type)
