"""Phase 3: the synthetic simulator drives the real accounting engine."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the desktop agent package importable for the simulator.
AGENT_ROOT = Path(__file__).resolve().parents[2] / "agents" / "desktop"
sys.path.insert(0, str(AGENT_ROOT))

from netquota_agent.simulator import as_payload, generate_samples  # noqa: E402

from .helpers import (  # noqa: E402
    agent_headers,
    create_enrollment_code,
    create_group,
    enroll_device,
)

GB = 1024**3


async def test_simulator_end_to_end(client, auth_headers):
    group = await create_group(client, auth_headers, quota_bytes=1 * GB)
    code = await create_enrollment_code(client, auth_headers, group_id=group["id"])
    device = await enroll_device(
        client, code, name="[SIM] Test", platform="simulator"
    )
    headers = agent_headers(device["device_id"], device["credential"])

    samples = generate_samples(count=10, seed=99, mean_bytes_per_interval=1_000_000)
    expected_total = 0
    for i, (observed, interfaces) in enumerate(samples, start=1):
        payload = as_payload(i, observed, interfaces)
        resp = await client.post("/api/v1/agent/usage", headers=headers, json=payload)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        if i == 1:
            assert body["received_bytes"] == 0  # baseline
        else:
            expected_total += body["received_bytes"] + body["sent_bytes"]

    # Replay several samples: must not change totals.
    for i in (5, 7, 10, 10):
        _, interfaces = samples[i - 1]
        payload = as_payload(i, samples[i - 1][0], interfaces)
        resp = await client.post("/api/v1/agent/usage", headers=headers, json=payload)
        assert resp.json()["duplicate"] is True

    summary = (
        await client.get("/api/v1/dashboard/summary", headers=auth_headers)
    ).json()
    assert summary["groups"][0]["used_bytes"] == expected_total


async def test_simulator_crosses_threshold(client, auth_headers):
    # 1 MB quota, samples of ~1 MB each cross 80/90/100% quickly.
    group = await create_group(client, auth_headers, quota_bytes=1_000_000)
    code = await create_enrollment_code(client, auth_headers, group_id=group["id"])
    device = await enroll_device(client, code, name="[SIM] Threshold")
    headers = agent_headers(device["device_id"], device["credential"])

    samples = generate_samples(count=6, seed=7, mean_bytes_per_interval=400_000)
    for i, (observed, interfaces) in enumerate(samples, start=1):
        await client.post(
            "/api/v1/agent/usage",
            headers=headers,
            json=as_payload(i, observed, interfaces),
        )

    events = (await client.get("/api/v1/events", headers=auth_headers)).json()
    types = {e["event_type"] for e in events}
    assert {"threshold_80", "threshold_90", "threshold_100"} <= types