# Alarms — JustChess

## Sources

- Owner answer Q2 = GitHub scheduled check (message 082d61ed); Q3 = `/api/health`; `slo-config.md`.

| Alarm | Signal | Threshold | Severity | Routing |
|---|---|---|---|---|
| Production down | `monitor` step "Health" | `/api/health` not 200 twice, 20 s apart | P1 | GitHub email on failed scheduled run → owner |
| Database or engine degraded | `/api/health` body `database: down` / `engine: unavailable` (HTTP 503) | any | P1 (database) / P2 (engine: friend games still work) | same email; body is printed in the run log |
| Slow responses | `monitor` step "Latency" | warm `/api/health` > 2 s | P2 | same email |
| Broken page or open cron | `monitor` step "Homepage and cron protection" | homepage not 200 or missing content, or cron not 401 | P1 (cron open is a security issue) | same email |
| CI red on `main` | `tests` workflow | any failure | P2 (blocks Production promotion once Deployment Checks are on) | GitHub email |

## Escalation

Single owner (repository and Vercel project owner); no on-call rota. On an alert: open the failed run's log, then follow `../deployment-pipeline/rollback-runbook.md` if a recent deploy is the cause, or `log-queries.md` to diagnose.

## Setup

- Commit `.github/workflows/monitor.yml` (scheduled `7,37 * * * *`, plus manual "Run workflow").
- Ensure GitHub → Settings → Notifications → Actions has email on failed workflows enabled (default: notify for workflows you triggered or whose schedule you last edited).
- GitHub pauses scheduled workflows after 60 days of repository inactivity: re-enable under Actions → monitor.
