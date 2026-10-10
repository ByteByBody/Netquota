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

## Verification
- [x] Backend test suite green (29 tests, `pytest` in server/)
- [x] Desktop agent test suite green (7 tests, `pytest` in agents/desktop/)
- [x] Dashboard TypeScript + production build passes (`npm run build`)
- [x] OpenAPI contract generated (`shared/openapi/openapi.json`)
- [x] End-to-end: simulator -> API -> Postgres-shaped accounting -> dashboard summary
- [~] Android build + unit tests (no Android SDK in this environment)
- [~] iOS build + unit tests (no Xcode in this environment)
- [~] Real Windows/Linux host run of the collector