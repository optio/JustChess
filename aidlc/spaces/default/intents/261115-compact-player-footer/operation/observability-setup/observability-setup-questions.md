# Observability Setup Questions

## Evidence

Production runs on Vercel (Hobby, function region `fra1`) with Neon PostgreSQL `aws eu-central-1`; no NFR or infrastructure design exists (express scope). Measured 2026-11-15 after the latency fix: room read ~0.11 s, move delivery ≤ 0.12 s, computer reply ~0.22 s (`../deployment-execution/smoke-test-results.md`). Vercel Hobby keeps runtime logs only briefly and has no built-in alerting; GitHub Actions CI already runs (`tests`). Existing signals: `GET /`, `GET /api/engine`, `GET /api/cron/maintenance` (401 without secret), 89 structured `logger` calls in `justchess/`.

## Q1 — Service level objectives

A. 99.5% availability per 30 days and 95% of moves delivered within 1 s.
B. 99% availability per 30 days and 95% of moves delivered within 2 s.
C. No formal targets.
X. Other (please specify)

[Answer]: B. 99% / 2 s (message 082d61ed).

## Q2 — Alerting

A. GitHub Actions scheduled check of Production every 30 minutes; GitHub emails the owner on failure.
B. External uptime service the owner signs up for.
C. No alerts.
X. Other (please specify)

[Answer]: A. GitHub scheduled check (message 082d61ed).

## Q3 — Health endpoint

A. Add `GET /api/health`: read-only database and engine check, 200 or 503.
B. Monitor existing URLs only.
X. Other (please specify)

[Answer]: A. Add /api/health (message 082d61ed).
