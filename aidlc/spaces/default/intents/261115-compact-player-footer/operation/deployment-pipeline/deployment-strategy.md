# Deployment Strategy — JustChess

## Sources

- `deployment-pipeline-questions.md` Q1–Q4 (owner answers), HANDOVER.md (Deployment, Vercel limits), `cd-config.md`.

## Strategy

**Atomic immutable deployments with gated promotion.** Each Vercel deployment is an immutable build; Production switches by moving the domain alias in one step, so there are no partial rollouts. Blue/green and canary traffic splitting are not used: the app is small, has one Production environment, and Vercel Hobby offers no weighted routing. The previous deployment stays available for an instant alias rollback (`rollback-runbook.md`).

## Environment promotion

| Stage | Trigger | Data | Gate to next |
|---|---|---|---|
| Local | Developer runs the suites | Temporary SQLite / disposable PostgreSQL | Tests green before pushing |
| Preview | Push to any non-`main` branch | Neon `preview` branch (Q4) | CI `tests` green; Preview smoke for risky changes |
| Production | Push / merge to `main` | Neon production branch | CI `tests` green (Deployment Checks) → alias moves |

No separate staging environment: Preview with an isolated database fills that role.

## Approvals

- Production promotion is automatic once `tests` passes; the owner's approval is pushing or merging to `main` (owner chose one production branch and an automated test gate instead of manual promotion, Q3).
- Force Promote past a failing check, and any external configuration change (Neon branches, Vercel env vars, deployment settings), needs the owner's explicit request.

## Feature flags

No feature-flag service (CloudWatch Evidently / AppConfig are not in this stack). Runtime tuning lives in `gameplay.yaml`, deployed with the code. Risky features ship dark only by keeping them on a branch until Preview verification passes.

## Health check and smoke after a Production deploy

- `GET /` returns 200 and the lobby shell.
- `GET /api/engine` returns `available: true` (bundled Stockfish).
- `GET /api/cron/maintenance` without the secret returns 401.
- Create a room, open it in a second browser, play one move each (WebSocket delivery).
- Abort condition: any of these fails → roll back (`rollback-runbook.md`).

## Database changes

Schema stays at version 5. New runtime tables (e.g. `room_stand_ins`) are additive `CREATE TABLE IF NOT EXISTS`, created at startup under an advisory lock, so a rollback to an older build leaves them unused and harmless. Never reset or drop external PostgreSQL schemas.

## Security implications

CI uses no secrets and a throwaway database; Production secrets stay in Vercel. Isolating Preview data (Q4) removes the risk of Preview tests writing Production rows. Force Promote is the one bypass of the gate and is reserved for emergencies.
