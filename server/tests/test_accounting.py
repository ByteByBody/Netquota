"""Accounting engine edge cases: duplicates, resets, interface changes,
out-of-order samples, group reassignment and historical attribution."""

from __future__ import annotations

from .helpers import (
    create_enrollment_code,
    create_group,
    enroll_device,
    report_usage,
)


async def _setup(client, auth_headers, *, quota=10 * 1024**3):
    group = await create_group(client, auth_headers, quota_bytes=quota)
    code = await create_enrollment_code(client, auth_headers, group_id=group["id"])
    device = await enroll_device(client, code)
    return group, device["device_id"], device["credential"]


async def test_duplicate_samples_never_double_count(client, auth_headers):
    _, did, cred = await _setup(client, auth_headers)
    await report_usage(client, did, cred, sequence=1, received=100, sent=100)
    await report_usage(client, did, cred, sequence=2, received=300, sent=300)
    for _ in range(3):
        dup = await report_usage(
            client, did, cred, sequence=2, received=300, sent=300
        )
        assert dup["duplicate"] is True

    summary = (
        await client.get("/api/v1/dashboard/summary", headers=auth_headers)
    ).json()
    # Only the 200+200 delta from sample 2 counts.
    assert summary["groups"][0]["used_bytes"] == 400


async def test_counter_reset_does_not_lose_subsequent_traffic(client, auth_headers):
    _, did, cred = await _setup(client, auth_headers)
    await report_usage(client, did, cred, sequence=1, received=1_000_000, sent=0)
    # Counter resets to a low value; delta should equal the new totals.
    reset = await report_usage(client, did, cred, sequence=2, received=500, sent=0)
    assert reset["interfaces"][0]["from_reset"] is True
    assert reset["received_bytes"] == 500
    # And normal differences resume afterwards.
    normal = await report_usage(client, did, cred, sequence=3, received=1500, sent=0)
    assert normal["received_bytes"] == 1000


async def test_agent_signalled_reset(client, auth_headers):
    _, did, cred = await _setup(client, auth_headers)
    await report_usage(client, did, cred, sequence=1, received=10_000, sent=0)
    r = await report_usage(
        client,
        did,
        cred,
        sequence=2,
        received=200,
        sent=0,
        interfaces=[
            {"name": "eth0", "bytes_received_total": 200, "bytes_sent_total": 0, "reset": True}
        ],
    )
    assert r["received_bytes"] == 200
    assert r["interfaces"][0]["reason"] == "agent_reset"


async def test_virtual_interfaces_not_counted(client, auth_headers):
    _, did, cred = await _setup(client, auth_headers)
    await report_usage(
        client,
        did,
        cred,
        sequence=1,
        received=0,
        sent=0,
        interfaces=[
            {"name": "eth0", "bytes_received_total": 0, "bytes_sent_total": 0},
            {"name": "docker0", "bytes_received_total": 0, "bytes_sent_total": 0},
            {"name": "tun0", "bytes_received_total": 0, "bytes_sent_total": 0},
        ],
    )
    r = await report_usage(
        client,
        did,
        cred,
        sequence=2,
        received=0,
        sent=0,
        interfaces=[
            {"name": "eth0", "bytes_received_total": 1000, "bytes_sent_total": 100},
            {"name": "docker0", "bytes_received_total": 5000, "bytes_sent_total": 5000},
            {"name": "tun0", "bytes_received_total": 9000, "bytes_sent_total": 9000},
        ],
    )
    # Only eth0 counts: 1100, not 20_100.
    assert r["received_bytes"] == 1000
    assert r["sent_bytes"] == 100


async def test_new_interface_after_baseline_not_counted(client, auth_headers):
    _, did, cred = await _setup(client, auth_headers)
    await report_usage(client, did, cred, sequence=1, received=1000, sent=0)
    # A new interface appears with an already-large counter: baseline only.
    r = await report_usage(
        client,
        did,
        cred,
        sequence=2,
        received=0,
        sent=0,
        interfaces=[
            {"name": "eth0", "bytes_received_total": 2000, "bytes_sent_total": 0},
            {"name": "wlan0", "bytes_received_total": 9_000_000, "bytes_sent_total": 0},
        ],
    )
    assert r["received_bytes"] == 1000  # only eth0 delta
    assert r["sent_bytes"] == 0


async def test_out_of_order_and_future_rejected(client, auth_headers):
    _, did, cred = await _setup(client, auth_headers)
    await report_usage(client, did, cred, sequence=5, received=100, sent=0)
    # Future timestamp rejected.
    fut = await report_usage(
        client,
        did,
        cred,
        sequence=6,
        received=200,
        sent=0,
        observed_at="2999-01-01T00:00:00Z",
    )
    assert fut["accepted"] is False
    # In-order continue works.
    ok = await report_usage(client, did, cred, sequence=7, received=400, sent=0)
    assert ok["accepted"] and ok["received_bytes"] == 300


async def test_group_reassignment_preserves_history(client, auth_headers):
    g1, did, cred = await _setup(client, auth_headers)
    await report_usage(client, did, cred, sequence=1, received=1000, sent=0)
    await report_usage(client, did, cred, sequence=2, received=2000, sent=0)  # +1000 in g1

    g2 = await create_group(client, auth_headers, name="Guests", quota_bytes=5 * 1024**3)
    resp = await client.patch(
        f"/api/v1/devices/{did}",
        headers=auth_headers,
        json={"group_id": g2["id"]},
    )
    assert resp.status_code == 200

    await report_usage(client, did, cred, sequence=3, received=3000, sent=0)  # +1000 in g2

    summary = (
        await client.get("/api/v1/dashboard/summary", headers=auth_headers)
    ).json()
    by_name = {g["group_name"]: g for g in summary["groups"]}
    assert by_name["Household"]["used_bytes"] == 1000
    assert by_name["Guests"]["used_bytes"] == 1000


async def test_measurement_scope_surfaces_warning(client, auth_headers):
    group = await create_group(client, auth_headers)
    code = await create_enrollment_code(client, auth_headers, group_id=group["id"])
    device = await enroll_device(
        client, code, platform="ios", scope="app_only", quality="partial"
    )
    summary = (
        await client.get("/api/v1/dashboard/summary", headers=auth_headers)
    ).json()
    assert summary["groups"][0]["has_missing_measurements"] is True
    assert summary["measurement_warnings"]