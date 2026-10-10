"""Administrator authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import get_settings
from ...database import get_session
from ...models import AdminSession, AdminUser
from ...schemas.auth import AdminOut, LoginIn, TokenOut
from ...security.deps import get_current_admin
from ...security.passwords import verify_password
from ...security.ratelimit import check_rate_limit
from ...security.tokens import create_admin_token
from ...timeutil import utcnow

router = APIRouter()


@router.post("/auth/login", response_model=TokenOut)
async def login(
    payload: LoginIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    check_rate_limit(f"login:{request.client.host if request.client else 'x'}", get_settings().rate_limit_auth_per_minute)
    admin = await session.scalar(
        select(AdminUser).where(AdminUser.username == payload.username)
    )
    if admin is None or not admin.is_active or not verify_password(
        payload.password, admin.password_hash
    ):
        # Constant-ish response; do not reveal which part failed.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    token, jti, expires_at = create_admin_token(admin.id, admin.username)
    session.add(
        AdminSession(
            admin_id=admin.id,
            token_id=jti,
            created_at=utcnow(),
            expires_at=expires_at,
        )
    )
    admin.last_login_at = utcnow()
    await session.commit()
    return TokenOut(access_token=token, expires_at=expires_at)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    # Revoke all active sessions for this admin.
    sessions = (
        await session.scalars(
            select(AdminSession).where(
                AdminSession.admin_id == admin.id,
                AdminSession.revoked_at.is_(None),
            )
        )
    ).all()
    now = utcnow()
    for s in sessions:
        s.revoked_at = now
    await session.commit()


@router.get("/auth/me", response_model=AdminOut)
async def me(admin: AdminUser = Depends(get_current_admin)) -> AdminOut:
    return AdminOut(
        id=admin.id,
        username=admin.username,
        created_at=admin.created_at,
        last_login_at=admin.last_login_at,
    )