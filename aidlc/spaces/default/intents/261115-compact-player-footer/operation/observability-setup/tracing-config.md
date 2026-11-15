# Tracing Configuration — JustChess

## Sources

- Vercel response header `x-vercel-id` (observed `cdg1::fra1::…`); application architecture in README.md.

No distributed tracing (X-Ray/OpenTelemetry) is instrumented: one FastAPI function plus one database, so a trace would add little over request logs, and adding an exporter means a third-party account and data sharing that the owner has not chosen.

What correlates a request today:

- `x-vercel-id` on every response identifies the edge and function region and the request in Vercel's logs.
- Room codes in log lines tie together a room's HTTP requests, socket events and engine replies.

Revisit if Production grows beyond one function or when debugging cross-instance socket delivery (the "away" race in `../deployment-execution/smoke-test-results.md`): adding the `x-vercel-id` and a per-socket id to `justchess.live` log lines would be the first step.
