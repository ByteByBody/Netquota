"""Seed a NetQuota server with clearly-labelled demo data.

Creates a group with a quota, an enrollment code, and enrolls a simulated
device that reports synthetic cumulative samples. Everything created here is
labelled synthetic (platform="simulator", device name prefixed "[SIM]").

Usage:
    python scripts/seed_demo.py --server http://127.0.0.1:8000 \
        --admin admin --password changeme
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agents" / "desktop"))

import httpx  # noqa: E402
from netquota_agent.simulator import SIM_PREFIX, as_payload, generate_samples  # noqa: E402

GB = 1024**3


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--admin", default="admin")
    parser.add_argument("--password", default="changeme")
    args = parser.parse_args()

    with httpx.Client(base_url=args.server, timeout=30) as c:
        token = c.post(
            "/api/v1/auth/login",
            json={"username": args.admin, "password": args.password},
        ).json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        # Group with a 10 GiB quota.
        group = c.post(
            "/api/v1/groups",
            headers=h,
            json={"name": "Household", "quota_bytes": 10 * GB, "reset_day": 1},
        ).json()
        print(f"group: {group['name']} ({group['id']})")

        # Two simulated devices.
        for label, seed, mb in (("Living Room PC", 11, 40), ("Kids' Tablet", 22, 90)):
            code = c.post(
                "/api/v1/enrollment/codes",
                headers=h,
                json={"label": label, "group_id": group["id"]},
            ).json()["code"]
            enrolled = c.post(
                "/api/v1/enroll",
                json={
                    "enrollment_code": code,
                    "name": f"{SIM_PREFIX} {label}",
                    "platform": "simulator",
                    "agent_version": "0.1.0",
                    "measurement_scope": "device_total",
                    "measurement_quality": "exact",
                    "capabilities": {"simulated": True},
                    "installation_id": str(uuid.uuid4()),
                },
            ).json()
            did, cred = enrolled["device_id"], enrolled["credential"]
            ah = {"X-Device-Id": did, "X-Device-Credential": cred}
            samples = generate_samples(
                count=20,
                seed=seed,
                start=datetime.now(timezone.utc),
                mean_bytes_per_interval=mb * 1024 * 1024,
            )
            total = 0
            for i, (observed, interfaces) in enumerate(samples, start=1):
                body = c.post(
                    "/api/v1/agent/usage",
                    headers=ah,
                    json=as_payload(i, observed, interfaces),
                ).json()
                total += body["received_bytes"] + body["sent_bytes"]
            print(f"device: {label} -> {total / GB:.2f} GiB synthetic")

        summary = c.get("/api/v1/dashboard/summary", headers=h).json()
        print(
            f"summary: {summary['device_count']} devices, "
            f"{summary['groups'][0]['percentage_used']:.1f}% quota used"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())