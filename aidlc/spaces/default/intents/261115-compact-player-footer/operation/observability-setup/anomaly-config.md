# Anomaly Detection — JustChess

## Sources

- `slo-config.md`, `alarms.md`.

No statistical anomaly detection (CloudWatch anomaly bands are not available on this stack). Fixed thresholds stand in for it:

- Response time above 2 s on a warm health request (the move-delivery SLO threshold) fails the monitor.
- Any 503 from `/api/health` fails the monitor, naming the degraded part.
- Manual monthly review: failed monitor runs vs the 14-run error budget, Neon connection peaks, Vercel error rate. If failures cluster at certain hours, consider a cold-start warm-up or a tighter retry.
