"""
MODULE_CONTRACT
- PURPOSE: Verify core security primitives (JWT, password hashing, encryption).
- SCOPE: Unit tests for create_access_token, create_refresh_token, decode_token, verify_token, hash_password, verify_password, encrypt_data, decrypt_data, get_fernet.
- DEPENDS: app.core.security, app.core.config.
- LINKS: V-M-001.

MODULE_MAP
- test_create_access_token_has_correct_subject_and_type: Verifies JWT access token payload.
- test_create_refresh_token_has_correct_type: Verifies JWT refresh token payload.
- test_decode_token_returns_payload_for_valid_token: Verifies successful decode.
- test_decode_token_returns_none_for_tampered_token: Verifies tampered token rejection.
- test_decode_token_returns_none_for_expired_token: Verifies expired token rejection.
- test_verify_token_returns_user_id_for_valid_access: Verifies access token verification.
- test_verify_token_returns_none_for_refresh_when_expecting_access: Verifies type mismatch.
- test_hash_password_and_verify_password: Verifies password roundtrip.
- test_encrypt_data_and_decrypt_data_roundtrip: Verifies encryption roundtrip.
- test_get_fernet_raises_without_data_encryption_key: Verifies missing key error.

CHANGE_SUMMARY
- 2026-04-05: Added security unit tests for Phase 5.
"""

from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from jose import jwt

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_token,
    hash_password,
    verify_password,
    encrypt_data,
    decrypt_data,
    get_fernet,
)
from app.core import security as sec_module


def test_create_access_token_has_correct_subject_and_type(monkeypatch):
    monkeypatch.setattr(sec_module.settings, "secret_key", "test-secret-key-for-jwt-tests")
    token = create_access_token(subject=42)
    payload = jwt.decode(token, "test-secret-key-for-jwt-tests", algorithms=["HS256"])
    assert payload["sub"] == "42"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_create_refresh_token_has_correct_type(monkeypatch):
    monkeypatch.setattr(sec_module.settings, "secret_key", "test-secret-key-for-jwt-tests")
    token = create_refresh_token(subject=7)
    payload = jwt.decode(token, "test-secret-key-for-jwt-tests", algorithms=["HS256"])
    assert payload["sub"] == "7"
    assert payload["type"] == "refresh"


def test_decode_token_returns_payload_for_valid_token(monkeypatch):
    monkeypatch.setattr(sec_module.settings, "secret_key", "test-secret-key-for-jwt-tests")
    token = create_access_token(subject=10)
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "10"
    assert payload["type"] == "access"


def test_decode_token_returns_none_for_tampered_token(monkeypatch):
    monkeypatch.setattr(sec_module.settings, "secret_key", "test-secret-key-for-jwt-tests")
    token = create_access_token(subject=10)
    tampered = token[:-5] + "XXXXX"
    assert decode_token(tampered) is None


def test_decode_token_returns_none_for_expired_token(monkeypatch):
    monkeypatch.setattr(sec_module.settings, "secret_key", "test-secret-key-for-jwt-tests")
    secret = "test-secret-key-for-jwt-tests"
    expired = datetime.now(timezone.utc) - timedelta(hours=1)
    to_encode = {"sub": "1", "exp": expired, "type": "access"}
    token = jwt.encode(to_encode, secret, algorithm="HS256")
    assert decode_token(token) is None


def test_verify_token_returns_user_id_for_valid_access(monkeypatch):
    monkeypatch.setattr(sec_module.settings, "secret_key", "test-secret-key-for-jwt-tests")
    token = create_access_token(subject="abc-123")
    result = verify_token(token, expected_type="access")
    assert result == "abc-123"


def test_verify_token_returns_none_for_refresh_when_expecting_access(monkeypatch):
    monkeypatch.setattr(sec_module.settings, "secret_key", "test-secret-key-for-jwt-tests")
    token = create_refresh_token(subject=5)
    result = verify_token(token, expected_type="access")
    assert result is None


def test_hash_password_and_verify_password():
    plain = "super-secret-password"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_encrypt_data_and_decrypt_data_roundtrip(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(sec_module.settings, "data_encryption_key", key)
    sec_module._fernet = None

    original = "sensitive-data-to-encrypt"
    encrypted = encrypt_data(original)
    assert encrypted != original

    decrypted = decrypt_data(encrypted)
    assert decrypted == original

    sec_module._fernet = None


def test_get_fernet_raises_without_data_encryption_key(monkeypatch):
    from app.core.config import Settings

    fake_settings = Settings(
        secret_key="test-secret-key-for-jwt-tests",
        data_encryption_key=None,
    )
    monkeypatch.setattr(sec_module, "settings", fake_settings)
    sec_module._fernet = None

    with pytest.raises(RuntimeError, match="DATA_ENCRYPTION_KEY must be set"):
        get_fernet()

    sec_module._fernet = None
