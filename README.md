# NetQuota

Self-hosted internet usage and group quota monitoring for a home network.

NetQuota registers the devices in your household, groups them, gives each group a
monthly data allowance, and tracks usage reported by agents on Windows, Linux,
Android, and iPhone. It shows remaining quota, consumption, history, and alerts at
80 / 90 / 100%, and flags devices that have gone quiet.

**This release is monitoring and alerting only.** NetQuota never blocks, throttles,
or disconnects anything.

> Displayed figures are device-reported usage, not guaranteed ISP-billed usage.
> See [docs/platform-limitations.md](docs/platform-limitations.md) — iOS in
> particular cannot measure whole-device usage with public APIs.

## What's here

| Component | Stack | Status |
|-----------|-------|--------|
| Backend | FastAPI, SQLAlchemy (async), PostgreSQL, Alembic, pytest | Implemented, 29 backend tests pass |
| Dashboard | React, TypeScript, Vite, Tailwind, Recharts, PWA | Implemented, production build passes |
| Windows/Linux agent | Python, psutil | Implemented, unit tests pass |
| Simulator | Python | Implemented, drives the real backend in tests |
| Android agent | Kotlin, Compose, WorkManager, Keystore, TrafficStats | Source complete; needs Android SDK to build |
| iOS agent | SwiftUI, Keychain, URLSession, BackgroundTasks | Source complete; needs Xcode to build |
| Deployment | Docker Compose, Caddy, PostgreSQL | Implemented |

Full build/verification status: [docs/CHECKLIST.md](docs/CHECKLIST.md).

## Quick start (development, no Docker)

The backend defaults to SQLite so you can run it immediately.

```sh
# 1. Backend
cd server
python -m venv .venv
. .venv/Scripts/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
NETQUOTA_ADMIN_BOOTSTRAP_PASSWORD=changeme uvicorn app.main:app --reload
# API docs at http://127.0.0.1:8000/docs

# 2. Dashboard (new terminal)
cd apps/dashboard
npm install
npm run dev                          # http://127.0.0.1:5173

# 3. Demo data (optional, clearly labelled synthetic)
cd server
python scripts/seed_demo.py --password changeme
```

Sign in at http://127.0.0.1:5173 with `admin` / `changeme`.

## Quick start (home server, Docker)

```sh
cd deployment
cp .env.example .env                 # edit POSTGRES_PASSWORD, JWT_SECRET, ADMIN_PASSWORD
docker compose up -d --build
```

Build the dashboard and copy it to Caddy's site root (or serve it separately):

```sh
cd apps/dashboard && npm ci && npm run build
# copy apps/dashboard/dist/* to the caddy /srv location referenced in deployment/Caddyfile
```

See [docs/architecture.md](docs/architecture.md) for backup/restore and TLS.

## Enroll a device

1. In the dashboard, open **Settings**, optionally choose a group, and generate a
   single-use enrollment code.
2. On the device, run the agent with that code.

Desktop (Windows/Linux):

```sh
netquota-agent enroll --server https://netquota.local --code <CODE> --name "Living Room PC"
netquota-agent run
```

Installers: `agents/desktop/packaging/install-windows.ps1` and
`install-linux.sh` (systemd). Android and iOS: build the apps under `apps/` and
follow their READMEs.

Without any real device you can exercise the whole system with the simulator:

```sh
cd agents/desktop
python simulate.py --server http://127.0.0.1:8000 --code <CODE> --samples 24
```

## Repository layout

```
netquota/
├── apps/
│   ├── dashboard/          React admin UI
│   ├── android-agent/      Kotlin Android app
│   └── ios-agent/          SwiftUI iOS app
├── server/                 FastAPI backend, migrations, tests, scripts
├── agents/desktop/         Shared Windows/Linux Python agent + simulator
├── shared/openapi/         Generated OpenAPI contract
├── deployment/             docker-compose.yml, Caddyfile, .env.example
└── docs/                   architecture, protocol, privacy, limitations, checklist
```

## How usage accounting works (short version)

Agents send **cumulative** counters, never deltas. The server stores each raw
sample (`usage_samples`) and derives `usage_deltas` transactionally:

- a retried sample can never be counted twice (`UNIQUE(device_id, sequence,
  interface_name)`),
- counter resets/wraps re-baseline instead of producing bogus numbers,
- a newly seen interface starts at a baseline (no double counting),
- virtual/bridge/VPN interfaces are excluded by default to avoid double counting,
- a device changing group keeps its history attributed to the old group.

Alerts at 80/90/100% are deduplicated per period, and stale devices are flagged
without inventing usage. Details: [docs/protocol.md](docs/protocol.md) and
[docs/architecture.md](docs/architecture.md).

## Testing

```sh
# Backend (SQLite, no services required)
cd server && pytest

# Desktop agent
cd agents/desktop && pytest
```

The backend suite covers enrollment, revocation, duplicate/out-of-order samples,
counter resets, interface changes, group reassignment and historical attribution,
quota maths, monthly transitions, threshold de-duplication, stale detection,
authorization, and input validation.

Android and iOS unit tests are provided; they require their respective SDKs to run
(see the CHECKLIST for what has and has not been verified on this machine).

## Explicitly not in this release

- No blocking, throttling, or automatic disconnection.
- No packet inspection, browsing history, or per-app monitoring.
- No covert monitoring: every agent discloses what it collects and shows its
  monitoring state.
- No public-internet exposure of the management API (use a VPN for remote access).

## Documentation

- [docs/architecture.md](docs/architecture.md) — components, data model, config, backups
- [docs/protocol.md](docs/protocol.md) — the versioned agent API
- [docs/privacy.md](docs/privacy.md) — what is and isn't collected, revocation
- [docs/platform-limitations.md](docs/platform-limitations.md) — per-platform measurement truth
- [docs/CHECKLIST.md](docs/CHECKLIST.md) — implementation and verification status

## License

Provided as-is for self-hosting. Add a LICENSE file appropriate to your use.