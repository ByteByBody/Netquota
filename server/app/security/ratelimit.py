"""Rate limiting.

A small in-process sliding-window limiter.  Adequate for a single home-server
instance (10-100 devices).  Documented as such; a multi-instance deployment
should move this to Redis.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, status

_WINDOWS: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(key: str, limit: int, window_seconds: float = 60.0) -> None:
    now = time.monotonic()
    bucket = _WINDOWS[key]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        retry_after = int(window_seconds - (now - bucket[0])) + 1
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
    bucket.append(now)


def reset_rate_limits() -> None:
    """Test helper."""
    _WINDOWS.clear()