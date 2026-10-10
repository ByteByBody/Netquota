"""Dashboard aggregation helpers (independent of the frontend)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Device, Group, UsageDelta
from ..schemas.dashboard import DashboardSummary, DeviceHealth
from ..schemas.groups import UsagePoint
from ..timeutil import utcnow
from .alerts import mark_stale_devices
from .devices import _is_stale
from .groups import get_active_group
from .quotas import get_or_create_period, group_summary


async def usage_series(
    session: AsyncSession,
    *,
    group_id: str | None = None,
    device_id: str | None = None,
    starts_at: datetime,
    ends_at: datetime,
    granularity: str = "day",
) -> list[UsagePoint]:
    """Bucket usage deltas by day (MVP granularity)."""
    conditions = [
        UsageDelta.recorded_at >= starts_at,
        UsageDelta.recorded_at < ends_at,
    ]
    if group_id is not None:
        conditions.append(UsageDelta.group_id == group_id)
    if device_id is not None:
        conditions.append(UsageDelta.device_id == device_id)

    rows = (
        await session.execute(
            select(
                UsageDelta.recorded_at,
                UsageDelta.received_bytes,
                UsageDelta.sent_bytes,
            ).where(*conditions)
        )
    ).all()

    buckets: dict[date, list[int]] = {}
    for recorded_at, received, sent in rows:
        key = recorded_at.date()
        agg = buckets.setdefault(key, [0, 0])
        agg[0] += int(received)
        agg[1] += int(sent)

    points: list[UsagePoint] = []
    cursor = starts_at.date()
    end_date = (ends_at - timedelta(microseconds=1)).date()
    while cursor <= end_date:
        received, sent = buckets.get(cursor, [0, 0])
        points.append(
            UsagePoint(
                bucket=cursor,
                received_bytes=received,
                sent_bytes=sent,
                total_bytes=received + sent,
            )
        )
        cursor += timedelta(days=1)
    return points


async def build_summary(session: AsyncSession, run_stale_check: bool = True) -> DashboardSummary:
    now = utcnow()
    if run_stale_check:
        await mark_stale_devices(session)

    devices = (await session.scalars(select(Device))).all()
    active = [d for d in devices if d.is_active]
    stale = [d for d in active if _is_stale(d)]
    reporting = [d for d in active if not _is_stale(d)]

    groups = (await session.scalars(select(Group).order_by(Group.name))).all()
    summaries = [await group_summary(session, g) for g in groups]

    # Totals across each group's active period.
    total_received = 0
    total_sent = 0
    active_starts: datetime | None = None
    active_ends: datetime | None = None
    for group, summary in zip(groups, summaries):
        if summary.period_starts_at and (
            active_starts is None or summary.period_starts_at < active_starts
        ):
            active_starts = summary.period_starts_at
        if summary.period_ends_at and (
            active_ends is None or summary.period_ends_at > active_ends
        ):
            active_ends = summary.period_ends_at
        period = await get_or_create_period(session, group)
        row = (
            await session.execute(
                select(
                    func.coalesce(func.sum(UsageDelta.received_bytes), 0),
                    func.coalesce(func.sum(UsageDelta.sent_bytes), 0),
                ).where(
                    UsageDelta.group_id == group.id,
                    UsageDelta.quota_period_id == period.id,
                )
            )
        ).one()
        total_received += int(row[0])
        total_sent += int(row[1])

    # Stale device list.
    stale_health = []
    for d in stale:
        group = await get_active_group(session, d.id)
        minutes = (
            int((now - d.last_seen_at).total_seconds() // 60)
            if d.last_seen_at
            else None
        )
        stale_health.append(
            DeviceHealth(
                id=d.id,
                name=d.name,
                platform=d.platform,
                group_name=group.name if group else None,
                last_seen_at=d.last_seen_at,
                minutes_since_report=minutes,
                measurement_quality=d.measurement_quality,
            )
        )

    from ..models import Event

    events = (
        await session.scalars(
            select(Event).order_by(Event.created_at.desc()).limit(15)
        )
    ).all()

    warnings: list[str] = []
    if any(
        d.measurement_scope in {"partial", "unsupported", "app_only"} for d in active
    ):
        warnings.append(
            "Some devices report only partial measurement coverage. Totals are "
            "device-reported usage, not guaranteed ISP-billed usage."
        )

    series: list[UsagePoint] = []
    if active_starts and active_ends:
        series = await usage_series(
            session, starts_at=active_starts, ends_at=active_ends
        )

    return DashboardSummary(
        generated_at=now,
        active_period_starts_at=active_starts,
        active_period_ends_at=active_ends,
        device_count=len(devices),
        reporting_device_count=len(reporting),
        stale_device_count=len(stale),
        revoked_device_count=len(devices) - len(active),
        total_received_bytes=total_received,
        total_sent_bytes=total_sent,
        total_bytes=total_received + total_sent,
        groups=summaries,
        recent_events=[
            {
                "id": e.id,
                "event_type": e.event_type,
                "created_at": e.created_at.isoformat(),
                "severity": e.severity,
                "message": e.message,
                "group_id": e.group_id,
                "device_id": e.device_id,
            }
            for e in events
        ],
        stale_devices=stale_health,
        measurement_warnings=warnings,
        usage_series=series,
    )