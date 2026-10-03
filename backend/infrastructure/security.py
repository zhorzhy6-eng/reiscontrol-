"""Argon2 passwords and HS256 JWTs; secrets come from the environment."""

import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


class Argon2Passwords:
    """Verify passwords against Argon2id hashes."""

    def __init__(self) -> None:
        self.hasher = PasswordHasher()

    def verify(self, password_hash: str, password: str) -> bool:
        """Return false for an invalid password without logging the input."""
        try:
            return self.hasher.verify(password_hash, password)
        except VerifyMismatchError:
            return False


class Hs256Tokens:
    """Issue short-lived JWTs and opaque refresh tokens."""

    def __init__(self, secret: str) -> None:
        if len(secret) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 characters")
        self.secret = secret

    def access(self, user_id: UUID, device_id: UUID, role: str, now: datetime) -> str:
        """Issue an access token valid for fifteen minutes."""
        return jwt.encode(
            {
                "sub": str(user_id),
                "device_id": str(device_id),
                "role": role,
                "iat": now,
                "exp": now + timedelta(minutes=15),
            },
            self.secret,
            algorithm="HS256",
        )

    def decode(self, token: str) -> dict:
        """Validate and decode a signed access token."""
        return jwt.decode(token, self.secret, algorithms=["HS256"])

    def refresh(self) -> tuple[str, str]:
        """Return a random bearer secret and only its SHA-256 storage hash."""
        token = secrets.token_urlsafe(48)
        return token, self.refresh_hash(token)

    def refresh_hash(self, token: str) -> str:
        """Hash an opaque refresh token before database lookup."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
