"""Device listing and management helpers."""

from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import Device, Group, UsageDelta, UsageSample
from ..schemas.devices import DeviceDetailOut, DeviceOut
from ..timeutil import utcnow
from .groups import get_active_group, set_device_group


def _is_stale(device: Device) -> bool:
    if device.last_seen_at is None:
        return device.is_active
    cutoff = utcnow() - timedelta(minutes=get_settings().stale_after_minutes)
    return device.last_seen_at < cutoff


async def device_to_out(session: AsyncSession, device: Device) -> DeviceOut:
    group = await get_active_group(session, device.id)
    return DeviceOut(
        id=device.id,
        name=device.name,
        platform=device.platform,
        agent_version=device.agent_version,
        created_at=device.created_at,
        last_seen_at=device.last_seen_at,
        is_active=device.is_active,
        measurement_scope=device.measurement_scope,
        measurement_quality=device.measurement_quality,
        last_sequence=device.last_sequence or 0,
        group_id=group.id if group else None,
        group_name=group.name if group else None,
        is_stale=_is_stale(device),
    )


async def list_devices(session: AsyncSession) -> list[DeviceOut]:
    devices = (await session.scalars(select(Device).order_by(Device.name))).all()
    return [await device_to_out(session, d) for d in devices]


async def get_device_detail(
    session: AsyncSession, device: Device
) -> DeviceDetailOut:
    base = await device_to_out(session, device)
    group = await get_active_group(session, device.id)

    received = sent = 0
    if group is not None:
        from .quotas import get_or_create_period

        period = await get_or_create_period(session, group)
        from sqlalchemy import func

        row = (
            await session.execute(
                select(
                    func.coalesce(func.sum(UsageDelta.received_bytes), 0),
                    func.coalesce(func.sum(UsageDelta.sent_bytes), 0),
                ).where(
                    UsageDelta.device_id == device.id,
                    UsageDelta.quota_period_id == period.id,
                )
            )
        ).one()
        received, sent = int(row[0]), int(row[1])

    interfaces = list(
        (
            await session.scalars(
                select(UsageSample.interface_name)
                .where(UsageSample.device_id == device.id)
                .distinct()
            )
        ).all()
    )

    try:
        capabilities = json.loads(device.capabilities_json) if device.capabilities_json else {}
    except (ValueError, TypeError):
        capabilities = {}

    warnings: list[str] = []
    if device.measurement_scope in {"partial", "unsupported", "app_only"}:
        warnings.append(
            f"Measurement scope '{device.measurement_scope}' covers only part of "
            "this device's traffic."
        )

    return DeviceDetailOut(
        **base.model_dump(),
        capabilities=capabilities,
        current_period_received=received,
        current_period_sent=sent,
        interfaces=interfaces,
        recent_warnings=warnings,
    )


async def patch_device(
    session: AsyncSession,
    device: Device,
    *,
    name: str | None = None,
    group_id: str | None = None,
    group_id_set: bool = False,
    is_active: bool | None = None,
    actor_admin_id: str | None = None,
) -> DeviceOut:
    if name is not None:
        device.name = name
    if is_active is not None:
        device.is_active = is_active
    if group_id_set:
        await set_device_group(session, device.id, group_id, actor_admin_id=actor_admin_id)
    await session.flush()
    return await device_to_out(session, device)


async def revoke_device(
    session: AsyncSession, device: Device, *, actor_admin_id: str | None = None
) -> None:
    from ..models.enums import EventType
    from .events import emit_event
    from ..security.secrets import generate_device_credential

    device.is_active = False
    # Rotate the credential so a stolen token is useless even if reactivated.
    _, cred_id, cred_hash = generate_device_credential(device.id)
    device.credential_id = cred_id
    device.credential_hash = cred_hash
    await session.flush()
    await emit_event(
        session,
        EventType.DEVICE_REVOKED,
        device_id=device.id,
        message=f"Device '{device.name}' revoked",
    )