# Deployment Execution Questions

## Evidence

Pre-deployment state (2026-11-15): commit `a5e2ccf` is live as Production deployment `just-chess-h1hnczub1` (Ready), aliased to https://justchess.mijnesite.be and https://just-chess.vercel.app. Read-only checks on both: `/` 200 with the new header and "Loading JustChess…", `/api/engine` `available:true` (`path_source:"env"`), `/api/cron/maintenance` without secret 401, `/static/js/busy.js` 200. No schema migration: schema version 5 unchanged; the additive runtime table `room_stand_ins` is created at startup. Build and Test: 465 passed / 1 optional skip, Node 230/230. Neon CLI is not installed; Vercel CLI 65.16.0 and GitHub CLI are authenticated.

## Q1 — Live browser smoke on Production

A. Yes: two-player move exchange plus computer stand-in takeover on the live site (two throwaway rooms in the Production database, removed by daily cleanup).
B. No: rely on the read-only checks.
X. Other (please specify)

[Answer]: A. Yes, run it (message 0f73dfc4).

## Q2 — Push the CI workflow

A. Commit and push `.github/workflows/tests.yml` and the deployment docs to `main`, then watch the first CI run (redeploys the same app code).
B. Not yet.
X. Other (please specify)

[Answer]: A. Yes, push it (message 0f73dfc4).

## Q3 — Neon Preview branch

A. Owner creates a `preview` branch in the Neon console and sets the Preview-scoped `DATABASE_URL` with `vercel env add DATABASE_URL preview` at a hidden prompt; the assistant verifies presence without reading the value.
B. Later: Preview stays on the shared database.
X. Other (please specify)

[Answer]: A. Owner does it with guidance (message 0f73dfc4).
