# NetQuota architecture

NetQuota is a self-hosted household tool that measures internet usage reported by
agents on enrolled devices, groups those devices, and tracks each group's monthly
quota. It is a monitoring and alerting system: it never blocks, throttles, or
disconnects anything.

## Components

```
                    ┌───────────────────────────────────────────┐
                    │            Home server (Docker)            │
                    │                                            │
  Windows agent ───►│  Caddy (TLS)  ─►  FastAPI (api)  ─►  Postgres│
  Linux agent   ───►│                     │                      │
  Android app   ───►│                     ├─ accounting engine    │
  iPhone app    ───►│                     ├─ quota engine         │
                    │                     └─ alerts               │
  Browser  ────────►│  Caddy  ─►  Dashboard (static React)        │
                    └───────────────────────────────────────────┘
```

- **server/** — FastAPI + SQLAlchemy (async) + PostgreSQL. Owns all accounting,
  quota, and alert logic. Platform- and agent-agnostic.
- **apps/dashboard/** — React + TS + Vite + Tailwind + Recharts admin UI.
- **agents/desktop/** — shared Python agent for Windows and Linux (psutil).
- **apps/android-agent/** — Kotlin + Compose + WorkManager + TrafficStats.
- **apps/ios-agent/** — SwiftUI + Keychain + URLSession + BackgroundTasks.
- **shared/openapi/** — the versioned API contract.

## Data model

UUID primary keys (stored as 36-char strings for portability), UTC timestamps.

| Table | Purpose |
|-------|---------|
| `devices` | Registered devices, hashed credentials, last-seen, capability metadata. |
| `groups` | Groups with a name and quota reset day. |
| `group_assignments` | Time-bounded membership; history preserved on reassignment. |
| `quota_periods` | One active period per group (configurable monthly reset). |
| `usage_samples` | Raw cumulative counter observations. |
| `usage_deltas` | Calculated traffic attributed to device + group + period. |
| `events` | Thresholds, staleness, enrollment, accounting warnings. |
| `admin_users`, `admin_sessions` | Administrator accounts and revocable sessions. |
| `enrollment_codes` | Single-use, expiring enrollment codes. |

### Why samples *and* deltas

Agents report **cumulative** counters, never deltas. The server stores every
observation in `usage_samples` and derives `usage_deltas` transactionally. This
makes retries idempotent (`UNIQUE(device_id, sequence, interface_name)`), lets
counter resets be detected after the fact, and keeps a complete audit trail.

## Accounting engine (`app/services/usage.py`)

For each interface, the delta between successive valid samples is
`received_delta + sent_delta`. Rules:

- **Baseline**: the first ever sample yields zero delta.
- **Counter reset / wrap**: if the new counter is lower than the previous one, or
  the agent flags `reset: true`, the old counter is discarded and the delta is
  the new total (never a negative or a huge bogus value).
- **New interface**: a previously unseen interface establishes a baseline and
  yields no delta on first sight, so pre-existing counters are not counted.
- **Out-of-order**: sample `N` is only compared against the latest accepted
  sample with a smaller sequence. Duplicates return early with `duplicate: true`.
- **Interface selection**: virtual/bridge/VPN/tunnel interfaces are excluded under
  the `primary` policy to avoid double counting. Non-selected interfaces are still
  stored as samples so history and renames remain visible.
- **Clock skew**: samples more than `max_clock_skew_seconds` in the future are
  rejected.

Bytes are integers throughout. Conversion to GiB happens only in the UI.

## Quota engine (`app/services/quotas.py`)

Per group and active period:

```
group_usage      = Σ (received_bytes + sent_bytes)
remaining_bytes  = max(0, quota_bytes - group_usage)
percentage_used  = 100 * group_usage / quota_bytes
```

`get_or_create_period` computes the period from the group's `reset_day` using
`month_bounds`, so month transitions are automatic and historical deltas keep the
period they were recorded in. Changing a device's group never moves previously
recorded usage: deltas reference the group that was active at record time.

## Alerts (`app/services/alerts.py`)

- Threshold events at 80%, 90%, 100%, deduplicated per `(period, threshold)` via
  a unique `dedupe_key`.
- Stale-agent events when a device has not reported within
  `stale_after_minutes`; deduplicated per stale episode (`device + last_seen`),
  so a device that recovers and goes stale again produces a new event.

## Security

- Administrator auth: JWT (HS256) with revocable server-side sessions.
- Device auth: high-entropy token; only a SHA-256 id (indexed) and a PBKDF2 hash
  are stored. Revocation rotates and invalidates the credential.
- Enrollment: single-use, expiring codes stored hashed only.
- Rate limiting on `/enroll` and `/auth/login` (in-process; single-instance).
- PostgreSQL is not published to the host (see `deployment/docker-compose.yml`).
- TLS terminated by Caddy.

## Configuration

Environment variables (prefix `NETQUOTA_`), see `server/app/config.py`. Key ones:

| Variable | Default | Meaning |
|----------|---------|---------|
| `NETQUOTA_DATABASE_URL` | `sqlite+aiosqlite:///./netquota.db` | DB URL (Postgres in deployment). |
| `NETQUOTA_JWT_SECRET` | dev value | **Must** be set in production. |
| `NETQUOTA_ADMIN_BOOTSTRAP_PASSWORD` | unset | Creates the first admin at startup. |
| `NETQUOTA_STALE_AFTER_MINUTES` | 30 | Stale threshold. |
| `NETQUOTA_INTERFACE_POLICY` | `primary` | Interface selection for ingestion. |

## Local development

```sh
# Backend (SQLite by default, no Postgres needed)
cd server
python -m venv .venv && .venv/Scripts/activate     # Windows
pip install -e ".[dev]"
uvicorn app.main:app --reload
pytest

# Dashboard
cd apps/dashboard
npm install
npm run dev     # proxies /api to http://127.0.0.1:8000
```

Seed demo data (clearly labelled synthetic):

```sh
python scripts/seed_demo.py --password <admin-password>
```

## Database and backup

Production uses PostgreSQL in Docker. Back up:

```sh
docker compose exec -T db pg_dump -U netquota netquota > backup-$(date +%F).sql
```

Restore:

```sh
cat backup-2026-10-10.sql | docker compose exec -T db psql -U netquota -d netquota
```

The named volume `db_data` holds the database; also back up `deployment/.env`.
Test a restore on a throwaway database before relying on it.

## Migrations

Alembic is configured (`server/alembic.ini`, `server/migrations/`). The container
runs `alembic upgrade head` at start. To create a migration after model changes:

```sh
cd server
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```