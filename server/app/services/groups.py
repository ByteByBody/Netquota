"""Group membership helpers, preserving historical attribution."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Group, GroupAssignment
from ..models.enums import EventType
from ..timeutil import utcnow
from .events import emit_event


async def get_active_group(
    session: AsyncSession, device_id: str, at: datetime | None = None
) -> Group | None:
    """Return the group the device belonged to at ``at`` (default: now)."""
    at = at or utcnow()
    stmt = (
        select(Group)
        .join(GroupAssignment, GroupAssignment.group_id == Group.id)
        .where(
            GroupAssignment.device_id == device_id,
            GroupAssignment.valid_from <= at,
            (GroupAssignment.valid_until.is_(None))
            | (GroupAssignment.valid_until > at),
        )
        .order_by(GroupAssignment.valid_from.desc())
        .limit(1)
    )
    return await session.scalar(stmt)


async def get_open_assignment(
    session: AsyncSession, device_id: str
) -> GroupAssignment | None:
    return await session.scalar(
        select(GroupAssignment).where(
            GroupAssignment.device_id == device_id,
            GroupAssignment.valid_until.is_(None),
        )
    )


async def set_device_group(
    session: AsyncSession,
    device_id: str,
    group_id: str | None,
    *,
    at: datetime | None = None,
    actor_admin_id: str | None = None,
) -> GroupAssignment | None:
    """Close the current assignment and open a new one.

    Historical usage rows keep referencing the group that was active when the
    usage was recorded, so reassignment never rewrites history.
    """
    at = at or utcnow()
    current = await get_open_assignment(session, device_id)
    if current is not None:
        if current.group_id == group_id:
            return current
        current.valid_until = at

    if group_id is None:
        await emit_event(
            session,
            EventType.GROUP_CHANGED,
            device_id=device_id,
            message="Device removed from all groups",
            details={"previous_group_id": current.group_id if current else None},
        )
        return None

    group = await session.get(Group, group_id)
    if group is None:
        raise ValueError("group not found")

    assignment = GroupAssignment(
        device_id=device_id,
        group_id=group_id,
        valid_from=at,
        valid_until=None,
    )
    session.add(assignment)
    await session.flush()
    await emit_event(
        session,
        EventType.GROUP_CHANGED,
        device_id=device_id,
        group_id=group_id,
        message=f"Device assigned to group '{group.name}'",
        details={"previous_group_id": current.group_id if current else None},
    )
    return assignment