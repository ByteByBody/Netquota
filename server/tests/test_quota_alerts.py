"""Quota engine, threshold alerts, period transitions, stale detection."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Device
from app.timeutil import month_bounds, utcnow
from .helpers import (
    create_enrollment_code,
    create_group,
    enroll_device,
    report_usage,
)

MB = 1024**2


async def test_thresholds_emitted_and_deduplicated(client, auth_headers):
    # 100 MB quota so samples can cross 80/90/100%.
    group = await create_group(client, auth_headers, quota_bytes=100 * MB)
    code = await create_enrollment_code(client, auth_headers, group_id=group["id"])
    device = await enroll_device(client, code)

    await report_usage(client, device["device_id"], device["credential"], sequence=1, received=0, sent=0)
    # Cross 80% (85 MB cumulative).
    await report_usage(client, device["device_id"], device["credential"], sequence=2, received=85 * MB, sent=0)
    # Cross 90% (91 MB), then 100% (101 MB).
    await report_usage(client, device["device_id"], device["credential"], sequence=3, received=91 * MB, sent=0)
    await report_usage(client, device["device_id"], device["credential"], sequence=4, received=101 * MB, sent=0)

    events = (
        await client.get("/api/v1/events", headers=auth_headers)
    ).json()
    threshold_events = [
        e for e in events if e["event_type"].startswith("threshold_")
    ]
    types = sorted(e["event_type"] for e in threshold_events)
    assert types == ["threshold_100", "threshold_80", "threshold_90"]

    # A repeated sample in the same period must not duplicate threshold events.
    await report_usage(client, device["device_id"], device["credential"], sequence=5, received=102 * MB, sent=0)
    events2 = (
        await client.get("/api/v1/events", headers=auth_headers)
    ).json()
    threshold2 = [e for e in events2 if e["event_type"].startswith("threshold_")]
    assert len(threshold2) == 3


async def test_monthly_period_transition(client, auth_headers):
    group = await create_group(client, auth_headers, quota_bytes=1_000_000, reset_day=1)
    code = await create_enrollment_code(client, auth_headers, group_id=group["id"])
    device = await enroll_device(client, code)
    await report_usage(
        client,
        device["device_id"],
        device["credential"],
        sequence=1,
        received=0,
        sent=0,
        observed_at="2026-09-15T00:00:00Z",
    )
    await report_usage(
        client,
        device["device_id"],
        device["credential"],
        sequence=2,
        received=500,
        sent=0,
        observed_at="2026-09-20T00:00:00Z",
    )
    # Next month: new period, usage resets.
    await report_usage(
        client,
        device["device_id"],
        device["credential"],
        sequence=3,
        received=900,
        sent=0,
        observed_at="2026-10-02T00:00:00Z",
    )
    summary = (
        await client.get("/api/v1/dashboard/summary", headers=auth_headers)
    ).json()
    # Current period is October; only the +400 from sequence 3 belongs to it.
    assert summary["groups"][0]["used_bytes"] == 400


def test_month_bounds():
    start, end = month_bounds(datetime(2026, 10, 10), reset_day=1)
    assert start == datetime(2026, 10, 1)
    assert end == datetime(2026, 11, 1)

    start, end = month_bounds(datetime(2026, 10, 10), reset_day=15)
    assert start == datetime(2026, 9, 15)
    assert end == datetime(2026, 10, 15)

    start, end = month_bounds(datetime(2026, 10, 5), reset_day=15)
    assert start == datetime(2026, 9, 15)
    assert end == datetime(2026, 10, 15)


async def test_stale_agent_detection(client, auth_headers):
    group = await create_group(client, auth_headers)
    code = await create_enrollment_code(client, auth_headers, group_id=group["id"])
    device = await enroll_device(client, code)

    # Force last_seen into the past.
    async with SessionLocal() as session:
        d = (await session.scalars(select(Device))).one()
        d.last_seen_at = utcnow() - timedelta(hours=2)
        await session.commit()

    summary = (
        await client.get("/api/v1/dashboard/summary", headers=auth_headers)
    ).json()
    assert summary["stale_device_count"] == 1
    assert summary["stale_devices"][0]["id"] == device["device_id"]

    events = (await client.get("/api/v1/events?event_type=stale_agent", headers=auth_headers)).json()
    assert len(events) >= 1

    # Calling again must not duplicate the stale event for the same episode.
    await client.get("/api/v1/dashboard/summary", headers=auth_headers)
    events2 = (await client.get("/api/v1/events?event_type=stale_agent", headers=auth_headers)).json()
    assert len(events2) == len(events)