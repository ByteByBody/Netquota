"""Agent-facing endpoints: heartbeat, usage, config."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import get_settings
from ...database import get_session
from ...models import Device
from ...schemas.agent import (
    AgentConfigOut,
    HeartbeatIn,
    HeartbeatOut,
    UsageReportIn,
    UsageReportOut,
)
from ...security.deps import get_current_device
from ...services.usage import ingest_usage_report
from ...timeutil import utcnow

router = APIRouter()


@router.post("/agent/heartbeat", response_model=HeartbeatOut)
async def heartbeat(
    payload: HeartbeatIn,
    device: Device = Depends(get_current_device),
    session: AsyncSession = Depends(get_session),
) -> HeartbeatOut:
    now = utcnow()
    device.last_seen_at = now
    if payload.agent_version:
        device.agent_version = payload.agent_version
    if payload.measurement_scope:
        device.measurement_scope = payload.measurement_scope
    if payload.measurement_quality:
        device.measurement_quality = payload.measurement_quality
    if payload.capabilities:
        device.capabilities_json = json.dumps(payload.capabilities)
    if payload.last_sequence is not None:
        device.last_sequence = max(device.last_sequence or 0, payload.last_sequence)
    await session.commit()
    return HeartbeatOut(
        server_time=now,
        next_heartbeat_seconds=300,
        config_version=1,
        acknowledged_sequence=device.last_sequence,
    )


@router.post("/agent/usage", response_model=UsageReportOut)
async def report_usage(
    payload: UsageReportIn,
    device: Device = Depends(get_current_device),
    session: AsyncSession = Depends(get_session),
) -> UsageReportOut:
    result = await ingest_usage_report(session, device, payload)
    await session.commit()
    return result


@router.get("/agent/config", response_model=AgentConfigOut)
async def agent_config(
    device: Device = Depends(get_current_device),
    session: AsyncSession = Depends(get_session),
) -> AgentConfigOut:
    settings = get_settings()
    notes = []
    if device.measurement_scope in {"partial", "unsupported", "app_only"}:
        notes.append(
            "This device reports partial measurement coverage; totals are "
            "device-reported usage, not ISP-billed usage."
        )
    return AgentConfigOut(
        heartbeat_interval_seconds=300,
        reporting_interval_seconds=300,
        stale_after_minutes=settings.stale_after_minutes,
        interface_policy=settings.interface_policy,
        server_time=utcnow(),
        notes=notes,
    )