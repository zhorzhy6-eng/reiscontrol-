"""Authentication use cases and signed token tests."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from argon2 import PasswordHasher

from backend.application.auth import (
    AuthenticationError,
    AuthUser,
    login,
    refresh_access,
)
from backend.infrastructure.security import Argon2Passwords, Hs256Tokens

NOW = datetime.now(timezone.utc)


class FakeAuthRepository:
    def __init__(self):
        self.user = AuthUser(
            id=uuid4(),
            phone="+70000000000",
            password_hash=PasswordHasher().hash("correct-password"),
            role="driver",
            is_active=True,
        )
        self.device_id = None
        self.refresh_hash = None
        self.expires_at = None

    def get_by_phone(self, phone):
        return self.user if phone == self.user.phone else None

    def get_by_id(self, user_id):
        return self.user if user_id == self.user.id else None

    def register_device(self, user_id, device_id, platform, app_version):
        self.device_id = device_id

    def save_refresh(self, user_id, device_id, token_hash, expires_at):
        self.refresh_hash = token_hash
        self.expires_at = expires_at

    def find_refresh_user(self, token_hash, now):
        if token_hash == self.refresh_hash and now < self.expires_at:
            return self.user.id, self.device_id
        return None


def test_login_issues_device_bound_access_and_hashed_refresh():
    repository = FakeAuthRepository()
    tokens = Hs256Tokens("a" * 32)
    device_id = uuid4()
    response = login(
        phone=repository.user.phone,
        password="correct-password",
        device_id=device_id,
        platform="android",
        app_version="1.0.0",
        repository=repository,
        passwords=Argon2Passwords(),
        tokens=tokens,
        now=NOW,
    )
    assert repository.refresh_hash != response.refresh_token
    assert tokens.decode(response.access_token)["device_id"] == str(device_id)
    assert response.expires_in == 900
    access, expires_in = refresh_access(
        response.refresh_token, repository=repository, tokens=tokens, now=NOW
    )
    assert tokens.decode(access)["sub"] == str(repository.user.id)
    assert expires_in == 900
    with pytest.raises(AuthenticationError):
        refresh_access(
            response.refresh_token,
            repository=repository,
            tokens=tokens,
            now=NOW + timedelta(days=31),
        )


def test_login_rejects_bad_password_and_refresh_expiry():
    repository = FakeAuthRepository()
    tokens = Hs256Tokens("a" * 32)
    with pytest.raises(AuthenticationError):
        login(
            phone=repository.user.phone,
            password="wrong",
            device_id=uuid4(),
            platform="android",
            app_version="1.0.0",
            repository=repository,
            passwords=Argon2Passwords(),
            tokens=tokens,
            now=NOW,
        )
    with pytest.raises(AuthenticationError):
        refresh_access("invalid", repository=repository, tokens=tokens, now=NOW)
