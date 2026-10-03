"""Password login and refresh-token use cases."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID


class AuthenticationError(PermissionError):
    """Credentials or refresh token are invalid."""


@dataclass(frozen=True, slots=True)
class AuthUser:
    """Minimal authenticated user projection."""

    id: UUID
    phone: str
    password_hash: str
    role: str
    is_active: bool
    full_name: str | None = None


@dataclass(frozen=True, slots=True)
class LoginTokens:
    """Tokens returned to an authenticated client."""

    access_token: str
    refresh_token: str
    expires_in: int
    user: AuthUser


class AuthRepository(Protocol):
    """Authentication persistence operations."""

    def get_by_phone(self, phone: str) -> AuthUser | None:
        """Load a user by phone."""

    def get_by_id(self, user_id: UUID) -> AuthUser | None:
        """Load a user by ID."""

    def register_device(
        self, user_id: UUID, device_id: UUID, platform: str, app_version: str
    ) -> None:
        """Associate the login device with its owner."""

    def save_refresh(
        self, user_id: UUID, device_id: UUID, token_hash: str, expires_at: datetime
    ) -> None:
        """Store only a hash of the refresh token."""

    def find_refresh_user(self, token_hash: str, now: datetime) -> tuple[UUID, UUID] | None:
        """Find a live refresh token and its bound device."""


class PasswordVerifier(Protocol):
    """Password hash verification boundary."""

    def verify(self, password_hash: str, password: str) -> bool:
        """Check a candidate without revealing the stored hash."""


class TokenService(Protocol):
    """JWT and random refresh-token boundary."""

    def access(self, user_id: UUID, device_id: UUID, role: str, now: datetime) -> str:
        """Issue a 15-minute signed access token."""

    def refresh(self) -> tuple[str, str]:
        """Return an opaque refresh token and its storage hash."""

    def refresh_hash(self, token: str) -> str:
        """Hash an incoming refresh token for lookup."""


def login(
    *,
    phone: str,
    password: str,
    device_id: UUID,
    platform: str,
    app_version: str,
    repository: AuthRepository,
    passwords: PasswordVerifier,
    tokens: TokenService,
    now: datetime | None = None,
) -> LoginTokens:
    """Authenticate a user and bind a refresh token to a device."""
    current = now or datetime.now(timezone.utc)
    user = repository.get_by_phone(phone)
    if user is None or not user.is_active or not passwords.verify(user.password_hash, password):
        raise AuthenticationError("Invalid credentials")
    repository.register_device(user.id, device_id, platform, app_version)
    refresh_token, token_hash = tokens.refresh()
    repository.save_refresh(user.id, device_id, token_hash, current + timedelta(days=30))
    return LoginTokens(
        access_token=tokens.access(user.id, device_id, user.role, current),
        refresh_token=refresh_token,
        expires_in=15 * 60,
        user=user,
    )


def refresh_access(
    refresh_token: str,
    *,
    repository: AuthRepository,
    tokens: TokenService,
    now: datetime | None = None,
) -> tuple[str, int]:
    """Issue a new access token for a live, device-bound refresh token."""
    current = now or datetime.now(timezone.utc)
    owner = repository.find_refresh_user(tokens.refresh_hash(refresh_token), current)
    if owner is None:
        raise AuthenticationError("Invalid refresh token")
    user_id, device_id = owner
    user = repository.get_by_id(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Invalid refresh token")
    return tokens.access(user.id, device_id, user.role, current), 15 * 60
