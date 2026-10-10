"""Unit tests for the shared desktop agent (no network required)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from netquota_agent.collector import is_virtual, select_interfaces  # noqa: E402
from netquota_agent.simulator import as_payload, generate_samples  # noqa: E402
from netquota_agent.state import AgentState  # noqa: E402


def test_primary_policy_excludes_virtual_and_loopback():
    counters = {
        "eth0": 1,
        "wlan0": 2,
        "lo": 3,
        "docker0": 4,
        "br-abc": 5,
        "tun0": 6,
        "vEthernet (Default Switch)": 7,
        "Ethernet": 8,
        "Wi-Fi": 9,
    }
    selected = select_interfaces(counters, policy="primary")
    assert set(selected) == {"eth0", "wlan0", "Ethernet", "Wi-Fi"}


def test_all_policy_counts_everything_but_loopback():
    counters = {"eth0": 1, "docker0": 2, "lo": 3}
    assert set(select_interfaces(counters, policy="all")) == {"eth0", "docker0"}


def test_include_and_exclude_overrides():
    counters = {"eth0": 1, "wlan0": 2, "docker0": 3}
    selected = select_interfaces(
        counters, policy="primary", include=["docker0"], exclude=["wlan0"]
    )
    assert set(selected) == {"eth0", "docker0"}


def test_is_virtual():
    assert is_virtual("tun0")
    assert is_virtual("vEthernet (Default Switch)")
    assert not is_virtual("eth0")
    assert not is_virtual("Wi-Fi")


def test_simulator_deterministic_and_monotonic():
    a = generate_samples(count=5, seed=42)
    b = generate_samples(count=5, seed=42)
    assert [s[1][0].bytes_received_total for s in a] == [
        s[1][0].bytes_received_total for s in b
    ]
    totals = [s[1][0].bytes_received_total for s in a]
    assert totals == sorted(totals)  # cumulative, never decreasing


def test_simulator_payload_shape():
    samples = generate_samples(count=1, seed=1)
    observed, interfaces = samples[0]
    payload = as_payload(1, observed, interfaces)
    assert payload["schema_version"] == 1
    assert payload["sequence"] == 1
    assert payload["interfaces"][0]["name"] == "eth0"


def test_state_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    state = AgentState(device_id="abc", sequence=7)
    state.save(path)
    loaded = AgentState.load(path)
    assert loaded.device_id == "abc"
    assert loaded.sequence == 7
    assert loaded.next_sequence() == 8