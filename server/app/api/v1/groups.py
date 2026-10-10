"""Group management and group usage endpoints (admin)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...models import AdminUser, Group, UsageDelta
from ...schemas.groups import (
    GroupCreate,
    GroupOut,
    GroupPatch,
    GroupQuotaSummary,
    GroupUsageOut,
    GroupUsageSeries,
    UsagePoint,
)
from ...security.deps import get_current_admin
from ...services.dashboard import usage_series
from ...services.quotas import get_or_create_period, group_summary, member_device_ids
from ...timeutil import utcnow

router = APIRouter()


async def _group_out(session: AsyncSession, group: Group) -> GroupOut:
    members = await member_device_ids(session, group.id)
    return GroupOut(
        id=group.id,
        name=group.name,
        description=group.description,
        created_at=group.created_at,
        reset_day=group.reset_day,
        device_count=len(members),
    )


@router.get("/groups", response_model=list[GroupOut])
async def list_groups(
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[GroupOut]:
    groups = (await session.scalars(select(Group).order_by(Group.name))).all()
    return [await _group_out(session, g) for g in groups]


@router.post("/groups", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> GroupOut:
    exists = await session.scalar(select(Group).where(Group.name == payload.name))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "group name already exists")
    group = Group(
        name=payload.name,
        description=payload.description,
        created_at=utcnow(),
        reset_day=payload.reset_day,
        default_quota_bytes=payload.quota_bytes or 0,
    )
    session.add(group)
    await session.flush()
    # Create the current quota period immediately so summaries are stable.
    await get_or_create_period(session, group)

    from ...services.groups import set_device_group

    for device_id in payload.device_ids:
        await set_device_group(session, device_id, group.id)
    await session.commit()
    return await _group_out(session, group)


@router.patch("/groups/{group_id}", response_model=GroupOut)
async def patch_group(
    group_id: str,
    payload: GroupPatch,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> GroupOut:
    group = await session.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "group not found")
    if payload.name is not None:
        group.name = payload.name
    if payload.description is not None:
        group.description = payload.description
    if payload.reset_day is not None:
        group.reset_day = payload.reset_day
    if payload.quota_bytes is not None:
        group.default_quota_bytes = payload.quota_bytes
        # Update the active period quota as well.
        period = await get_or_create_period(session, group)
        period.quota_bytes = payload.quota_bytes
    await session.flush()
    await session.commit()
    return await _group_out(session, group)


@router.post("/groups/{group_id}/devices/{device_id}", response_model=GroupOut)
async def assign_device(
    group_id: str,
    device_id: str,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> GroupOut:
    group = await session.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "group not found")
    from ...services.groups import set_device_group

    await set_device_group(session, device_id, group_id, actor_admin_id=admin.id)
    await session.commit()
    return await _group_out(session, group)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: str,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    group = await session.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "group not found")
    # Close open assignments; historical deltas keep their group reference.
    from ...models import GroupAssignment

    assignments = (
        await session.scalars(
            select(GroupAssignment).where(
                GroupAssignment.group_id == group_id,
                GroupAssignment.valid_until.is_(None),
            )
        )
    ).all()
    now = utcnow()
    for a in assignments:
        a.valid_until = now
    await session.delete(group)
    await session.commit()


@router.get("/groups/{group_id}/usage", response_model=GroupUsageOut)
async def group_usage_detail(
    group_id: str,
    days: int = Query(default=30, ge=1, le=400),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> GroupUsageOut:
    group = await session.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "group not found")
    summary: GroupQuotaSummary = await group_summary(session, group)
    series: list[UsagePoint] = []
    if summary.period_starts_at and summary.period_ends_at:
        series = await usage_series(
            session,
            group_id=group.id,
            starts_at=summary.period_starts_at,
            ends_at=summary.period_ends_at,
        )
    return GroupUsageOut(
        group_id=group.id, group_name=group.name, summary=summary, series=series
    )


@router.get("/groups/{group_id}/usage/series", response_model=GroupUsageSeries)
async def group_usage_series(
    group_id: str,
    granularity: str = Query(default="day", pattern="^(day|month)$"),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> GroupUsageSeries:
    group = await session.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "group not found")
    summary = await group_summary(session, group)
    series = []
    if summary.period_starts_at and summary.period_ends_at:
        series = await usage_series(
            session,
            group_id=group.id,
            starts_at=summary.period_starts_at,
            ends_at=summary.period_ends_at,
            granularity=granularity,
        )
    return GroupUsageSeries(
        group_id=group.id, granularity=granularity, series=series
    )