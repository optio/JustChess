# Rollback Runbook — JustChess on Vercel

## Sources

- `deployment-strategy.md`, `cd-config.md`; Vercel CLI 65.16.0 authenticated on the owner's machine (`deployment-pipeline-questions.md` Q2).

## When to roll back

Any post-deploy smoke check fails (`deployment-strategy.md`), error rate visibly rises in Vercel logs, players report broken games, or the engine reports unavailable after a deploy that worked before.

## Escalation

Owner: the repository and Vercel project owner (only maintainer). There is no on-call rota; incidents are handled by the owner, with an AI session assisting on request.

## Steps (instant alias rollback, ~1 minute)

1. List recent Production deployments: `vercel ls just-chess --prod` (or Vercel dashboard → Deployments).
2. Pick the last known-good deployment URL.
3. Roll back: `vercel rollback <deployment-url>` (dashboard: the deployment's menu → "Instant Rollback"). The Production alias moves back at once; no rebuild.
4. Verify: `GET /` 200, `GET /api/engine` available, one two-browser move.
5. Note: after an Instant Rollback Vercel stops auto-assigning new `main` deployments to Production until one is promoted again. Fix forward on `main`, let `tests` pass, then promote the fixed deployment (`vercel promote <url>` or dashboard "Promote").
6. Record what happened and the fix in HANDOVER.md.

## Code-level fix forward

`git revert <bad commit>` on `main` and push: CI runs, and the reverted build is promoted when `tests` passes.

## Data considerations

- Schema version is unchanged by app deploys; additive runtime tables stay and are ignored by older builds, so no database rollback is needed.
- Never restore or reset the Neon database as part of an app rollback. If data was damaged, use Neon's point-in-time restore into a new branch, inspect it, and switch `DATABASE_URL` only with the owner's explicit decision.

## Reversing the pipeline changes from this stage

- CI gate: remove the `tests` entry under Settings → Deployment Checks (deploys then promote without waiting) and/or delete `.github/workflows/tests.yml`.
- Fallback CLI deploy (if adopted): remove `git.deploymentEnabled` from `vercel.json` and the workflow's `deploy` job; revoke `VERCEL_TOKEN`.
- Preview database: point Preview's `DATABASE_URL` back to the shared URL and delete the Neon `preview` branch.
