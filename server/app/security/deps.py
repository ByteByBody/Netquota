"""FastAPI authentication dependencies."""

from __future__ import annotations

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..models import AdminSession, AdminUser, Device
from ..timeutil import utcnow
from .secrets import credential_id_for, verify_device_credential
from .tokens import decode_admin_token


async def get_current_admin(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> AdminUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_admin_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    jti = payload.get("jti")
    admin_id = payload.get("sub")
    if not jti or not admin_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token payload")

    record = await session.scalar(
        select(AdminSession).where(AdminSession.token_id == jti)
    )
    if record is None or record.revoked_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session revoked")
    if record.expires_at < utcnow():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")

    admin = await session.get(AdminUser, admin_id)
    if admin is None or not admin.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Admin not found or inactive")
    return admin


async def get_current_device(
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    x_device_credential: str | None = Header(default=None, alias="X-Device-Credential"),
    session: AsyncSession = Depends(get_session),
) -> Device:
    if not x_device_id or not x_device_credential:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Missing device credentials"
        )
    device = await session.get(Device, x_device_id)
    if device is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown device")
    if not device.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Device revoked")
    # Fast lookup by credential id, then constant-time verify.
    if credential_id_for(x_device_credential) != device.credential_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credential")
    if not verify_device_credential(x_device_credential, device.credential_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credential")
    return device