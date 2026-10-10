"""Persistent local sequence state.

The sequence number must survive agent restarts so the server can order samples
and detect gaps. State is stored atomically next to the credential.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .config import state_path


@dataclass
class AgentState:
    device_id: str | None = None
    sequence: int = 0
    installation_id: str | None = None
    last_report_at: str | None = None
    last_report_ok: bool = False
    last_error: str | None = None
    # Per-interface cumulative counters at last successful report, used to
    # detect resets even when the OS counter is recreated.
    counters: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> "AgentState":
        path = path or state_path()
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return cls()
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: Path | None = None) -> None:
        path = path or state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: temp file + replace.
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(asdict(self), fh, indent=2)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def next_sequence(self) -> int:
        self.sequence += 1
        return self.sequence