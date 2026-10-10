"""HTTP client for the NetQuota server: enrollment, heartbeat, usage.

Uses only the standard library (urllib) so the agent has no heavy HTTP
dependency. Implements bounded retry with exponential backoff and jitter, and
treats 4xx (except 429) as permanent so it does not retry forever.
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from . import __version__


@dataclass
class ApiError(Exception):
    status: int | None
    message: str

    def __str__(self) -> str:  # pragma: no cover
        return f"ApiError(status={self.status}, message={self.message})"


class ApiClient:
    def __init__(
        self,
        base_url: str,
        *,
        device_id: str | None = None,
        credential: str | None = None,
        verify_tls: bool = True,
        timeout: float = 15.0,
        max_retries: int = 4,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.device_id = device_id
        self.credential = credential
        self.timeout = timeout
        self.max_retries = max_retries
        # urllib only allows disabling verification via an https context; we
        # accept the setting but default to verifying.
        self.verify_tls = verify_tls

    # -- low level -----------------------------------------------------------
    def _request(
        self, method: str, path: str, body: dict | None = None, *, auth: bool = True
    ) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json", "User-Agent": f"netquota-agent/{__version__}"}
        if auth:
            if not self.device_id or not self.credential:
                raise ApiError(None, "missing device credentials")
            headers["X-Device-Id"] = self.device_id
            headers["X-Device-Credential"] = self.credential

        delay = 1.0
        last: ApiError | None = None
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
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

    # -- API -----------------------------------------------------------------
    def enroll(
        self,
        *,
        enrollment_code: str,
        name: str,
        platform: str,
        measurement_scope: str,
        measurement_quality: str,
        capabilities: dict,
        installation_id: str | None = None,
    ) -> dict:
        return self._request(
            "POST",
            "/api/v1/enroll",
            {
                "enrollment_code": enrollment_code,
                "name": name,
                "platform": platform,
                "agent_version": __version__,
                "measurement_scope": measurement_scope,
                "measurement_quality": measurement_quality,
                "capabilities": capabilities,
                "installation_id": installation_id,
            },
            auth=False,
        )

    def heartbeat(self, *, state: dict) -> dict:
        return self._request(
            "POST",
            "/api/v1/agent/heartbeat",
            {
                "schema_version": 1,
                "agent_version": __version__,
                "status": state.get("status", "online"),
                "last_sequence": state.get("last_sequence"),
                "measurement_scope": state.get("measurement_scope"),
                "measurement_quality": state.get("measurement_quality"),
                "capabilities": state.get("capabilities", {}),
            },
        )

    def report_usage(self, payload: dict) -> dict:
        return self._request("POST", "/api/v1/agent/usage", payload)

    def get_config(self) -> dict:
        return self._request("GET", "/api/v1/agent/config")