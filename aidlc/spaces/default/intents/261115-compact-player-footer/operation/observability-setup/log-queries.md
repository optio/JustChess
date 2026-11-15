# Log Queries — JustChess

## Sources

- Vercel CLI 65.16.0 (authenticated); `justchess/` logger names (`justchess.api`, `justchess.live`, `justchess.db`, `justchess.coordination`, …); `alarms.md`.

Logs never contain tokens, connection URLs or driver diagnostics (by design); room codes appear.

| Purpose | Command / filter |
|---|---|
| Live tail of Production | `vercel logs https://justchess.mijnesite.be --scope sachavandewalle-6312s-projects` |
| Errors only | Vercel → Logs → Level: Error (or filter the tail for `ERROR` / `Traceback`) |
| Database trouble | filter for `Database error`, `PostgreSQL operation failed`, `Health check: the database did not answer` |
| Live-socket listener drops | filter for `Room listener interrupted; reconnecting` |
| Engine | filter for `computer's reply`, `engine queue is full`, `Discarded a stale computer reply` |
| Push notifications | filter for `Web Push`, `Alert` |
| One room | filter for the 6-character room code |

Retention: Vercel Hobby keeps runtime logs only briefly; copy anything needed for an incident into HANDOVER.md or the incident notes right away. Log drains to a retained store need a paid plan (not configured).
