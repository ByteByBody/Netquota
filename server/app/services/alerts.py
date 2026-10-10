"""Alerting: quota thresholds and stale-agent detection. Deduplicated."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import Device, Event, Group, QuotaPeriod
from ..models.enums import EventType, THRESHOLDS
from ..timeutil import utcnow
from .events import emit_event
from .quotas import group_usage


def _threshold_event_type(threshold: int) -> str:
    return {
        80: EventType.THRESHOLD_80,
        90: EventType.THRESHOLD_90,
        100: EventType.THRESHOLD_100,
    }[threshold]


async def evaluate_thresholds(
    session: AsyncSession, group: Group, period_id: str
) -> list[int]:
    """Emit deduplicated threshold events. Return thresholds newly crossed."""
    period = await session.get(QuotaPeriod, period_id)
    if period is None or period.quota_bytes <= 0:
        return []
    received, sent = await group_usage(session, group.id, period.id)
    used = received + sent
    pct = 100.0 * used / period.quota_bytes
    crossed: list[int] = []
    for threshold in THRESHOLDS:
        if pct < threshold:
            continue
        dedupe_key = f"threshold:{period.id}:{threshold}"
        event = await emit_event(
            session,
            _threshold_event_type(threshold),
            group_id=group.id,
            quota_period_id=period.id,
            severity="critical" if threshold >= 100 else "warning",
            message=(
                f"Group '{group.name}' reached {threshold}% "
                f"({used} / {period.quota_bytes} bytes)"
            ),
            details={
                "threshold": threshold,
                "used_bytes": used,
                "quota_bytes": period.quota_bytes,
                "percentage": round(pct, 2),
            },
            dedupe_key=dedupe_key,
        )
        if event is not None:
            crossed.append(threshold)
    return crossed


async def mark_stale_devices(session: AsyncSession) -> int:
    """Emit stale-agent events for devices that stopped reporting.

    One event per stale episode: dedupe key includes the last-seen timestamp, so
    a device that recovers and goes stale again produces a new event.
    """
    settings = get_settings()
    cutoff = utcnow() - timedelta(minutes=settings.stale_after_minutes)
    devices = (
        await session.scalars(select(Device).where(Device.is_active.is_(True)))
    ).all()
    emitted = 0
    for device in devices:
        if device.last_seen_at is None or device.last_seen_at >= cutoff:
            continue
        dedupe_key = f"stale:{device.id}:{device.last_seen_at.isoformat()}"
        event = await emit_event(
            session,
            EventType.STALE_AGENT,
            device_id=device.id,
            severity="warning",
            message=f"Device '{device.name}' has not reported recently",
            details={
                "last_seen_at": device.last_seen_at.isoformat(),
                "stale_after_minutes": settings.stale_after_minutes,
            },
            dedupe_key=dedupe_key,
        )
        if event is not None:
            emitted += 1
    return emitted


async def active_threshold_events(
    session: AsyncSession, period_id: str
) -> list[Event]:
    return list(
        (
            await session.scalars(
                select(Event).where(
                    Event.quota_period_id == period_id,
                    Event.event_type.in_(
                        [
                            EventType.THRESHOLD_80,
                            EventType.THRESHOLD_90,
                            EventType.THRESHOLD_100,
                        ]
                    ),
                )
            )
        ).all()
    )