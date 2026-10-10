"""Network-counter collection via psutil with an explicit interface policy.

Selection policy (documented in docs/platform-limitations.md):
  * primary (default): count physical interfaces only; exclude loopback,
    virtual/bridge/VPN/tunnel adapters which would double-count traffic.
  * all: count every interface except loopback.
  * include/exclude overrides from config win over the policy.

On Windows the primary interface is usually "Ethernet" or "Wi-Fi". On Linux it
is usually "eth0"/"enp*"/"wlan0"/"wlp*". Using psutil's per-interface counters
for these avoids double counting through bridges and VPNs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

try:
    import psutil
except ImportError:  # pragma: no cover - import guard for tests without psutil
    psutil = None  # type: ignore

_VIRTUAL_PREFIXES = (
    "lo",
    "docker",
    "br-",
    "veth",
    "virbr",
    "vmnet",
    "vboxnet",
    "tun",
    "tap",
    "wg",
    "utun",
    "awdl",
    "llw",
    "bridge",
    "teredo",
    "isatap",
    "loopback",
    "bluetooth",
    "npcap",
    "vethernet",
)


def is_virtual(name: str) -> bool:
    n = name.strip().lower().replace(" ", "")
    return any(n.startswith(p) for p in _VIRTUAL_PREFIXES)


@dataclass
class InterfaceCounters:
    name: str
    bytes_received_total: int
    bytes_sent_total: int


@dataclass
class CollectionResult:
    interfaces: list[InterfaceCounters] = field(default_factory=list)
    measurement_scope: str = "device_total"
    measurement_quality: str = "exact"
    notes: list[str] = field(default_factory=list)


def select_interfaces(
    counters: dict,
    *,
    policy: str = "primary",
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> list[str]:
    include = include or []
    exclude = exclude or []
    selected: list[str] = []
    for name in counters:
        if name in include:
            selected.append(name)
            continue
        if name in exclude:
            continue
        if policy == "all":
            if name.lower() != "lo":
                selected.append(name)
            continue
        # primary policy
        if is_virtual(name):
            continue
        selected.append(name)
    return selected


def collect(
    *,
    policy: str = "primary",
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> CollectionResult:
    if psutil is None:  # pragma: no cover
        return CollectionResult(
            measurement_scope="unsupported",
            measurement_quality="unknown",
            notes=["psutil is not installed; cannot read interface counters."],
        )

    raw = psutil.net_io_counters(pernic=True)
    names = select_interfaces(
        raw, policy=policy, include=include, exclude=exclude
    )
    result = CollectionResult()
    for name in sorted(names):
        c = raw[name]
        result.interfaces.append(
            InterfaceCounters(
                name=name,
                bytes_received_total=int(c.bytes_recv),
                bytes_sent_total=int(c.bytes_sent),
            )
        )
    if not result.interfaces:
        result.measurement_scope = "unsupported"
        result.measurement_quality = "unknown"
        result.notes.append("No countable network interfaces were found.")
    return result