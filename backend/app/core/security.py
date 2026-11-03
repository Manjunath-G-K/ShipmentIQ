"""Password, JWT, and CSRF primitives for the authentication boundary."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings


PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
_password_hasher = PasswordHasher(type=Type.ID)


def hash_password(password: str) -> str:
    """Hash a password using Argon2id with a random salt."""

    validate_password(password)
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password without exposing hash or verifier errors to callers."""

    try:
        return _password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def validate_password(password: str) -> None:
    """Reject empty, excessively long, or too-short password input."""

    if not isinstance(password, str) or not (
        PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH
    ):
        raise ValueError(
            f"Password must be between {PASSWORD_MIN_LENGTH} and "
            f"{PASSWORD_MAX_LENGTH} characters"
        )


def create_access_token(user_id: UUID, settings: Settings) -> str:
    """Create a short-lived JWT with required identity and validation claims."""

    if not settings.jwt_secret_key:
        raise RuntimeError("JWT_SECRET_KEY is required for authentication")

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
        "jti": str(uuid4()),
        "token_type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> UUID:
    """Validate a JWT and return only its subject identity."""

    if not settings.jwt_secret_key:
        raise RuntimeError("JWT_SECRET_KEY is required for authentication")

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={
                "require": ["sub", "iss", "aud", "iat", "exp", "jti", "token_type"]
            },
        )
        if payload.get("token_type") != "access":
            raise jwt.InvalidTokenError("unexpected token type")
        return UUID(str(payload["sub"]))
    except (jwt.InvalidTokenError, ValueError, TypeError) as exc:
        raise ValueError("Invalid access token") from exc


def _csrf_signature(nonce: str, session_token: str, secret_key: str) -> str:
    message = f"{session_token}.{nonce}".encode("utf-8")
    return hmac.new(secret_key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def new_csrf_token(session_token: str, settings: Settings) -> str:
    """Create a signed double-submit value bound to the current JWT cookie."""

    nonce = secrets.token_urlsafe(32)
    signature = _csrf_signature(nonce, session_token, settings.jwt_secret_key)
    return f"{nonce}.{signature}"


def csrf_tokens_match(
    cookie_token: str | None,
    header_token: str | None,
    session_token: str | None,
    settings: Settings,
) -> bool:
    """Compare CSRF values and reject injected values without a valid signature."""

    if not cookie_token or not header_token or not session_token:
        return False
    if not secrets.compare_digest(cookie_token, header_token):
        return False
    try:
        nonce, signature = cookie_token.split(".", maxsplit=1)
    except ValueError:
        return False
    expected = _csrf_signature(nonce, session_token, settings.jwt_secret_key)
    return hmac.compare_digest(signature, expected)
