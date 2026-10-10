"""Quota engine: periods, group aggregation, summaries.

Independent of the frontend and agents. All byte values are integers. Display
conversion happens only in the dashboard.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Device,
    Group,
    GroupAssignment,
    QuotaPeriod,
    UsageDelta,
)
from ..models.enums import EventType, MeasurementQuality
from ..schemas.groups import GroupQuotaSummary
from ..timeutil import month_bounds, utcnow
from .events import emit_event

_QUALITY_RANK = {
    MeasurementQuality.EXACT: 0,
    MeasurementQuality.ESTIMATED: 1,
    MeasurementQuality.PARTIAL: 2,
    MeasurementQuality.UNKNOWN: 3,
}


async def get_or_create_period(
    session: AsyncSession, group: Group, at: datetime | None = None
) -> QuotaPeriod:
    """Return the active quota period for ``group``, creating it if needed."""
    at = at or utcnow()
    starts_at, ends_at = month_bounds(at, group.reset_day)
    existing = await session.scalar(
        select(QuotaPeriod).where(
            QuotaPeriod.group_id == group.id,
            QuotaPeriod.starts_at == starts_at,
        )
    )
    if existing is not None:
        return existing

    period = QuotaPeriod(
        group_id=group.id,
        starts_at=starts_at,
        ends_at=ends_at,
        quota_bytes=int(group.default_quota_bytes or 0),
        created_at=utcnow(),
    )
    session.add(period)
    await session.flush()
    await emit_event(
        session,
        EventType.QUOTA_PERIOD_CREATED,
        group_id=group.id,
        quota_period_id=period.id,
        message=f"Quota period started for '{group.name}'",
        details={"quota_bytes": period.quota_bytes, "starts_at": starts_at.isoformat()},
    )
    return period


async def group_usage(
    session: AsyncSession, group_id: str, period_id: str
) -> tuple[int, int]:
    """Return ``(received, sent)`` bytes attributed to a group in a period."""
    stmt = select(
        func.coalesce(func.sum(UsageDelta.received_bytes), 0),
        func.coalesce(func.sum(UsageDelta.sent_bytes), 0),
    ).where(
        UsageDelta.group_id == group_id,
        UsageDelta.quota_period_id == period_id,
    )
    received, sent = (await session.execute(stmt)).one()
    return int(received), int(sent)


async def member_device_ids(session: AsyncSession, group_id: str) -> list[str]:
    rows = await session.execute(
        select(GroupAssignment.device_id).where(
            GroupAssignment.group_id == group_id,
            GroupAssignment.valid_until.is_(None),
        )
    )
    return [r[0] for r in rows]


async def group_summary(
    session: AsyncSession, group: Group, at: datetime | None = None
) -> GroupQuotaSummary:
    period = await get_or_create_period(session, group, at)
    received, sent = await group_usage(session, group.id, period.id)
    used = received + sent
    quota = int(period.quota_bytes or 0)
    remaining = max(0, quota - used)
    pct = (100.0 * used / quota) if quota > 0 else 0.0

    device_ids = await member_device_ids(session, group.id)
    quality = MeasurementQuality.EXACT
    missing = False
    if device_ids:
        devices = (
            await session.scalars(select(Device).where(Device.id.in_(device_ids)))
        ).all()
        for d in devices:
            if _QUALITY_RANK.get(d.measurement_quality, 3) > _QUALITY_RANK[quality]:
                quality = d.measurement_quality
            if d.measurement_scope in {
                "unsupported",
                "partial",
                "app_only",
            }:
                missing = True
    else:
        quality = MeasurementQuality.UNKNOWN

    return GroupQuotaSummary(
        group_id=group.id,
        group_name=group.name,
        quota_bytes=quota,
        used_bytes=used,
        remaining_bytes=remaining,
        percentage_used=round(pct, 2),
        period_starts_at=period.starts_at,
        period_ends_at=period.ends_at,
        device_count=len(device_ids),
        measurement_quality=quality,
        has_missing_measurements=missing,
    )