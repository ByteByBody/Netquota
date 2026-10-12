"""Keep-alive loop: (re)start the role's components and keep them running.

The logic is deliberately free of Windows calls so it can be unit tested; the
platform-specific ``is_up`` / ``start`` behaviour is injected by ``main``.
"""

from __future__ import annotations

import time
from typing import Callable

from .plan import Component


class Supervisor:
    def __init__(
        self,
        components: list[Component],
        *,
        is_up: Callable[[Component], bool],
        start: Callable[[Component], None],
        cooldown: float = 15.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._components = list(components)
        self._is_up = is_up
        self._start = start
        self._cooldown = cooldown
        self._clock = clock
        self._last_start: dict[str, float] = {}

    def ensure_once(self) -> list[str]:
        """Start every missing, non-cooling-down component; return their names."""
        started: list[str] = []
        now = self._clock()
        for component in self._components:
            if self._is_up(component):
                continue
            last = self._last_start.get(component.name)
            if last is not None and (now - last) < self._cooldown:
                continue
            self._start(component)
            self._last_start[component.name] = now
            started.append(component.name)
        return started

    def run(
        self,
        *,
        stop_requested: Callable[[], bool],
        sleep: Callable[[float], None] = time.sleep,
        poll_seconds: float = 3.0,
    ) -> None:
        self.ensure_once()
        while not stop_requested():
            sleep(poll_seconds)
            self.ensure_once()
