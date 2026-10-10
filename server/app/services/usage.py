"""Usage ingestion: the accounting engine.

Agents submit cumulative counters.  This module converts successive valid
observations into deltas, transactionally, handling counter resets, interface
changes, out-of-order samples, duplicates and agent restarts.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import Device, Group, GroupAssignment, UsageDelta, UsageSample
from ..models.enums import EventType
from ..schemas.agent import AcceptedInterface, UsageReportIn, UsageReportOut
from ..timeutil import to_utc, utcnow
from .events import emit_event
from .quotas import get_or_create_period

# Interfaces we never count when the policy is "primary": virtual/bridge/VPN.
_VIRTUAL_PREFIXES = (
    "lo",
    "docker",
    "br-",
    "veth",
    "virbr",
    "vmnet",
    "vboxnet",
    "tun",
    "tap",
    "wg",
    "utun",
    "awdl",
    "llw",
    "bridge",
    "teredo",
    "isatap",
    "vEthernet",
    "Loopback",
    "Bluetooth",
    "Npcap",
)
_SKIP_PREFIX_LOWER = tuple(p.lower() for p in ("docker", "br-", "veth", "virbr", "vboxnet", "tun", "tap", "wg", "utun"))


def _normalise(name: str) -> str:
    return name.strip().lower().replace(" ", "")


def is_virtual_interface(name: str) -> bool:
    n = _normalise(name)
    return any(n.startswith(p) for p in _SKIP_PREFIX_LOWER) or n.startswith("veth")


def _selectable(name: str) -> bool:
    """Whether an interface should be counted under the primary policy."""
    return not is_virtual_interface(name)


async def _previous_sample(
    session: AsyncSession,
    device_id: str,
    interface_name: str,
    sequence: int,
    observed_at,
) -> UsageSample | None:
    """Most recent accepted sample for (device, interface) strictly before this one.

    Ordering is by sequence, then observed_at, so out-of-order arrivals are
    handled deterministically.
    """
    stmt = (
        select(UsageSample)
        .where(
            UsageSample.device_id == device_id,
            UsageSample.interface_name == interface_name,
            UsageSample.sequence < sequence,
        )
        .order_by(UsageSample.sequence.desc())
        .limit(1)
    )
    return await session.scalar(stmt)


def _compute_delta(
    prev: UsageSample | None,
    received_total: int,
    sent_total: int,
    reset_flag: bool,
) -> tuple[int, int, bool, str]:
    """Return ``(received_delta, sent_delta, from_reset, reason)``.

    Rules:
      * No previous sample (not even on another interface) -> baseline, 0 delta.
      * Agent signalled a reset -> discard old counter, delta = new totals.
      * Counter went backwards (wrap/reset) -> treat as reset, delta = new totals.
      * Otherwise -> simple difference.
    """
    if prev is None:
        return 0, 0, False, "baseline"
    if reset_flag:
        return received_total, sent_total, True, "agent_reset"
    if received_total < prev.bytes_received_total or sent_total < prev.bytes_sent_total:
        return received_total, sent_total, True, "counter_went_backwards"
    return (
        received_total - prev.bytes_received_total,
        sent_total - prev.bytes_sent_total,
        False,
        "ok",
    )


async def _device_has_any_sample(session: AsyncSession, device_id: str) -> bool:
    count = await session.scalar(
        select(func.count()).select_from(UsageSample).where(
            UsageSample.device_id == device_id
        )
    )
    return bool(count)


async def ingest_usage_report(
    session: AsyncSession,
    device: Device,
    report: UsageReportIn,
) -> UsageReportOut:
    settings = get_settings()
    now = utcnow()
    observed_at = to_utc(report.observed_at) or now

    # --- Validate timestamp -------------------------------------------------
    if observed_at > now + timedelta(seconds=settings.max_clock_skew_seconds):
        return UsageReportOut(
            accepted=False,
            reason="observed_at too far in the future",
            server_time=now,
            acknowledged_sequence=device.last_sequence,
        )

    # --- Idempotency: exact replay of an already-known sequence -------------
    seen = await session.scalar(
        select(func.count()).select_from(UsageSample).where(
            UsageSample.device_id == device.id,
            UsageSample.sequence == report.sequence,
        )
    )
    if seen and seen >= max(1, len(report.interfaces)):
        return UsageReportOut(
            accepted=True,
            duplicate=True,
            reason="sequence already processed",
            server_time=now,
            acknowledged_sequence=device.last_sequence or report.sequence,
        )

    # --- Late / out-of-order old sequence -----------------------------------
    if device.last_sequence and report.sequence < device.last_sequence:
        # Only accept if this sequence was never stored (partial gap fill).
        if seen:
            return UsageReportOut(
                accepted=True,
                duplicate=True,
                reason="out-of-order duplicate ignored",
                server_time=now,
                acknowledged_sequence=device.last_sequence,
            )

    first_ever = not await _device_has_any_sample(session, device.id)

    # Resolve active group + period once for this report.
    group: Group | None = None
    period_id: str | None = None
    assignment = await session.scalar(
        select(GroupAssignment).where(
            GroupAssignment.device_id == device.id,
            GroupAssignment.valid_until.is_(None),
        )
    )
    if assignment is not None:
        period = await get_or_create_period(session, await session.get(Group, assignment.group_id), observed_at)
        period_id = period.id
        # Bind the period onto the assignment for historical clarity.
        if assignment.quota_period_id is None:
            assignment.quota_period_id = period.id
        group = await session.get(Group, assignment.group_id)

    accepted_interfaces: list[AcceptedInterface] = []
    total_received = 0
    total_sent = 0
    duplicate = False

    for iface in report.interfaces:
        prev = await _previous_sample(
            session, device.id, iface.name, report.sequence, observed_at
        )
        # A brand-new interface after the device already reported: establish
        # baseline without counting (avoids counting a pre-existing counter).
        prev_any = prev
        if prev_any is None and not first_ever:
            prev_any = await session.scalar(
                select(UsageSample)
                .where(
                    UsageSample.device_id == device.id,
                    UsageSample.interface_name == iface.name,
                )
                .order_by(UsageSample.sequence.desc())
                .limit(1)
            )

        r_delta, s_delta, from_reset, reason = _compute_delta(
            prev, iface.bytes_received_total, iface.bytes_sent_total, iface.reset
        )

        sample = UsageSample(
            device_id=device.id,
            sequence=report.sequence,
            observed_at=observed_at,
            received_at=now,
            interface_name=iface.name,
            bytes_received_total=iface.bytes_received_total,
            bytes_sent_total=iface.bytes_sent_total,
            measurement_scope=report.measurement_scope,
            measurement_quality=report.measurement_quality,
            reset_flag=bool(iface.reset),
        )
        counted = _selectable(iface.name) or settings.interface_policy == "all"
        try:
            # Savepoint so a concurrent duplicate only rolls back this interface.
            async with session.begin_nested():
                session.add(sample)
                await session.flush()
                if counted:
                    session.add(
                        UsageDelta(
                            device_id=device.id,
                            group_id=group.id if group else None,
                            quota_period_id=period_id,
                            sample_id=sample.id,
                            received_bytes=r_delta,
                            sent_bytes=s_delta,
                            recorded_at=observed_at,
                            from_reset=from_reset,
                        )
                    )
                    await session.flush()
        except IntegrityError:
            duplicate = True
            accepted_interfaces.append(
                AcceptedInterface(
                    name=iface.name,
                    received_bytes=0,
                    sent_bytes=0,
                    accepted=False,
                    reason="duplicate sample",
                )
            )
            continue
        else:
            duplicate = False

        if counted:
            total_received += r_delta
            total_sent += s_delta

        if from_reset:
            await emit_event(
                session,
                EventType.COUNTER_RESET,
                device_id=device.id,
                group_id=group.id if group else None,
                severity="warning",
                message=f"Counter reset detected on interface '{iface.name}'",
                details={"sequence": report.sequence, "reason": reason},
            )

        accepted_interfaces.append(
            AcceptedInterface(
                name=iface.name,
                received_bytes=r_delta,
                sent_bytes=s_delta,
                accepted=True,
                reason=reason,
                from_reset=from_reset,
            )
        )

    # Update device bookkeeping (monotonic sequence acknowledgement).
    device.last_seen_at = now
    device.last_sequence = max(device.last_sequence or 0, report.sequence)
    if report.measurement_scope:
        device.measurement_scope = report.measurement_scope
    if report.measurement_quality:
        device.measurement_quality = report.measurement_quality
    await session.flush()

    # Evaluate thresholds after commit-worthy changes.
    if group is not None and period_id is not None:
        from .alerts import evaluate_thresholds

        await evaluate_thresholds(session, group, period_id)

    return UsageReportOut(
        accepted=True,
        duplicate=duplicate,
        server_time=now,
        acknowledged_sequence=device.last_sequence,
        received_bytes=total_received,
        sent_bytes=total_sent,
        interfaces=accepted_interfaces,
    )