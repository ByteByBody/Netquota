# Agent protocol (v1)

Every NetQuota agent — Windows, Linux, Android, iOS, and the simulator —
communicates through the same versioned REST API under `/api/v1`. Quota maths is
never done by an agent.

Base URL example: `https://netquota.local/api/v1`

All request/response bodies are JSON. Timestamps are ISO-8601 UTC (`...Z`).

## Authentication

After enrollment a device holds a **device id** and a **credential**. Every
authenticated call sends:

```
X-Device-Id: <uuid>
X-Device-Credential: <token>
```

The server stores only a hash of the credential. Revoking a device invalidates
it immediately.

## 1. Enrollment

`POST /enroll` — no device auth; rate limited.

```json
{
  "enrollment_code": "single-use-code-from-admin",
  "name": "Living Room PC",
  "platform": "windows",
  "agent_version": "0.1.0",
  "measurement_scope": "device_total",
  "measurement_quality": "exact",
  "capabilities": { "collector": "psutil" },
  "installation_id": "uuid-stable-across-restarts"
}
```

Response:

```json
{
  "device_id": "…",
  "credential": "…",
  "heartbeat_interval_seconds": 300,
  "reporting_interval_seconds": 300,
  "server_time": "2026-10-10T08:45:00Z"
}
```

`platform` ∈ `windows | linux | android | ios | simulator | unknown`.
`measurement_scope` and `measurement_quality` are validated server-side (see
below). The credential is returned **once**; store it in OS secure storage.

## 2. Heartbeat

`POST /agent/heartbeat`

```json
{
  "schema_version": 1,
  "agent_version": "0.1.0",
  "status": "online",
  "last_sequence": 142,
  "measurement_scope": "device_total",
  "measurement_quality": "exact",
  "capabilities": {}
}
```

Response includes `server_time`, `next_heartbeat_seconds`, and
`acknowledged_sequence`.

## 3. Usage report

`POST /agent/usage`

```json
{
  "schema_version": 1,
  "sequence": 142,
  "observed_at": "2026-10-10T08:45:00Z",
  "measurement_scope": "device_total",
  "measurement_quality": "exact",
  "interfaces": [
    { "name": "Wi-Fi", "bytes_received_total": 1250000000, "bytes_sent_total": 185000000, "reset": false }
  ]
}
```

- Counters are **cumulative**, not deltas.
- `sequence` is a strictly increasing integer per device, persisted locally so it
  survives restarts. It is the idempotency key together with the interface name.
- `reset: true` (optional) tells the server the agent observed a counter reset.
  The server also detects resets by comparing counter values.

Response:

```json
{
  "schema_version": 1,
  "accepted": true,
  "duplicate": false,
  "server_time": "2026-10-10T08:45:02Z",
  "acknowledged_sequence": 142,
  "received_bytes": 500000,
  "sent_bytes": 50000,
  "interfaces": [
    { "name": "Wi-Fi", "received_bytes": 500000, "sent_bytes": 50000, "accepted": true, "reason": "ok", "from_reset": false }
  ]
}
```

A repeated `(sequence, interface)` returns `duplicate: true` with zero delta and
never inflates usage. Reasons include `baseline`, `ok`, `agent_reset`, and
`counter_went_backwards`.

## 4. Agent configuration

`GET /agent/config` returns heartbeat/reporting intervals, `stale_after_minutes`,
and the `interface_policy`, plus any measurement notes for this device.

## Measurement scope and quality

| Scope | Meaning |
|-------|---------|
| `device_total` | Whole-device traffic on selected physical interfaces (Windows/Linux). |
| `all_interfaces` | Every interface except loopback. |
| `android_total` | Android `TrafficStats` device totals (since boot; includes mobile). |
| `interface` | A single named interface. |
| `app_only` | Only this app's own traffic (iOS URLSession). |
| `partial` | Only part of the device's traffic is measurable. |
| `unsupported` | No reliable counter is available. |

| Quality | Meaning |
|---------|---------|
| `exact` | The counter covers the claimed scope precisely. |
| `estimated` | Derived or approximate. |
| `partial` | Covers a subset of the scope. |
| `unknown` | Agent could not determine quality. |

Scopes `app_only`, `partial`, and `unsupported` mark the group as having missing
measurements; the dashboard shows a warning and never claims the figure equals
ISP-billed usage.

## Administrator endpoints (dashboard)

Separate authentication: `POST /auth/login` returns a JWT bearer token.
Passwords are hashed with PBKDF2; sessions are revocable.

`GET /dashboard/summary`, `GET /devices`, `PATCH /devices/{id}`,
`POST /devices/{id}/revoke`, `GET /devices/{id}/usage`, `GET /groups`,
`POST /groups`, `PATCH /groups/{id}`, `DELETE /groups/{id}`,
`POST /groups/{id}/devices/{device_id}`, `GET /groups/{id}/usage`,
`GET /groups/{id}/usage/series`, `GET /events`,
`POST /enrollment/codes`, `GET /enrollment/codes`,
`DELETE /enrollment/codes/{id}`.

Agent and router credentials are never exposed through the dashboard.

## Error handling and retries

- `4xx` (except `429`) is permanent; do not retry blindly.
- `429` includes `Retry-After`.
- `5xx` and network errors are transient: retry with exponential backoff and
  jitter (the desktop agent caps at 60 s).
- On failure the agent must **not** advance its persisted sequence, so the retry
  reuses the same number and the server deduplicates it.

The machine-readable contract lives in `shared/openapi/openapi.json` and is also
served at `/openapi.json` by a running server.