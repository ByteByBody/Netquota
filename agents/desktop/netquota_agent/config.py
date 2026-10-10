"""Agent configuration and platform paths."""

from __future__ import annotations

import json
import os
import platform
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

APP_NAME = "NetQuotaAgent"
DEFAULT_INTERVAL_SECONDS = 300


def config_dir() -> Path:
    override = os.environ.get("NETQUOTA_AGENT_CONFIG_DIR")
    if override:
        return Path(override)
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        return Path(base) / "NetQuota"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "NetQuota"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "netquota"


def config_path() -> Path:
    return config_dir() / "agent.json"


def state_path() -> Path:
    return config_dir() / "state.json"


def credential_path() -> Path:
    return config_dir() / "credential"


@dataclass
class AgentConfig:
    server_url: str = "http://127.0.0.1:8000"
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS
    heartbeat_seconds: int = 300
    verify_tls: bool = True
    # "primary" excludes virtual/bridge/VPN interfaces; "all" counts everything.
    interface_policy: str = "primary"
    # Explicit allow/deny overrides, e.g. ["Ethernet", "Wi-Fi"].
    include_interfaces: list[str] = field(default_factory=list)
    exclude_interfaces: list[str] = field(default_factory=list)

    @classmethod
    def load(cls) -> "AgentConfig":
        path = config_path()
        data: dict = {}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        # Environment overrides.
        if os.environ.get("NETQUOTA_SERVER_URL"):
            data["server_url"] = os.environ["NETQUOTA_SERVER_URL"]
        if os.environ.get("NETQUOTA_INTERVAL_SECONDS"):
            data["interval_seconds"] = int(os.environ["NETQUOTA_INTERVAL_SECONDS"])
        if os.environ.get("NETQUOTA_INTERFACE_POLICY"):
            data["interface_policy"] = os.environ["NETQUOTA_INTERFACE_POLICY"]
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self) -> None:
        config_dir().mkdir(parents=True, exist_ok=True)
        config_path().write_text(
            json.dumps(asdict(self), indent=2), encoding="utf-8"
        )


def platform_name() -> str:
    system = platform.system()
    if system == "Windows":
        return "windows"
    if system == "Linux":
        return "linux"
    if system == "Darwin":
        # macOS is not a supported agent platform in this release.
        return "unknown"
    return "unknown"