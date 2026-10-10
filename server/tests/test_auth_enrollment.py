"""Enrollment and authentication tests."""

from __future__ import annotations

from .helpers import (
    agent_headers,
    create_enrollment_code,
    create_group,
    enroll_device,
    report_usage,
)


async def test_enrollment_code_single_use(client, auth_headers):
    group = await create_group(client, auth_headers)
    code = await create_enrollment_code(client, auth_headers, group_id=group["id"])

    await enroll_device(client, code, name="a")
    # Second use of the same code must fail.
    resp = await client.post(
        "/api/v1/enroll",
        json={
            "enrollment_code": code,
            "name": "b",
            "platform": "linux",
        },
    )
    assert resp.status_code == 409


async def test_invalid_enrollment_code(client, auth_headers):
    resp = await client.post(
        "/api/v1/enroll",
        json={"enrollment_code": "nope", "name": "x", "platform": "linux"},
    )
    assert resp.status_code == 401


async def test_login_wrong_password(client):
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong"}
    )
    assert resp.status_code == 401


async def test_protected_endpoint_requires_auth(client):
    resp = await client.get("/api/v1/devices")
    assert resp.status_code == 401


async def test_device_credential_required(client, auth_headers):
    group = await create_group(client, auth_headers)
    code = await create_enrollment_code(client, auth_headers, group_id=group["id"])
    device = await enroll_device(client, code)
    # Wrong credential rejected.
    resp = await client.post(
        "/api/v1/agent/heartbeat",
        headers=agent_headers(device["device_id"], "bogus"),
        json={"schema_version": 1},
    )
    assert resp.status_code == 401


async def test_revocation_invalidates_credential(client, auth_headers):
    group = await create_group(client, auth_headers)
    code = await create_enrollment_code(client, auth_headers, group_id=group["id"])
    device = await enroll_device(client, code)
    device_id, credential = device["device_id"], device["credential"]

    # Works before revocation.
    ok = await report_usage(
        client, device_id, credential, sequence=1, received=10, sent=10
    )
    assert ok["accepted"]

    resp = await client.post(
        f"/api/v1/devices/{device_id}/revoke", headers=auth_headers
    )
    assert resp.status_code == 200

    denied = await client.post(
        "/api/v1/agent/heartbeat",
        headers=agent_headers(device_id, credential),
        json={"schema_version": 1},
    )
    assert denied.status_code in (401, 403)


async def test_logout_revokes_session(client, auth_headers):
    assert (await client.get("/api/v1/auth/me", headers=auth_headers)).status_code == 200
    assert (
        await client.post("/api/v1/auth/logout", headers=auth_headers)
    ).status_code == 204
    assert (await client.get("/api/v1/auth/me", headers=auth_headers)).status_code == 401