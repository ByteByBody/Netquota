"""Phase 1 vertical slice.

One group (10 GB quota), one simulated device, two cumulative samples, correct
delta, correct group usage/remaining, idempotent repeat, working summary API.
"""

from __future__ import annotations

from .helpers import (
    create_enrollment_code,
    create_group,
    enroll_device,
    report_usage,
)

GB = 1024**3


async def test_vertical_slice(client, auth_headers):
    # 1. Group with a 10 GB monthly quota.
    group = await create_group(client, auth_headers, name="Home", quota_bytes=10 * GB)

    # 2. Enroll one simulated device into it.
    code = await create_enrollment_code(client, auth_headers, group_id=group["id"])
    device = await enroll_device(client, code, name="sim-1")
    device_id = device["device_id"]
    credential = device["credential"]

    # 3. Two cumulative samples.
    first = await report_usage(
        client, device_id, credential, sequence=1, received=1_000_000, sent=200_000
    )
    assert first["accepted"] is True
    # Baseline sample yields no delta.
    assert first["received_bytes"] == 0 and first["sent_bytes"] == 0

    second = await report_usage(
        client, device_id, credential, sequence=2, received=1_500_000, sent=250_000
    )
    assert second["accepted"] is True
    # 4. Correct difference.
    assert second["received_bytes"] == 500_000
    assert second["sent_bytes"] == 50_000

    # Idempotent repeat of sample 2 must not double-count.
    repeat = await report_usage(
        client, device_id, credential, sequence=2, received=1_500_000, sent=250_000
    )
    assert repeat["duplicate"] is True
    assert repeat["received_bytes"] == 0 and repeat["sent_bytes"] == 0

    # 5/6. Group usage and remaining quota via the summary endpoint.
    resp = await client.get("/api/v1/dashboard/summary", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    summary = resp.json()
    assert summary["device_count"] == 1
    group_summary = summary["groups"][0]
    assert group_summary["used_bytes"] == 550_000
    assert group_summary["quota_bytes"] == 10 * GB
    assert group_summary["remaining_bytes"] == 10 * GB - 550_000
    assert group_summary["percentage_used"] > 0