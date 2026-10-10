#!/usr/bin/env python3
"""End-to-end simulator against a running NetQuota server.

Enrolls a clearly-labelled synthetic device and reports cumulative samples.
Intended for validating the backend and dashboard before real devices exist.

Example:
    python simulate.py --server http://127.0.0.1:8000 --code <CODE> \
        --name "[SIM] Living Room PC" --samples 48
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone

from netquota_agent.reporter import ApiClient, ApiError
from netquota_agent.simulator import SIM_PREFIX, as_payload, generate_samples


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NetQuota synthetic usage simulator")
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--code", required=True, help="single-use enrollment code")
    parser.add_argument("--name", default=f"{SIM_PREFIX} Simulated Device")
    parser.add_argument("--platform", default="simulator")
    parser.add_argument("--samples", type=int, default=24)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--interval-seconds", type=int, default=300)
    parser.add_argument("--mb-per-interval", type=float, default=5.0)
    args = parser.parse_args(argv)

    if not args.name.startswith(SIM_PREFIX):
        args.name = f"{SIM_PREFIX} {args.name}"

    client = ApiClient(args.server)
    try:
        enrolled = client.enroll(
            enrollment_code=args.code,
            name=args.name,
            platform=args.platform,
            measurement_scope="device_total",
            measurement_quality="exact",
            capabilities={"simulated": True, "note": "synthetic data"},
            installation_id=str(uuid.uuid4()),
        )
    except ApiError as exc:
        print(f"enrollment failed: {exc}", file=sys.stderr)
        return 1

    device_id, credential = enrolled["device_id"], enrolled["credential"]
    authed = ApiClient(args.server, device_id=device_id, credential=credential)
    print(f"Enrolled {args.name} as {device_id}")

    samples = generate_samples(
        count=args.samples,
        seed=args.seed,
        start=datetime.now(timezone.utc),
        interval_seconds=args.interval_seconds,
        mean_bytes_per_interval=int(args.mb_per_interval * 1024 * 1024),
    )
    for i, (observed, interfaces) in enumerate(samples, start=1):
        payload = as_payload(i, observed, interfaces)
        try:
            result = authed.report_usage(payload)
        except ApiError as exc:
            print(f"sample {i} failed: {exc}", file=sys.stderr)
            continue
        print(
            f"  seq={i:>3} accepted={result['accepted']} "
            f"dup={result['duplicate']} "
            f"delta={result['received_bytes'] + result['sent_bytes']} bytes"
        )
    print("Simulation complete. This device reports SYNTHETIC data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())