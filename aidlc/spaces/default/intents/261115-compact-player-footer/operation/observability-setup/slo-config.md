# SLO Configuration — JustChess

## Sources

- Owner answer Q1 = 99% / 2 s (`observability-setup-questions.md`, message 082d61ed); baseline from `../deployment-execution/smoke-test-results.md`.

## Objectives (30-day rolling window)

| SLO | SLI | Target | Error budget | Baseline (2026-11-15) |
|---|---|---|---|---|
| Availability | Share of scheduled monitor runs (`.github/workflows/monitor.yml`, every 30 min = 1,440 checks/30 days) where `/api/health` answers 200 | ≥ 99% | ≤ 14 failed checks ≈ 7.2 h | 100% of checks run so far |
| Move delivery | Time for a submitted move to reach the opponent's screen | 95% within 2 s | 5% of moves | ≤ 0.12 s (live smoke) |
| API latency (proxy) | Warm `/api/health` response time in the monitor | ≤ 2 s per check | counts as an availability failure | ~0.1 s |

## Measurement notes

- Availability: count failed `monitor` runs in GitHub → Actions → monitor (filter by status) over the last 30 days. Alert threshold (any failed run) sits well below SLO breach (15 failed runs), leaving time to fix.
- Move delivery is not measured continuously (no client telemetry is collected, by design: no tracking). It is checked by the live smoke procedure after deployments; `tests/test_nfr_integration.py` keeps a p95 < 1 s regression locally and in CI.
- Review monthly; tighten to 99.5% / 1 s once a month of data shows headroom.
