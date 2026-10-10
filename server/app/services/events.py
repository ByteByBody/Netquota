"""Event emission helper with deduplication support."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Event
from ..timeutil import utcnow


async def emit_event(
    session: AsyncSession,
    event_type: str,
    *,
    message: str | None = None,
    severity: str = "info",
    device_id: str | None = None,
    group_id: str | None = None,
    quota_period_id: str | None = None,
    details: dict | None = None,
    dedupe_key: str | None = None,
    created_at: datetime | None = None,
) -> Event | None:
    """Create an event.

    If ``dedupe_key`` is given and an event with that key already exists, no new
    row is written and ``None`` is returned.  This makes threshold alerts and
    stale alerts idempotent.
    """
    if dedupe_key is not None:
        existing = await session.scalar(
            select(Event.id).where(Event.dedupe_key == dedupe_key).limit(1)
        )
        if existing is not None:
            return None

    event = Event(
        event_type=event_type,
        created_at=created_at or utcnow(),
        device_id=device_id,
        group_id=group_id,
        quota_period_id=quota_period_id,
        severity=severity,
        message=message,
        details_json=json.dumps(details) if details else None,
        dedupe_key=dedupe_key,
    )
    session.add(event)
    await session.flush()
    return event