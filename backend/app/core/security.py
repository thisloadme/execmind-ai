"""ExecMind - JWT token management and password hashing utilities."""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jose import jwt, JWTError

from app.core.config import settings

BCRYPT_COST_FACTOR = 12

def _load_key(path: str) -> str:
    """Load RSA key from file path."""
    key_path = Path(path)
    if not key_path.exists():
        raise FileNotFoundError(f"JWT key not found: {path}")
    return key_path.read_text()

def _get_private_key() -> str:
    """Load JWT private key for signing tokens."""
    return _load_key(settings.JWT_PRIVATE_KEY_PATH)

def _get_public_key() -> str:
    """Load JWT public key for verifying tokens."""
    return _load_key(settings.JWT_PUBLIC_KEY_PATH)

import bcrypt

def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    salt = bcrypt.gensalt(rounds=BCRYPT_COST_FACTOR)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), 
        hashed_password.encode("utf-8")
    )


def create_access_token(user_id: str, username: str, role: str) -> str:
    """Create a short-lived JWT access token with RS256 signing.

    Args:
        user_id: UUID string of the user.
        username: Username for the token claims.
        role: User role for authorization.

    Returns:
        Encoded JWT access token string.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, _get_private_key(), algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived JWT refresh token with RS256 signing.

    Args:
        user_id: UUID string of the user.

    Returns:
        Encoded JWT refresh token string.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, _get_private_key(), algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token using the public key.

    Args:
        token: Encoded JWT token string.

    Returns:
        Decoded payload dictionary.

    Raises:
        JWTError: If token is invalid or expired.
    """
    return jwt.decode(
        token,
        _get_public_key(),
        algorithms=[settings.JWT_ALGORITHM],
    )


def hash_token(token: str) -> str:
    """Create a SHA-256 hash of a token for secure storage.

    Args:
        token: Raw token string.

    Returns:
        Hex digest of the SHA-256 hash.
    """
    return hashlib.sha256(token.encode()).hexdigest()
