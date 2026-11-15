# Dashboards — JustChess

## Sources

- Vercel Hobby project `sachavandewalle-6312s-projects/just-chess`; GitHub repository `optio/JustChess`; `alarms.md`.

No custom dashboard service is used (Hobby plan, no CloudWatch). The views:

| View | Where | Shows |
|---|---|---|
| Uptime history | GitHub → Actions → monitor | One row per 30-minute check, red/green; each log prints health body and response time |
| Build health | GitHub → Actions → tests | CI results per push |
| Requests and errors | Vercel → just-chess → Observability (and Logs) | Function invocations, error rate, duration, region; available retention is limited on Hobby |
| Deployments | Vercel → Deployments, or `vercel ls just-chess` | What is live; rollback targets |
| Database | Neon console → project → Monitoring | Connections, compute activity (watch connection counts: each live socket holds one LISTEN connection, each instance up to 4 idle pooled ones) |

Golden signals mapping: latency (monitor response time, Vercel duration), traffic (Vercel invocations), errors (Vercel 5xx, monitor failures), saturation (Neon connections, Vercel function duration near the 300 s cap for sockets).
