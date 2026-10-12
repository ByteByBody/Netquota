"""Filesystem locations, repo discovery, and role resolution for the launcher.

The launcher shares its data directory with the agent (``%ProgramData%\\NetQuota``
on Windows) so the agent's config, state and credential are reused unchanged.
"""

from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass
from pathlib import Path

_ROLES = ("host", "agent")


def data_dir() -> Path:
    """Shared NetQuota data directory (overridable for tests/deployments)."""
    override = os.environ.get("NETQUOTA_DATA_DIR")
    if override:
        return Path(override)
    if platform.system() == "Windows":
        base = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        return Path(base) / "NetQuota"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "netquota"


def role_file(data: Path) -> Path:
    return Path(data) / "role.txt"


def log_dir(data: Path) -> Path:
    return Path(data) / "logs"


def stop_flag(data: Path) -> Path:
    return Path(data) / "supervisor.stop"


def launcher_config_path(data: Path) -> Path:
    return Path(data) / "launcher.json"


def find_repo(start: Path) -> Path | None:
    """Walk up from *start* to the first directory that looks like a checkout."""
    start = Path(start).resolve()
    for candidate in (start, *start.parents):
        if (candidate / "server").is_dir() and (candidate / "agents").is_dir():
            return candidate
    return None


def resolve_role(data: Path, repo: Path | None) -> str:
    """Explicit role file wins; otherwise infer ``host`` from a server venv."""
    rf = role_file(data)
    if rf.exists():
        value = rf.read_text(encoding="utf-8").strip().lower()
        if value in _ROLES:
            return value
    if repo is not None:
        repo = Path(repo)
        for rel in ("server/.venv/Scripts/python.exe", "server/.venv/bin/python"):
            if (repo / rel).exists():
                return "host"
    return "agent"


@dataclass
class LauncherConfig:
    repo_root: Path | None = None

    def __post_init__(self) -> None:
        if self.repo_root is not None:
            self.repo_root = Path(self.repo_root)


def read_launcher_config(data: Path) -> LauncherConfig:
    path = launcher_config_path(data)
    if not path.exists():
        return LauncherConfig()
    raw = json.loads(path.read_text(encoding="utf-8"))
    root = raw.get("repo_root")
    return LauncherConfig(repo_root=Path(root) if root else None)


def write_launcher_config(data: Path, config: LauncherConfig) -> None:
    data = Path(data)
    data.mkdir(parents=True, exist_ok=True)
    payload = {"repo_root": str(config.repo_root) if config.repo_root else None}
    launcher_config_path(data).write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
