"""Synthetic usage simulator.

Generates clearly-labelled deterministic synthetic samples so the backend and
dashboard can be validated before real devices exist. Devices enrolled by the
simulator use platform="simulator" and names prefixed with "[SIM]" so synthetic
data is always distinguishable from real measurements.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


SIM_PREFIX = "[SIM]"


@dataclass
class SimulatedInterface:
    name: str
    bytes_received_total: int
    bytes_sent_total: int


def generate_samples(
    *,
    count: int,
    seed: int = 1234,
    start: datetime | None = None,
    interval_seconds: int = 300,
    interfaces: tuple[str, ...] = ("eth0",),
    mean_bytes_per_interval: int = 5_000_000,
) -> list[tuple[datetime, list[SimulatedInterface]]]:
    """Return ``count`` cumulative observations.

    Deterministic for a fixed seed. Counters always increase (a well-behaved
    agent); use ``inject_reset`` to simulate a counter reset.
    """
    rng = random.Random(seed)
    start = start or datetime(2026, 10, 1, tzinfo=timezone.utc)
    totals = {name: [0, 0] for name in interfaces}
    samples: list[tuple[datetime, list[SimulatedInterface]]] = []
    for i in range(count):
        observed = start + timedelta(seconds=interval_seconds * i)
        for name in interfaces:
            recv = max(0, int(rng.gauss(mean_bytes_per_interval, mean_bytes_per_interval / 4)))
            sent = max(0, int(rng.gauss(mean_bytes_per_interval / 5, mean_bytes_per_interval / 20)))
            totals[name][0] += recv
            totals[name][1] += sent
        samples.append(
            (
                observed,
                [
                    SimulatedInterface(name, totals[name][0], totals[name][1])
                    for name in interfaces
                ],
            )
        )
    return samples


def as_payload(
    sequence: int, observed: datetime, interfaces: list[SimulatedInterface]
) -> dict:
    return {
        "schema_version": 1,
        "sequence": sequence,
        "observed_at": observed.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "measurement_scope": "device_total",
        "measurement_quality": "exact",
        "interfaces": [
            {
                "name": i.name,
                "bytes_received_total": i.bytes_received_total,
                "bytes_sent_total": i.bytes_sent_total,
            }
            for i in interfaces
        ],
    }