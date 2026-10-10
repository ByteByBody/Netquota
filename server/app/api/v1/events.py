"""Event listing (admin)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...models import AdminUser, Event
from ...schemas.events import EventOut
from ...security.deps import get_current_admin

router = APIRouter()


@router.get("/events", response_model=list[EventOut])
async def list_events(
    event_type: str | None = Query(default=None),
    group_id: str | None = Query(default=None),
    device_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[EventOut]:
    stmt = select(Event)
    if event_type:
        stmt = stmt.where(Event.event_type == event_type)
    if group_id:
        stmt = stmt.where(Event.group_id == group_id)
    if device_id:
        stmt = stmt.where(Event.device_id == device_id)
    stmt = stmt.order_by(Event.created_at.desc()).limit(limit)
    events = (await session.scalars(stmt)).all()
    out = []
    for e in events:
        try:
            details = json.loads(e.details_json) if e.details_json else {}
        except (ValueError, TypeError):
            details = {}
        out.append(
            EventOut(
                id=e.id,
                event_type=e.event_type,
                created_at=e.created_at,
                device_id=e.device_id,
                group_id=e.group_id,
                quota_period_id=e.quota_period_id,
                severity=e.severity,
                message=e.message,
                details=details,
            )
        )
    return out