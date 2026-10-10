"""Network-scoped usage counting.

NetQuota normally reports everything a device's interfaces have transferred.
Some households instead want to count only the portion that happened while a
device was on *their* network (e.g. exclude a laptop's hotel-Wi-Fi usage).

You cannot simply report the OS's raw counter only while on-network: the delta
between two on-network samples would silently include the off-network bytes in
between. So this module keeps its own **accumulated** counter per interface,
advanced only across intervals whose *previous* sample was on-network, and
reports that accumulated value instead of the raw OS counter.

The server needs no changes: it still receives an ordinary monotonic counter and
applies its existing delta/reset/idempotency logic.

On-network is decided by matching the current default-gateway MAC against a
configured allow-list of MAC addresses.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field

from .collector import CollectionResult, InterfaceCounters


# --- MAC helpers -----------------------------------------------------------

_MAC_CLEAN = re.compile(r"[^0-9a-f]")
_MAC_PATTERN = re.compile(
    r"(?:[0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}|[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}"
)
_IPV4_PATTERN = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")


def normalize_mac(value: str | None) -> str | None:
    """Return a lower-case, colon-separated MAC, or None if not a MAC.

    Accepts Windows dash form (aa-bb-...), colon form, and Cisco dotted form
    (0011.2233.4455).
    """
    if not value:
        return None
    cleaned = _MAC_CLEAN.sub("", value.lower())
    if len(cleaned) != 12 or not all(c in "0123456789abcdef" for c in cleaned):
        return None
    return ":".join(cleaned[i : i + 2] for i in range(0, 12, 2))


def _hex_to_ipv4_little_endian(value: str) -> str | None:
    try:
        raw = int(value, 16).to_bytes(4, "little")
    except (ValueError, OverflowError):
        return None
    return ".".join(str(b) for b in raw)


# --- table parsers ---------------------------------------------------------


def parse_arp_table(text: str) -> dict[str, str]:
    """Parse `arp -a` (Windows/POSIX) or `ip neigh` output into {ip: mac}."""
    table: dict[str, str] = {}
    for line in text.splitlines():
        ip_match = _IPV4_PATTERN.search(line)
        mac_match = _MAC_PATTERN.search(line)
        if not ip_match or not mac_match:
            continue
        mac = normalize_mac(mac_match.group(0))
        if mac:
            table[ip_match.group(1)] = mac
    return table


def parse_default_gateway_linux(text: str) -> str | None:
    """Parse /proc/net/route for the default gateway IPv4 address.

    The kernel stores addresses little-endian in hex. The default route has
    destination 00000000 and the RTF_GATEWAY (0x2) flag set.
    """
    for line in text.splitlines()[1:]:  # skip header
        parts = line.split()
        if len(parts) < 4:
            continue
        _iface, destination, gateway, flags = parts[0], parts[1], parts[2], parts[3]
        if destination != "00000000":
            continue
        try:
            if not (int(flags, 16) & 0x2):
                continue
        except ValueError:
            continue
        ip = _hex_to_ipv4_little_endian(gateway)
        if ip:
            return ip
    return None


def parse_default_gateway_windows(text: str) -> str | None:
    """Parse `route print -4` output for the default (0.0.0.0) gateway."""
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
            ip_match = _IPV4_PATTERN.fullmatch(parts[2])
            if ip_match:
                return ip_match.group(1)
    return None


# --- platform gateway-MAC lookup (best effort, untested here) --------------


def _run(command: list[str]) -> str:
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=10, check=False
        )
        return completed.stdout or ""
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - platform
        return ""


def current_gateway_mac() -> str | None:  # pragma: no cover - platform dependent
    """Return the MAC of the current default gateway, or None if unknown."""
    import platform

    system = platform.system()
    if system == "Windows":
        gateway = parse_default_gateway_windows(_run(["route", "print", "-4"]))
        if not gateway:
            return None
        return parse_arp_table(_run(["arp", "-a"])).get(gateway)
    # Linux (and other POSIX with /proc).
    gateway = None
    try:
        with open("/proc/net/route", encoding="utf-8") as fh:
            gateway = parse_default_gateway_linux(fh.read())
    except OSError:
        return None
    if not gateway:
        return None
    table = parse_arp_table(_run(["ip", "neigh"]))
    if not table:
        try:
            with open("/proc/net/arp", encoding="utf-8") as fh:
                table = parse_arp_table(fh.read())
        except OSError:
            return None
    return table.get(gateway)


# --- accumulator -----------------------------------------------------------


@dataclass
class NetworkScope:
    """Accumulates interface counters only across on-network intervals.

    `gateway_macs` is the allow-list of normalized gateway MACs that mean
    "on my network". `totals` maps interface name -> [accumulated_rx, tx].
    """

    gateway_macs: set[str] = field(default_factory=set)
    totals: dict[str, list[int]] = field(default_factory=dict)
    _prev_raw: dict[str, list[int]] | None = None
    _prev_matched: bool = False

    def set_initial_match(self, matched: bool) -> None:
        """Seed whether the sample *before* the first observation was on-net."""
        self._prev_matched = matched

    def matches(self, current_mac: str | None) -> bool:
        mac = normalize_mac(current_mac)
        return bool(mac) and mac in self.gateway_macs

    def observe(self, raw: dict[str, list[int]], current_mac: str | None) -> None:
        matched_now = self.matches(current_mac)
        if self._prev_raw is None:
            # No baseline yet. If we were already on-network, count from zero;
            # otherwise just record the baseline without counting pre-join bytes.
            if self._prev_matched:
                for name, values in raw.items():
                    self.totals[name] = [int(values[0]), int(values[1])]
        elif self._prev_matched:
            for name, values in raw.items():
                previous = self._prev_raw.get(name)
                if previous is None:
                    # New interface: establish baseline, count nothing yet.
                    continue
                d_recv = int(values[0]) - previous[0]
                d_sent = int(values[1]) - previous[1]
                # Counter reset/wrap: clamp, never produce a negative delta.
                d_recv = max(0, d_recv)
                d_sent = max(0, d_sent)
                current = self.totals.setdefault(name, [0, 0])
                current[0] += d_recv
                current[1] += d_sent

        self._prev_raw = {name: [int(v[0]), int(v[1])] for name, v in raw.items()}
        self._prev_matched = matched_now

    # -- persistence --------------------------------------------------------
    def to_state(self) -> dict:
        return {
            "totals": {k: list(v) for k, v in self.totals.items()},
            "prev_raw": (
                {k: list(v) for k, v in self._prev_raw.items()}
                if self._prev_raw is not None
                else None
            ),
            "prev_matched": self._prev_matched,
        }

    @classmethod
    def from_state(cls, gateway_macs: set[str], data: dict) -> "NetworkScope":
        scope = cls(gateway_macs=set(gateway_macs))
        totals = data.get("totals") or {}
        scope.totals = {k: [int(v[0]), int(v[1])] for k, v in totals.items()}
        prev_raw = data.get("prev_raw")
        if prev_raw:
            scope._prev_raw = {k: [int(v[0]), int(v[1])] for k, v in prev_raw.items()}
        scope._prev_matched = bool(data.get("prev_matched", False))
        return scope


def build_scoped_result(scope: NetworkScope, *, interval_seconds: int) -> CollectionResult:
    """Shape accumulated per-interface totals into a CollectionResult.

    The reported scope stays `device_total` but quality is `estimated`: the
    figure counts only on-network intervals, at `interval_seconds` resolution,
    so it is not an exact device-wide total.
    """
    result = CollectionResult(
        measurement_scope="device_total",
        measurement_quality="estimated",
        notes=[
            "Counts only traffic measured while on the home network, sampled "
            f"every {interval_seconds}s. Switching networks mid-interval may "
            "misattribute up to one interval of traffic.",
        ],
    )
    for name in sorted(scope.totals):
        recv, sent = scope.totals[name]
        result.interfaces.append(
            InterfaceCounters(
                name=name,
                bytes_received_total=int(recv),
                bytes_sent_total=int(sent),
            )
        )
    return result


def collect_for_report(
    *,
    config,
    collected: CollectionResult,
    prev_scope_state: dict,
    current_mac: str | None,
) -> tuple[CollectionResult, dict]:
    """Glue a raw CollectionResult into an in-scope result for reporting.

    In "device" scope the collected result passes through unchanged and no
    scope state is kept. In "home_network" scope the raw counters are folded
    into a persistent accumulator and the accumulated totals are reported.
    """
    if getattr(config, "count_scope", "device") != "home_network":
        return collected, {}

    gates = {normalize_mac(m) for m in config.gateway_macs}
    gates.discard(None)
    scope = NetworkScope.from_state(gates, prev_scope_state or {})
    scope.observe({i.name: [i.bytes_received_total, i.bytes_sent_total] for i in collected.interfaces}, current_mac)
    result = build_scoped_result(scope, interval_seconds=config.sample_seconds)
    return result, scope.to_state()