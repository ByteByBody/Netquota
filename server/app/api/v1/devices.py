"""Device management endpoints (admin)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...models import AdminUser, Device
from ...schemas.devices import DeviceDetailOut, DeviceOut, DevicePatch
from ...security.deps import get_current_admin
from ...services.devices import (
    get_device_detail,
    list_devices,
    patch_device,
    revoke_device,
)

router = APIRouter()


@router.get("/devices", response_model=list[DeviceOut])
async def get_devices(
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[DeviceOut]:
    return await list_devices(session)


@router.get("/devices/{device_id}", response_model=DeviceDetailOut)
async def get_device(
    device_id: str,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> DeviceDetailOut:
    device = await session.get(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")
    return await get_device_detail(session, device)


@router.patch("/devices/{device_id}", response_model=DeviceOut)
async def update_device(
    device_id: str,
    payload: DevicePatch,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> DeviceOut:
    device = await session.get(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")
    result = await patch_device(
        session,
        device,
        name=payload.name,
        group_id=payload.group_id,
        group_id_set="group_id" in payload.model_fields_set,
        is_active=payload.is_active,
        actor_admin_id=admin.id,
    )
    await session.commit()
    return result


@router.post("/devices/{device_id}/revoke", response_model=DeviceOut)
async def revoke(
    device_id: str,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> DeviceOut:
    device = await session.get(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")
    await revoke_device(session, device, actor_admin_id=admin.id)
    await session.commit()
    from ...services.devices import device_to_out

    return await device_to_out(session, device)