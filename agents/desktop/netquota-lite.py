#!/usr/bin/env python3
"""NetQuota Lite — home-network usage reporter (stdlib only).

This is a single-file script that can run on any Linux-like system with Python
3.8+ (OpenWrt, Debian, Alpine, NAS, Pi, etc.) without installing dependencies.
It reads /proc/net/dev for cumulative interface counters and reports only the
traffic that occurred while the device's default gateway MAC matched one of the
configured "home" MACs.

Usage:
    python3 netquota-lite.py --server URL --device-id ID --credential TOKEN \
        --gateway-mac aa:bb:cc:dd:ee:ff [--interval 300] [--once]

Configuration is persisted in a state file next to the script, so the
accumulated on-network counters survive restarts. If the state file is lost,
the server will re-baseline automatically (same behaviour as the full agent).

The server expects the same /api/v1/agent/usage payload as the full agent;
the only difference is measurement_quality=estimated and a note explaining
the sampling resolution.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# --- MAC / parsing helpers (mirrored from network_scope.py) ------------------


def normalize_mac(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"[^0-9a-f]", "", value.lower())
    if len(cleaned) != 12 or not all(c in "0123456789abcdef" for c in cleaned):
        return None
    return ":".join(cleaned[i : i + 2] for i in range(0, 12, 2))


_IPV4_PATTERN = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")
_MAC_PATTERN = re.compile(
    r"(?:[0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}|[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}"
)


def parse_arp_table(text: str) -> dict[str, str]:
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
    for line in text.splitlines()[1:]:
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
        try:
            raw = int(gateway, 16).to_bytes(4, "little")
        except (ValueError, OverflowError):
            continue
        ip = ".".join(str(b) for b in raw)
        return ip
    return None


def _run(command: list[str]) -> str:
    try:
        import subprocess
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=10, check=False
        )
        return completed.stdout or ""
    except (OSError, subprocess.SubprocessError):
        return ""


def current_gateway_mac() -> str | None:
    gateway = parse_default_gateway_linux(_run(["ip", "route", "show", "default"]))
    if not gateway:
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


# --- /proc/net/dev reader ----------------------------------------------------


def read_proc_net_dev() -> dict[str, list[int]]:
    """Return {iface: [rx_bytes, tx_bytes]} from /proc/net/dev."""
    try:
        with open("/proc/net/dev", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return {}
    out = {}
    for line in lines[2:]:  # skip header lines
        parts = line.strip().split()
        if not parts:
            continue
        name = parts[0].rstrip(":")
        if not name:
            continue
        try:
            rx = int(parts[1])
            tx = int(parts[9])
        except (IndexError, ValueError):
            continue
        out[name] = [rx, tx]
    return out


# --- accumulator (mirrored) --------------------------------------------------


@dataclass
class NetworkScope:
    gateway_macs: set[str] = field(default_factory=set)
    totals: dict[str, list[int]] = field(default_factory=dict)
    _prev_raw: dict[str, list[int]] | None = None
    _prev_matched: bool = False

    def set_initial_match(self, matched: bool) -> None:
        self._prev_matched = matched

    def matches(self, current_mac: str | None) -> bool:
        mac = normalize_mac(current_mac)
        return bool(mac) and mac in self.gateway_macs

    def observe(self, raw: dict[str, list[int]], current_mac: str | None) -> None:
        matched_now = self.matches(current_mac)
        if self._prev_raw is None:
            if self._prev_matched:
                for name, values in raw.items():
                    self.totals[name] = [int(values[0]), int(values[1])]
        elif self._prev_matched:
            for name, values in raw.items():
                previous = self._prev_raw.get(name)
                if previous is None:
                    continue
                d_recv = max(0, int(values[0]) - previous[0])
                d_sent = max(0, int(values[1]) - previous[1])
                current = self.totals.setdefault(name, [0, 0])
                current[0] += d_recv
                current[1] += d_sent
        self._prev_raw = {name: [int(v[0]), int(v[1])] for name, v in raw.items()}
        self._prev_matched = matched_now

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

    def build_result(self, interval_seconds: int) -> dict:
        result = {
            "measurement_scope": "device_total",
            "measurement_quality": "estimated",
            "notes": [
                "Counts only traffic measured while on the home network, sampled "
                f"every {interval_seconds}s. Switching networks mid-interval may "
                "misattribute up to one interval of traffic.",
            ],
            "interfaces": [],
        }
        for name in sorted(self.totals):
            recv, sent = self.totals[name]
            result["interfaces"].append(
                {
                    "name": name,
                    "bytes_received_total": int(recv),
                    "bytes_sent_total": int(sent),
                }
            )
        return result


# --- HTTP client (stdlib urllib) --------------------------------------------


class ApiError(Exception):
    def __init__(self, status: int | None, message: str):
        self.status = status
        self.message = message
        super().__init__(f"{status}: {message}")


class ApiClient:
    def __init__(
        self,
        base_url: str,
        device_id: str,
        credential: str,
        verify_tls: bool = True,
        timeout: float = 15.0,
        max_retries: int = 4,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.device_id = device_id
        self.credential = credential
        self.timeout = timeout
        self.max_retries = max_retries
        self.verify_tls = verify_tls

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        import random
        import ssl

        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "netquota-lite/0.1.0",
            "X-Device-Id": self.device_id,
            "X-Device-Credential": self.credential,
        }
        context = None
        if not self.verify_tls and url.startswith("https://"):
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        delay = 1.0
        last: ApiError | None = None
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout, context=context) as resp:
                    raw = resp.read().decode()
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode(errors="replace")
                transient = exc.code >= 500 or exc.code == 429
                last = ApiError(exc.code, raw)
                if not transient:
                    raise last
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last = ApiError(None, str(exc))
            if attempt < self.max_retries:
                time.sleep(delay + random.uniform(0, delay / 2))
                delay = min(delay * 2, 60)
        raise last or ApiError(None, "request failed")

    def report_usage(self, payload: dict) -> dict:
        return self._request("POST", "/api/v1/agent/usage", payload)


# --- state persistence -------------------------------------------------------


def state_path_for(script_path: Path) -> Path:
    return script_path.with_name(".netquota_state.json")


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def save_state(path: Path, data: dict) -> None:
    import tempfile
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# --- main --------------------------------------------------------------------


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="NetQuota Lite — home-network usage reporter")
    p.add_argument("--server", required=True, help="NetQuota server base URL (e.g. https://netquota.local)")
    p.add_argument("--device-id", required=True, help="Device UUID from enrollment")
    p.add_argument("--credential", required=True, help="Device credential from enrollment")
    p.add_argument("--gateway-mac", required=True, action="append", help="Gateway MAC(s) that mean 'home'")
    p.add_argument("--interval", type=int, default=300, help="Reporting interval in seconds (default 300)")
    p.add_argument("--sample-interval", type=int, default=30, help="Sampling interval for on-network detection (default 30)")
    p.add_argument("--state-file", default=None, help="Path to state file (default: next to script)")
    p.add_argument("--no-verify-tls", action="store_true", help="Disable TLS verification (for self-signed certs)")
    p.add_argument("--once", action="store_true", help="Report once and exit")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    script_path = Path(__file__).resolve()
    state_file = Path(args.state_file) if args.state_file else state_path_for(script_path)

    # Normalize gateway MACs
    gateway_macs = {normalize_mac(m) for m in args.gateway_mac}
    gateway_macs.discard(None)
    if not gateway_macs:
        print("No valid gateway MACs provided", file=sys.stderr)
        return 1

    client = ApiClient(
        args.server,
        device_id=args.device_id,
        credential=args.credential,
        verify_tls=not args.no_verify_tls,
    )

    # Load persisted scope state
    raw_state = load_state(state_file)
    scope = NetworkScope.from_state(gateway_macs, raw_state.get("network_scope", {}))

    # Initial match: we don't know if the previous sample was on-network.
    # Safer to assume False; the first matched interval will be skipped (no
    # pre-join bytes counted), which slightly under-counts on first run after
    # state loss but never over-counts.
    initial_match = False

    def tick() -> bool:
        nonlocal initial_match
        raw = read_proc_net_dev()
        if not raw:
            print("No interfaces found in /proc/net/dev", file=sys.stderr)
            return False

        current_mac = current_gateway_mac()
        if scope._prev_raw is None:
            scope.set_initial_match(initial_match)
            initial_match = True  # after first tick, use real match state

        scope.observe(raw, current_mac)
        result = scope.build_result(args.sample_interval)

        sequence = raw_state.get("sequence", 0) + 1
        payload = {
            "schema_version": 1,
            "sequence": sequence,
            "observed_at": _iso_now(),
            "measurement_scope": result["measurement_scope"],
            "measurement_quality": result["measurement_quality"],
            "interfaces": result["interfaces"],
        }
        try:
            client.report_usage(payload)
        except ApiError as exc:
            print(f"Report failed: {exc}", file=sys.stderr)
            return False

        raw_state["sequence"] = sequence
        raw_state["network_scope"] = scope.to_state()
        save_state(state_file, raw_state)
        return True

    if args.once:
        return 0 if tick() else 1

    print(f"NetQuota Lite running; interval={args.interval}s, sample={args.sample_interval}s")
    while True:
        tick()
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())