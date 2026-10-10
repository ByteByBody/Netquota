"""Input validation and API error handling."""

from __future__ import annotations

from .helpers import (
    agent_headers,
    create_enrollment_code,
    create_group,
    enroll_device,
)


async def test_duplicate_group_name_rejected(client, auth_headers):
    await create_group(client, auth_headers, name="Dup")
    resp = await client.post(
        "/api/v1/groups", headers=auth_headers, json={"name": "Dup"}
    )
    assert resp.status_code == 409


async def test_invalid_platform_rejected(client, auth_headers):
    group = await create_group(client, auth_headers)
    code = await create_enrollment_code(client, auth_headers, group_id=group["id"])
    resp = await client.post(
        "/api/v1/enroll",
        json={"enrollment_code": code, "name": "x", "platform": "beos"},
    )
    assert resp.status_code == 422


async def test_negative_counters_rejected(client, auth_headers):
    group = await create_group(client, auth_headers)
    code = await create_enrollment_code(client, auth_headers, group_id=group["id"])
    device = await enroll_device(client, code)
    resp = await client.post(
        "/api/v1/agent/usage",
        headers=agent_headers(device["device_id"], device["credential"]),
        json={
            "schema_version": 1,
            "sequence": 1,
            "observed_at": "2026-10-10T08:45:00Z",
            "interfaces": [
                {"name": "eth0", "bytes_received_total": -1, "bytes_sent_total": 0}
            ],
        },
    )
    assert resp.status_code == 422


async def test_duplicate_interface_names_rejected(client, auth_headers):
    group = await create_group(client, auth_headers)
    code = await create_enrollment_code(client, auth_headers, group_id=group["id"])
    device = await enroll_device(client, code)
    resp = await client.post(
        "/api/v1/agent/usage",
        headers=agent_headers(device["device_id"], device["credential"]),
        json={
            "schema_version": 1,
            "sequence": 1,
            "observed_at": "2026-10-10T08:45:00Z",
            "interfaces": [
                {"name": "eth0", "bytes_received_total": 1, "bytes_sent_total": 0},
                {"name": "eth0", "bytes_received_total": 2, "bytes_sent_total": 0},
            ],
        },
    )
    assert resp.status_code == 422


async def test_unknown_device_404(client, auth_headers):
    resp = await client.get("/api/v1/devices/does-not-exist", headers=auth_headers)
    assert resp.status_code == 404


async def test_extra_fields_rejected(client, auth_headers):
    group = await create_group(client, auth_headers)
    code = await create_enrollment_code(client, auth_headers, group_id=group["id"])
    device = await enroll_device(client, code)
    resp = await client.post(
        "/api/v1/agent/usage",
        headers=agent_headers(device["device_id"], device["credential"]),
        json={
            "schema_version": 1,
            "sequence": 1,
            "observed_at": "2026-10-10T08:45:00Z",
            "surprise": True,
            "interfaces": [],
        },
    )
    assert resp.status_code == 422


async def test_group_quota_update_affects_active_period(client, auth_headers):
    group = await create_group(client, auth_headers, quota_bytes=1000)
    resp = await client.patch(
        f"/api/v1/groups/{group['id']}",
        headers=auth_headers,
        json={"quota_bytes": 5_000_000, "reset_day": 10},
    )
    assert resp.status_code == 200
    detail = (
        await client.get(f"/api/v1/groups/{group['id']}/usage", headers=auth_headers)
    ).json()
    assert detail["summary"]["quota_bytes"] == 5_000_000