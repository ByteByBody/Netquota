# NetQuota delivery checklist

Status legend: [x] done + tested, [~] implemented, not yet build-verified on the
target platform, [ ] planned.

## Phase 1 — Backend foundation
- [x] Monorepo layout
- [x] FastAPI app, config, async SQLAlchemy
- [x] Models: devices, groups, group_assignments, quota_periods, usage_samples,
      usage_deltas, events, admin users, sessions, enrollment codes
- [x] Alembic migrations scaffold
- [x] Administrator auth (JWT + revocable sessions)
- [x] Device + group management endpoints
- [x] OpenAPI documentation at /docs

## Phase 2 — Accounting engine
- [x] Cumulative-counter ingestion, transactional deltas
- [x] Uniqueness on (device, sequence, interface); idempotent retries
- [x] Counter reset / wrap handling (agent-flagged and value-based)
- [x] Interface selection policy (virtual/bridge/VPN excluded)
- [x] New-interface baseline (no double count)
- [x] Out-of-order / future-sample handling
- [x] Group attribution preserved across reassignment
- [x] Quota periods (configurable reset day), usage aggregation
- [x] Threshold alerts 80/90/100 deduplicated
- [x] Stale-agent detection deduplicated

## Phase 3 — Simulated agent
- [x] Deterministic simulator enrolling + reporting
- [x] Duplicate-sample test proving no double count

## Phase 4 — Windows / Linux agents
- [~] Shared collector (psutil), interface policy
- [~] Reporter with retry/backoff + persistent sequence state
- [~] Secure credential storage (keyring, file fallback)
- [~] systemd unit + Windows service + install scripts
- [x] Home-network scoped counting (gateway MAC rule + accumulator)
- [x] Standalone `netquota-lite.py` (stdlib only, for routers/NAS/Pi)
- [x] Unit tests for accumulator, parsers, gluing (22 tests)

## Phase 5 — Dashboard
- [~] React + TS + Vite + Tailwind + Recharts
- [~] Pages: Dashboard, Devices, Device detail, Groups, Settings
- [~] Responsive, dark/light, PWA manifest

## Phase 6 — Android agent
- [~] Kotlin, Gradle, WorkManager, Keystore, TrafficStats
- [~] Consent + status UI
- [ ] Android unit tests (needs Android SDK)

## Phase 7 — iOS agent
- [~] SwiftUI, Keychain, URLSession, BackgroundTasks
- [~] Honest measurement-quality reporting (documented limitation)
- [ ] iOS tests (needs Xcode)

## Phase 8 — Deployment
- [x] Docker Compose (Postgres + backend, healthchecks)
- [x] Caddy TLS reverse proxy
- [x] Backups / recovery docs
- [x] Privacy, protocol, architecture, limitations docs

## Phase 9 — Home deployment (Windows host + roommate)
- [x] Single self-contained `net-quota.exe` launcher (`run` / `stop` / `status` / `install`)
- [x] Role-aware: `host` supervises backend + dashboard + agent; `agent` runs the bundled agent only
- [x] Bundled agent, so an agent-only PC needs no Python/git and keeps its existing enrollment
- [x] Auto-start at login via a Startup shortcut that opens no console window
- [x] Components run in the background, auto-restart if closed, log to `%ProgramData%\NetQuota\logs`
- [x] Single-instance mutex so a second supervisor can't double-start components
- [x] Backend + dashboard bound to the LAN (`0.0.0.0`); firewall rules for 8000 / 5173
- [x] Roommate enrollment verified over the LAN
- [x] Login shortcut created with a plain COM `IShellLink` (no `wscript`/VBS dependency)
- [x] Launcher tests: path/role resolution, component plan, supervisor loop, process selectors

## Verification
- [x] Backend test suite green (29 tests, `pytest` in server/)
- [x] Desktop agent test suite green (29 tests, `pytest` in agents/desktop/)
- [x] Launcher test suite green (`pytest` in tools/tests)
- [x] `dist\net-quota.exe` built and installed on the host (backend + dashboard + agent up, reporting every ~6s)
- [x] Dashboard TypeScript + production build passes (`npm run build`)
- [x] OpenAPI contract generated (`shared/openapi/openapi.json`)
- [x] End-to-end: simulator -> API -> Postgres-shaped accounting -> dashboard summary
- [~] Android build + unit tests (no Android SDK in this environment)
- [~] iOS build + unit tests (no Xcode in this environment)
- [~] Real Windows/Linux host run of the collector