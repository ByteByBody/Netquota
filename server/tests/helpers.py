"""Shared test helpers."""

from __future__ import annotations

from datetime import timedelta

import httpx

from app.timeutil import utcnow


def _default_observed() -> str:
    return (utcnow() - timedelta(seconds=5)).isoformat() + "Z"


async def create_group(
    client: httpx.AsyncClient,
    headers: dict,
    *,
    name: str = "Household",
    quota_bytes: int = 10 * 1024**3,
    reset_day: int = 1,
    device_ids: list[str] | None = None,
) -> dict:
    resp = await client.post(
        "/api/v1/groups",
        headers=headers,
        json={
            "name": name,
            "quota_bytes": quota_bytes,
            "reset_day": reset_day,
            "device_ids": device_ids or [],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def create_enrollment_code(
    client: httpx.AsyncClient, headers: dict, *, group_id: str | None = None
) -> str:
    resp = await client.post(
        "/api/v1/enrollment/codes",
        headers=headers,
        json={"label": "test", "group_id": group_id},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["code"]


async def enroll_device(
    client: httpx.AsyncClient,
    code: str,
    *,
    name: str = "sim-device",
    platform: str = "simulator",
    scope: str = "device_total",
    quality: str = "exact",
    agent_version: str = "0.1.0",
) -> dict:
    resp = await client.post(
        "/api/v1/enroll",
        json={
            "enrollment_code": code,
            "name": name,
            "platform": platform,
            "agent_version": agent_version,
            "measurement_scope": scope,
            "measurement_quality": quality,
            "capabilities": {"test": True},
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def agent_headers(device_id: str, credential: str) -> dict:
    return {"X-Device-Id": device_id, "X-Device-Credential": credential}


async def report_usage(
    client: httpx.AsyncClient,
    device_id: str,
    credential: str,
    *,
    sequence: int,
    received: int,
    sent: int,
    interfaces: list[dict] | None = None,
    observed_at: str | None = None,
    scope: str = "device_total",
    quality: str = "exact",
) -> dict:
    payload = {
        "schema_version": 1,
        "sequence": sequence,
        "observed_at": observed_at or _default_observed(),
        "measurement_scope": scope,
        "measurement_quality": quality,
        "interfaces": interfaces
        if interfaces is not None
        else [
            {
                "name": "eth0",
                "bytes_received_total": received,
                "bytes_sent_total": sent,
            }
        ],
    }
    resp = await client.post(
        "/api/v1/agent/usage",
        headers=agent_headers(device_id, credential),
        json=payload,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()