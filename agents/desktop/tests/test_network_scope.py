"""Unit tests for network-scoped counting (gateway-MAC rule).

These are pure-logic tests: no subprocess, no real interfaces. Platform parsing
of ARP/route output and the accumulator are exercised with fixture text.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from netquota_agent.network_scope import (  # noqa: E402
    NetworkScope,
    build_scoped_result,
    collect_for_report,
    normalize_mac,
    parse_arp_table,
    parse_default_gateway_linux,
)


# --- MAC normalization -----------------------------------------------------


def test_normalize_mac_windows_dash_form():
    assert normalize_mac("AA-BB-CC-DD-EE-FF") == "aa:bb:cc:dd:ee:ff"


def test_normalize_mac_colon_form():
    assert normalize_mac("aa:bb:cc:dd:ee:ff") == "aa:bb:cc:dd:ee:ff"


def test_normalize_mac_cisco_dotted_form():
    assert normalize_mac("0011.2233.4455") == "00:11:22:33:44:55"


def test_normalize_mac_invalid_returns_none():
    assert normalize_mac("not-a-mac") is None
    assert normalize_mac("") is None
    assert normalize_mac(None) is None


# --- ARP table parsing -----------------------------------------------------


def test_parse_arp_table_windows_format():
    text = (
        "Interface: 192.168.1.10 --- 0x5\n"
        "  Internet Address      Physical Address      Type\n"
        "  192.168.1.1           aa-bb-cc-dd-ee-ff     dynamic\n"
        "  192.168.1.255         ff-ff-ff-ff-ff-ff     static\n"
    )
    table = parse_arp_table(text)
    assert table["192.168.1.1"] == "aa:bb:cc:dd:ee:ff"
    assert table["192.168.1.255"] == "ff:ff:ff:ff:ff:ff"


def test_parse_arp_table_ip_neigh_format():
    text = (
        "192.168.1.1 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE\n"
        "192.168.1.50 dev eth0 lladdr 11:22:33:44:55:66 STALE\n"
    )
    table = parse_arp_table(text)
    assert table["192.168.1.1"] == "aa:bb:cc:dd:ee:ff"
    assert table["192.168.1.50"] == "11:22:33:44:55:66"


# --- Linux default gateway parsing -----------------------------------------


def test_parse_default_gateway_linux_little_endian():
    text = (
        "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n"
        "eth0\t00000000\t0101A8C0\t0003\t0\t0\t0\t00000000\t0\t0\t0\n"
        "eth0\t0001A8C0\t00000000\t0001\t0\t0\t0\t00FFFFFF\t0\t0\t0\n"
    )
    assert parse_default_gateway_linux(text) == "192.168.1.1"


def test_parse_default_gateway_linux_requires_gateway_flag():
    text = (
        "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n"
        "eth0\t00000000\t0101A8C0\t0001\t0\t0\t0\t00000000\t0\t0\t0\n"
    )
    assert parse_default_gateway_linux(text) is None


# --- accumulator: count only matched intervals -----------------------------


def _raw(**interfaces):
    return {name: [recv, sent] for name, (recv, sent) in interfaces.items()}


def test_scope_counts_interval_only_when_previous_sample_matched():
    scope = NetworkScope({"aa:bb:cc:dd:ee:ff"})
    # Already home on the previous sample; this interval counts.
    scope.set_initial_match(True)
    scope.observe(_raw(eth0=(1000, 100)), current_mac="aa:bb:cc:dd:ee:ff")
    assert scope.totals["eth0"] == [1000, 100]


def test_scope_skips_first_interval_after_joining():
    scope = NetworkScope({"aa:bb:cc:dd:ee:ff"})
    scope.set_initial_match(False)
    # First observation as a home device must not count pre-join bytes.
    scope.observe(_raw(eth0=(5000, 500)), current_mac="aa:bb:cc:dd:ee:ff")
    assert scope.totals.get("eth0", [0, 0]) == [0, 0]
    # Next interval is fully on-network and counts.
    scope.observe(_raw(eth0=(5600, 540)), current_mac="aa:bb:cc:dd:ee:ff")
    assert scope.totals["eth0"] == [600, 40]


def test_scope_counts_last_interval_when_leaving():
    scope = NetworkScope({"aa:bb:cc:dd:ee:ff"})
    scope.set_initial_match(True)
    scope.observe(_raw(eth0=(1000, 100)), current_mac="aa:bb:cc:dd:ee:ff")
    # Now off-network: previous interval was home, so it still counts.
    scope.observe(_raw(eth0=(1500, 150)), current_mac="11:22:33:44:55:66")
    assert scope.totals["eth0"] == [1500, 150]
    # Still off-network: nothing new counted.
    scope.observe(_raw(eth0=(9000, 900)), current_mac="11:22:33:44:55:66")
    assert scope.totals["eth0"] == [1500, 150]


def test_scope_does_not_count_off_network_bytes():
    scope = NetworkScope({"aa:bb:cc:dd:ee:ff"})
    scope.set_initial_match(False)
    scope.observe(_raw(eth0=(100, 10)), current_mac=None)
    scope.observe(_raw(eth0=(999999, 99999)), current_mac="11:22:33:44:55:66")
    assert scope.totals.get("eth0", [0, 0]) == [0, 0]


def test_scope_counter_reset_yields_no_negative_delta():
    scope = NetworkScope({"aa:bb:cc:dd:ee:ff"})
    scope.set_initial_match(True)
    scope.observe(_raw(eth0=(10000, 1000)), current_mac="aa:bb:cc:dd:ee:ff")
    # Adapter reset: OS counters drop. Delta must clamp to zero, not go negative.
    scope.observe(_raw(eth0=(5, 1)), current_mac="aa:bb:cc:dd:ee:ff")
    assert scope.totals["eth0"] == [10000, 1000]
    scope.observe(_raw(eth0=(105, 21)), current_mac="aa:bb:cc:dd:ee:ff")
    assert scope.totals["eth0"] == [10100, 1020]


def test_scope_matches_any_configured_gateway_mac():
    scope = NetworkScope({"aa:bb:cc:dd:ee:ff", "11:22:33:44:55:66"})
    scope.set_initial_match(True)
    scope.observe(_raw(eth0=(100, 10)), current_mac="11:22:33:44:55:66")
    assert scope.totals["eth0"] == [100, 10]


def test_scope_unconfigured_mac_never_matches():
    scope = NetworkScope(set())
    scope.set_initial_match(False)
    scope.observe(_raw(eth0=(100, 10)), current_mac="aa:bb:cc:dd:ee:ff")
    assert scope.totals.get("eth0", [0, 0]) == [0, 0]


# --- persistence roundtrip -------------------------------------------------


def test_scope_state_roundtrip_preserves_accumulated():
    scope = NetworkScope({"aa:bb:cc:dd:ee:ff"})
    scope.set_initial_match(True)
    scope.observe(_raw(eth0=(1000, 100), wlan0=(50, 5)), current_mac="aa:bb:cc:dd:ee:ff")

    data = scope.to_state()
    restored = NetworkScope.from_state({"aa:bb:cc:dd:ee:ff"}, data)
    assert restored.totals["eth0"] == [1000, 100]
    assert restored.totals["wlan0"] == [50, 5]

    # Continuing after restore keeps accumulating from the preserved totals.
    restored.observe(_raw(eth0=(1200, 140), wlan0=(70, 9)), current_mac="aa:bb:cc:dd:ee:ff")
    assert restored.totals["eth0"] == [1200, 140]
    assert restored.totals["wlan0"] == [70, 9]


# --- result shaping for the reporter ---------------------------------------


def test_build_scoped_result_marks_estimated_and_notes_scope():
    scope = NetworkScope({"aa:bb:cc:dd:ee:ff"})
    scope.set_initial_match(True)
    scope.observe(_raw(eth0=(1000, 100)), current_mac="aa:bb:cc:dd:ee:ff")

    result = build_scoped_result(scope, interval_seconds=30)
    assert result.measurement_scope == "device_total"
    assert result.measurement_quality == "estimated"
    assert [i.name for i in result.interfaces] == ["eth0"]
    assert result.interfaces[0].bytes_received_total == 1000
    assert result.interfaces[0].bytes_sent_total == 100
    assert any("home network" in note.lower() for note in result.notes)


def test_build_scoped_result_empty_when_never_on_network():
    scope = NetworkScope({"aa:bb:cc:dd:ee:ff"})
    scope.set_initial_match(False)
    scope.observe(_raw(eth0=(1000, 100)), current_mac=None)

    result = build_scoped_result(scope, interval_seconds=30)
    assert result.interfaces == []
    assert result.measurement_quality == "estimated"


# --- config and state integration -----------------------------------------


def test_agent_config_scoped_defaults():
    from netquota_agent.config import AgentConfig

    config = AgentConfig()
    assert config.count_scope == "device"
    assert config.gateway_macs == []
    assert config.sample_seconds >= 15


def test_state_persists_network_scope(tmp_path):
    from netquota_agent.state import AgentState

    scope = NetworkScope({"aa:bb:cc:dd:ee:ff"})
    scope.set_initial_match(True)
    scope.observe(_raw(eth0=(1000, 100)), current_mac="aa:bb:cc:dd:ee:ff")

    path = tmp_path / "state.json"
    state = AgentState(device_id="abc", sequence=3)
    state.network_scope = scope.to_state()
    state.save(path)

    loaded = AgentState.load(path)
    assert loaded.network_scope["totals"]["eth0"] == [1000, 100]


# --- report-time gluing (pure) ---------------------------------------------


def test_collect_for_report_device_scope_passthrough():
    from netquota_agent.collector import CollectionResult, InterfaceCounters
    from netquota_agent.config import AgentConfig

    collected = CollectionResult(
        interfaces=[InterfaceCounters("eth0", 500, 50)],
        measurement_scope="device_total",
        measurement_quality="exact",
    )
    result, scope_state = collect_for_report(
        config=AgentConfig(count_scope="device"),
        collected=collected,
        prev_scope_state={},
        current_mac="aa:bb:cc:dd:ee:ff",
    )
    assert result is collected
    assert scope_state == {}


def test_collect_for_report_home_scope_uses_accumulator():
    from netquota_agent.collector import CollectionResult, InterfaceCounters
    from netquota_agent.config import AgentConfig

    config = AgentConfig(
        count_scope="home_network",
        gateway_macs=["aa:bb:cc:dd:ee:ff"],
        sample_seconds=30,
    )
    collected = CollectionResult(
        interfaces=[InterfaceCounters("eth0", 1000, 100)],
        measurement_scope="device_total",
        measurement_quality="exact",
    )
    # First observation seeds baseline only (prev not matched).
    result, scope_state = collect_for_report(
        config=config,
        collected=collected,
        prev_scope_state={},
        current_mac="aa:bb:cc:dd:ee:ff",
    )
    assert result.measurement_quality == "estimated"
    assert result.interfaces == []
    # Second observation on-network counts the delta.
    collected2 = CollectionResult(
        interfaces=[InterfaceCounters("eth0", 1300, 140)],
        measurement_scope="device_total",
        measurement_quality="exact",
    )
    result2, scope_state2 = collect_for_report(
        config=config,
        collected=collected2,
        prev_scope_state=scope_state,
        current_mac="aa:bb:cc:dd:ee:ff",
    )
    assert result2.interfaces[0].bytes_received_total == 300
    assert result2.interfaces[0].bytes_sent_total == 40
    assert scope_state2["totals"]["eth0"] == [300, 40]