# Deployment Planning Questions

## Evidence

Target: https://vercel.com/sachavandewalle-6312s-projects/just-chess. Owner has configured Neon DATABASE_URL locally. Vercel integration was suggested but remains unconfirmed; CLI is absent. No credential values have been accessed.

justchess/api.py Services has process-local asyncio room locks and LiveHub; live.py holds sockets per process. Engine worker, startup engine preparation and hourly cleanup use long-lived asyncio tasks. Vercel supports FastAPI/WebSockets but automatically scales instances and has bounded function lifetimes. Shared Neon persistence alone does not share room coordination, live sockets or engine tasks.

Sources: https://vercel.com/docs/frameworks/backend/fastapi ; https://vercel.com/docs/functions/concurrency-scaling ; https://vercel.com/docs/functions/limitations . These establish runtime constraints; the incompatibility assessment is an inference from this app's inspected source.

## Q1 — Deployment architecture

A. Vercel frontend with an always-on single-worker Python backend elsewhere (smallest change to retain current runtime behavior; needs another backend host).
B. Adapt the full backend for Vercel: shared coordination/live fan-out and durable/request-bound engine work (larger implementation before reliable full deployment).
C. Deploy a limited preview first, clearly identifying unsupported live/engine behavior; not a verified multiplayer release.
X. Other (please specify)

[Answer]: B. Adapt the entire FastAPI app for Vercel, including UI/API in that app; no separately hosted backend. Owner corrected earlier option 1 to option 2 (94b972b3). Store push/private-key secrets in environment variables rather than persistent PEM files; download verified Stockfish on startup when missing. Existing JUSTCHESS_VAPID_PRIVATE_KEY and startup installer already supply these mechanisms, but Vercel needs writable ephemeral engine storage and shared/durable coordination. No secrets have been read or moved.

## Q2 — Vercel access

Deployment constraints added by owner (2205fa7c): avoid polling wherever possible; browser/system Web Push notifications must keep working, including closed-page notifications. Prefer event-driven live transport; don't silently replace WebSockets with regular polling or drop background notification delivery. Evaluate direct Neon LISTEN/NOTIFY (pooled URL cannot LISTEN; reconnect must resync authoritative state), or a managed realtime facility after explicit choice. Keep transactional notification outbox and bounded send/retry design; do not promise continuous autonomous delivery on Hobby with no durable execution service. Architecture/adaptation plan is still not implemented.

A. Add the suggested Vercel integration so project configuration/deployments can be inspected through authorized tools.
B. Use an authenticated Vercel CLI on this machine (not currently installed/authenticated in this shell).
X. Other (please specify)

[Answer]: B. Owner installed/authenticated CLI (dfde4adc); verified Vercel CLI65.16.0, signed-in user and exact project. Per authorized secret-sync request, DATABASE_URL and JUSTCHESS_VAPID_PRIVATE_KEY from ignored .env were saved as Secret variables for Preview and Production through stdin without printing values. No deployment performed. Integration is unnecessary for this access path. Both scopes currently use same values as requested; isolate preview DB during deployment preparation if desired.

Neon credentials must be configured privately in Vercel for the chosen Preview/Production environments. Never paste secrets into chat. A separate Neon preview branch/database is needed to isolate preview from production; determine setup after architecture/access choice. Initial deployment should be Preview with smoke checks before Production promotion. Do not reset Neon without explicit scoped authorization.

## Q3 — Test gate before Production

Context (2026-11-15): Vercel `productionBranch` is `main`; every push to `main` deploys Production at once. Tests run only locally; the repository has no CI.

A. Keep as is: push to main deploys at once; tests stay a manual step before pushing.
B. Add a CI test gate: a GitHub Actions workflow runs the Python and JavaScript tests, and Production is deployed only after they pass.
C. Manual promotion: every push makes a Preview; the owner promotes to Production by hand.
X. Other (please specify)

[Answer]: B. Add CI test gate (message ea5c001c).

## Q4 — Preview database isolation

Context: Preview and Production share the same Neon DATABASE_URL and VAPID key, so Preview checks touch Production data.

A. Separate Neon branch for Preview, with Preview's DATABASE_URL pointing at it.
B. Keep shared; only non-destructive checks on Preview.
X. Other (please specify)

[Answer]: A. Separate Neon branch (message ea5c001c).
