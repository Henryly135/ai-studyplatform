import hashlib
import hmac
import base64
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings

_PASSWORD_HASH_SCHEME = "pbkdf2_sha256"
_PASSWORD_HASH_ITERATIONS = 600_000
_PASSWORD_SALT_BYTES = 16
_LEGACY_SHA256_HEX_LENGTH = 64


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_PASSWORD_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _PASSWORD_HASH_ITERATIONS,
    )
    return f"{_PASSWORD_HASH_SCHEME}${_PASSWORD_HASH_ITERATIONS}${_b64encode(salt)}${_b64encode(derived)}"


def verify_password(plain_password: str, password_hash: str) -> bool:
    if password_hash.startswith(f"{_PASSWORD_HASH_SCHEME}$"):
        try:
            _, iterations_text, salt_text, expected_text = password_hash.split("$", 3)
            iterations = int(iterations_text)
            salt = _b64decode(salt_text)
            expected = _b64decode(expected_text)
        except (ValueError, TypeError):
            return False

        derived = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(derived, expected)

    if _is_legacy_sha256_hash(password_hash):
        legacy_hash = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(legacy_hash, password_hash)

    return False


def password_hash_needs_upgrade(password_hash: str) -> bool:
    if not password_hash.startswith(f"{_PASSWORD_HASH_SCHEME}$"):
        return True
    try:
        _, iterations_text, _, _ = password_hash.split("$", 3)
        return int(iterations_text) < _PASSWORD_HASH_ITERATIONS
    except (ValueError, TypeError):
        return True


def _is_legacy_sha256_hash(password_hash: str) -> bool:
    return len(password_hash) == _LEGACY_SHA256_HEX_LENGTH and all(
        character in "0123456789abcdef" for character in password_hash.lower()
    )


def generate_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(user_id: int, identity: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    payload = {
        "sub": str(user_id),
        "identity": identity,
        "iat": datetime.now(timezone.utc),
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """
    Decodes and validates a JWT access token.
    Raises jwt.ExpiredSignatureError if expired, jwt.InvalidTokenError if invalid.
    """
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
