"""JWT creation/verification for administrator sessions."""

from __future__ import annotations

import uuid
from datetime import timedelta

import jwt

from ..config import get_settings
from ..timeutil import utcnow


def create_admin_token(admin_id: str, username: str) -> tuple[str, str, "object"]:
    """Return ``(token, jti, expires_at)``."""
    settings = get_settings()
    now = utcnow()
    expires_at = now + timedelta(minutes=settings.admin_token_ttl_minutes)
    jti = str(uuid.uuid4())
    payload = {
        "sub": admin_id,
        "username": username,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def decode_admin_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])