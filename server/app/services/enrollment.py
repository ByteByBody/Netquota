"""Enrollment: single-use, expiring codes; device registration."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import Device, EnrollmentCode, Group
from ..models.enums import EventType
from ..schemas.agent import EnrollIn
from ..security.secrets import (
    generate_device_credential,
    generate_enrollment_code,
    hash_enrollment_code,
)
from ..timeutil import utcnow
from .events import emit_event
from .groups import set_device_group


class EnrollmentError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


async def create_enrollment_code(
    session: AsyncSession,
    *,
    label: str | None = None,
    ttl_minutes: int | None = None,
    group_id: str | None = None,
    admin_id: str | None = None,
) -> tuple[EnrollmentCode, str]:
    settings = get_settings()
    raw, code_hash = generate_enrollment_code()
    now = utcnow()
    expires = now + timedelta(
        minutes=ttl_minutes or settings.enrollment_code_ttl_minutes
    )
    code = EnrollmentCode(
        code_hash=code_hash,
        label=label,
        group_id=group_id,
        created_at=now,
        expires_at=expires,
        created_by_admin_id=admin_id,
    )
    session.add(code)
    await session.flush()
    await emit_event(
        session,
        EventType.ENROLLMENT_CREATED,
        message=f"Enrollment code created{f' ({label})' if label else ''}",
        details={"expires_at": expires.isoformat(), "group_id": group_id},
    )
    return code, raw


async def enroll_device(
    session: AsyncSession, payload: EnrollIn
) -> tuple[Device, str]:
    now = utcnow()
    code_hash = hash_enrollment_code(payload.enrollment_code)
    code = await session.scalar(
        select(EnrollmentCode).where(EnrollmentCode.code_hash == code_hash)
    )
    if code is None:
        raise EnrollmentError("invalid enrollment code", 401)
    if code.is_revoked:
        raise EnrollmentError("enrollment code revoked", 401)
    if code.used_at is not None:
        raise EnrollmentError("enrollment code already used", 409)
    if code.expires_at < now:
        raise EnrollmentError("enrollment code expired", 410)

    import json

    device_id_placeholder = None
    raw, cred_id, cred_hash = generate_device_credential()
    device = Device(
        name=payload.name,
        platform=payload.platform,
        agent_version=payload.agent_version,
        credential_hash=cred_hash,
        credential_id=cred_id,
        created_at=now,
        last_seen_at=now,
        is_active=True,
        measurement_scope=payload.measurement_scope,
        measurement_quality=payload.measurement_quality,
        capabilities_json=json.dumps(payload.capabilities or {}),
        last_sequence=0,
    )
    session.add(device)
    await session.flush()

    # Re-issue credential bound to the real device id for traceability.
    raw, cred_id, cred_hash = generate_device_credential(device.id)
    device.credential_hash = cred_hash
    device.credential_id = cred_id

    code.used_at = now
    code.used_by_device_id = device.id
    await session.flush()

    # Pre-assign the group configured on the enrollment code, if any.
    if code.group_id:
        await set_device_group(session, device.id, code.group_id)

    await emit_event(
        session,
        EventType.ENROLLMENT_USED,
        device_id=device.id,
        message=f"Device '{device.name}' enrolled",
        details={"platform": device.platform, "code_id": code.id},
    )
    await emit_event(
        session,
        EventType.DEVICE_ACTIVATED,
        device_id=device.id,
        message=f"Device '{device.name}' activated",
    )
    return device, raw