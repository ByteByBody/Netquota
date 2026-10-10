"""Enrollment endpoints (agent + admin)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import get_settings
from ...database import get_session
from ...models import AdminUser, Device, EnrollmentCode, Group
from ...models.enums import EventType
from ...schemas.agent import EnrollIn, EnrollOut
from ...schemas.enrollment import (
    EnrollmentCodeCreate,
    EnrollmentCodeCreated,
    EnrollmentCodeOut,
)
from ...security.deps import get_current_admin
from ...security.ratelimit import check_rate_limit
from ...services.enrollment import EnrollmentError, create_enrollment_code, enroll_device
from ...services.events import emit_event
from ...services.groups import set_device_group
from ...timeutil import utcnow

router = APIRouter()


@router.post("/enroll", response_model=EnrollOut)
async def enroll(
    payload: EnrollIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> EnrollOut:
    settings = get_settings()
    check_rate_limit(
        f"enroll:{request.client.host if request.client else 'x'}",
        settings.rate_limit_enroll_per_minute,
    )
    try:
        device, credential = await enroll_device(session, payload)
    except EnrollmentError as exc:
        await session.rollback()
        raise HTTPException(exc.status_code, exc.message)
    await session.commit()
    return EnrollOut(
        device_id=device.id,
        credential=credential,
        heartbeat_interval_seconds=300,
        reporting_interval_seconds=300,
        server_time=utcnow(),
    )


# --- Admin: enrollment-code management -------------------------------------


@router.post(
    "/enrollment/codes",
    response_model=EnrollmentCodeCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_code(
    payload: EnrollmentCodeCreate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> EnrollmentCodeCreated:
    if payload.group_id is not None:
        group = await session.get(Group, payload.group_id)
        if group is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "group not found")
    code, raw = await create_enrollment_code(
        session,
        label=payload.label,
        ttl_minutes=payload.ttl_minutes,
        group_id=payload.group_id,
        admin_id=admin.id,
    )
    await session.commit()
    return EnrollmentCodeCreated(
        id=code.id,
        code=raw,
        label=code.label,
        expires_at=code.expires_at,
        group_id=payload.group_id,
    )


@router.get("/enrollment/codes", response_model=list[EnrollmentCodeOut])
async def list_codes(
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[EnrollmentCodeOut]:
    now = utcnow()
    codes = (
        await session.scalars(
            select(EnrollmentCode).order_by(EnrollmentCode.created_at.desc()).limit(100)
        )
    ).all()
    return [
        EnrollmentCodeOut(
            id=c.id,
            label=c.label,
            created_at=c.created_at,
            expires_at=c.expires_at,
            used_at=c.used_at,
            used_by_device_id=c.used_by_device_id,
            is_revoked=c.is_revoked,
            is_expired=c.expires_at < now,
        )
        for c in codes
    ]


@router.delete(
    "/enrollment/codes/{code_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def revoke_code(
    code_id: str,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    code = await session.get(EnrollmentCode, code_id)
    if code is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "code not found")
    code.is_revoked = True
    await session.commit()