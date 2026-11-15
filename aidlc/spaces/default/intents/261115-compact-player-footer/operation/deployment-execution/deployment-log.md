# Deployment Log — 2026-11-15

## Sources

- `deployment-execution-questions.md` (owner answers 0f73dfc4, 91587ab6), `../deployment-pipeline/cd-config.md`, `../deployment-pipeline/deployment-strategy.md`, Vercel CLI 65.16.0, GitHub CLI, live checks against https://justchess.mijnesite.be.

## Timeline (CET)

| Time | Event |
|---|---|
| 19:54 | `a5e2ccf` (UI follow-ups, computer stand-in, battery lesson) deployed to Production as `just-chess-h1hnczub1` (Ready, 28 s build), aliases justchess.mijnesite.be, just-chess.vercel.app. |
| ~20:30 | Read-only checks green (see `health-check-report.md`). Owner approved a live browser smoke (Q1). |
| ~20:35 | Live smoke: functionally green, but move delivery 13.6 s / 4.8 s, engine reply 11 s, room read 2.8–6.5 s. Diagnosed: function in `iad1`, Neon in `aws eu-central-1`, and a new TLS PostgreSQL connection per database step. |
| ~20:45 | Owner chose "Fix it now" (91587ab6). Neon region read from the local host name only (no credentials shown). |
| ~21:05 | `ad09526` pushed: `vercel.json` `regions: ["fra1"]`; `Database` reuses idle healthy PostgreSQL connections (max 4 idle, ≤ 30 s idle); schema name cached for notification channels; CI workflow `.github/workflows/tests.yml`. Local: 466 passed / 1 skip on PostgreSQL 17, Node 230/230. |
| 21:07–21:10 | First GitHub Actions run `43756215588` (job `tests`): success in 3 m 30 s — Python 464 passed / 3 skipped, Node 230/230. |
| ~21:08 | `ad09526` deployed to Production as `just-chess-90rq56pzu` (Ready, 33 s), served from `fra1`. |
| ~21:15 | Re-measured: room read ~0.11 s; live smoke green: move delivery ≤ 0.12 s, engine reply ~0.22 s, stand-in takeover works. |

## Database migrations

None. Schema version 5 unchanged; the additive runtime table `room_stand_ins` was created automatically at startup (`CREATE TABLE IF NOT EXISTS`).

## Rollback

Not needed. Previous good deployments: `just-chess-h1hnczub1` (`a5e2ccf`), `just-chess-1gl7gjgqq`. Procedure: `../deployment-pipeline/rollback-runbook.md`.

## Pending owner actions

1. Vercel → Settings → Deployment Checks → Add Checks → GitHub → `tests` (or the documented CLI fallback if the Hobby plan doesn't offer it).
2. Neon console → create branch `preview` from production; then run `vercel env add DATABASE_URL preview` and paste its direct (non-pooled) URL at the hidden prompt, replacing the shared value (`vercel env rm DATABASE_URL preview` first). Then a Preview deployment can be smoke-tested safely.
