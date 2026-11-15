# Health Check Report — Production

## Sources

- `curl` against https://justchess.mijnesite.be and https://just-chess.vercel.app; `vercel inspect`, `vercel project inspect`; `../deployment-pipeline/deployment-strategy.md` health checks.

| Check | Expected | Result |
|---|---|---|
| `GET /` | 200, lobby shell with new header | 200, "Loading JustChess…" and `topbar-player` present (both domains) |
| `GET /api/engine` | `available: true` | `{"available":true,"path_source":"env"}` (bundled Stockfish) |
| `GET /api/cron/maintenance` without secret | 401 | 401 |
| `GET /static/js/busy.js` | 200 | 200 |
| Function region | next to Neon (eu-central-1) | `x-vercel-id: cdg1::fra1::…` after `ad09526` (was `iad1`) |
| `GET /api/rooms/{code}` latency | well under 1 s | ~0.11 s ×5 (was 2.8–6.5 s) |
| CI gate | `tests` green on `main` | Run 43756215588 success (464 passed / 3 skipped; Node 230/230) |

Cold start: the first page load in a fresh run once took over 30 s before the lobby appeared; later loads ~2 s for player creation. Not re-measured after the region move.
