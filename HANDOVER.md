# JustChess — Handover and Remaining Work

Last updated: 2026-11-15. Keep this file limited to outstanding work; remove completed to-dos.

## Current checkpoint

Active intent: `261115-compact-player-footer`. Owner approved Code Generation for the authorized Vercel extension VFR1–VFR6 (f59f2390, approval recorded as 6aeffd02). Preserve the completed footer. Intent state: `aidlc/spaces/default/intents/261115-compact-player-footer/aidlc-state.md`; implementation and test artifacts are under `construction/code-generation/` and `construction/build-and-test/`.

Build and Test ran the frozen dependency check, full JavaScript suite, real Chromium footer/accessibility checks and the implementation regression. Evidence is **446 passed, 1 optional external Web Push skip** over 447 unique Python cases and **226 Node tests**, including isolated PostgreSQL 17 multi-instance coordination/outbox checks. Exact regression commands and limits are in `construction/code-generation/code-summary.md`; current stage matrix/results are in `construction/build-and-test/`. Traceability passes all 13 requirement IDs. Two Preview-only checks remain Unverified: deployed startup/Stockfish/assets and Preview smoke; Deployment Execution is scheduled to own them. Since that regression, the owner requested that Stockfish be downloaded and checksum-verified during the Vercel build, then bundled. The uncommitted implementation adds `prepare_vercel_stockfish.py`; Vercel's `installCommand` runs it after `uv sync`, packages the Linux x86_64 binary plus its GPLv3 license/source pointer, and makes startup prefer the bundled executable over `/tmp` download. This change has not been tested or deployed; the old dry-run listing predates it. Next work should verify the install/build/package and then smoke the Preview. No code test was run for this follow-on edit.

The owner answered **Accept failure** to Build and Test question `95ea8b39` (message `be05da5e`), and the answer was recorded. The attempted lifecycle report using `--result failed` was rejected because `failed` is not a supported outcome. Workflow state therefore still shows Build and Test in progress; no stage approval or advancement has been recorded. On resumption, run `aidlc engine orchestrate next` and follow the exact action it returns. Do not repeat the completed regression checks unless new code changes.

Disposable test service `justchess-vercel-verification` (postgres:17 tmpfs localhost55439) was stopped/removed after verification. Dedicated URL was `postgresql://postgres@127.0.0.1:55439/justchess_test`; each PG case created/dropped only its unique schema. Verification commands (recreate a disposable service before running PG):

- `env JUSTCHESS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/justchess_test uv run --frozen pytest -q tests/test_serverless.py tests/core tests/test_computer.py tests/test_notifications.py tests/test_push_api.py tests/test_postgres.py`
- `uv run --frozen pytest -q tests/test_accessibility_browser.py tests/test_game_screen.py tests/test_player_identity_browser.py`
- `uv run --frozen pytest -q tests/test_analysis.py tests/test_check_move_api.py tests/test_curate_puzzles.py tests/test_endgame_judge.py tests/test_endgames.py tests/test_endgames_content.py tests/test_envfile.py tests/test_frontend_js.py tests/test_gameplay.py tests/test_lessons.py tests/test_lessons_api.py tests/test_player_api.py tests/test_players.py tests/test_push_e2e.py tests/test_puzzles.py tests/test_puzzles_api.py tests/test_rate_limit.py`

## Deployment still pending

Vercel target is team `sachavandewalle-6312s-projects`, project `just-chess`, GitHub `optio/JustChess`. Owner requested a single production branch: Vercel `productionBranch` is now `main`; GitHub remote branch `production` was deleted. Future commits/merges pushed to `main` trigger Vercel Production deployments. This setting change did not itself deploy the already-pushed current `main` commit; no manual Production deployment was triggered in this step. Preview deployment remains authorized as part of the active intent.

Root securely synchronized DATABASE_URL, JUSTCHESS_VAPID_PRIVATE_KEY and generated CRON_SECRET into Preview+Production as Secrets. Local ignored .env remains chmod0600; do not display/read it for testing. Existing VAPID public identity was preserved. Direct non-pooled Neon URL is confirmed by owner. Preview and Production currently share that database/key: do not perform destructive Preview tests. The earlier dry source run succeeded with FastAPI145 files/~2.14MB, but it predates the bundled Stockfish build step; check the final function bundle size and contents after the build change. `prepare_vercel_stockfish.py` targets the Vercel default x86_64 architecture, packages the pinned checksum-verified binary and GPLv3 license/source pointer under `.vercel-stockfish/linux-x86_64/`, and `vercel.json` explicitly includes that directory. That directory is generated during build and excluded from source upload/git. No build or Preview deployment has yet confirmed the generated files are retained in the function package.

Actual Preview smoke must establish template/static/training bundling, FastAPI lifespan, bundled Stockfish startup/execution without a runtime download, WebSockets/reconnect, real Neon events and cron unauthorized response. Also verify the `/tmp` fallback only when the bundled engine is absent. No local check substitutes for that smoke. Vercel supports FastAPI ASGI WebSockets with Fluid Compute on all plans; each socket owns one direct PG listener connection and function max duration closes it. Budget Neon connections. Daily03:17UTC cron is eventual retry/cleanup, not a promise of prompt delivery without traffic. Remote send interruption has unavoidable at-least-once ambiguity; stable notification tags coalesce it. These limits are documented in README.

## Preserved completed footer evidence

Compact responsive footer, readonly nickname/pencil and inline save/edit states, draft/pending/error handling, one Copy player link action/manual bookmark fallback, styled help/regeneration dialogs and accessible keyboard/focus/touch controls are complete. Nine masked screenshots under the current record's `construction/code-generation/screenshots/` were visually inspected at320/375/1280 and dark375. Original final regression425 passed/8 skipped, Node226; do not rebuild completed UI.

## Outstanding manual/optional work

- Check closed-tab Web Push on a real phone; external Web Push E2E needs explicit browser credentials and normally skips. Reuse existing VAPID key; private values stay in ignored env or environment secrets.
- Owner may choose another cburnett license attribution: source lists CC BY-SA3.0 and GPLv2+; current UI shows CC BY-SA3.0. References: `static/ASSETS.md` and piece license.
- Minor existing follow-ups: cleanup lapses requests without broadcasting (page countdown hides banner); malformed trusted-proxy headers share the proxy rate window; join-request status polling has no rate cap; endgame disconnect-specific test absent (shared cancellation helper covered); engine/endgame limits precede some body/404 checks.
- Existing python-chess asyncio policy and websockets legacy deprecations remain.

## Standing rules and pointers

Run Python through `uv run --frozen`. Tests use temporary databases and never normal data. Do not reset external PostgreSQL schemas; auxiliary runtime tables are additive. Credentials never appear in server URLs/logs/error bodies. No commit/push unless owner requests. No Production deployment. Gameplay settings live in gameplay.yaml.

Player identity/polish and PostgreSQL support were completed/pushed through `dea733e`; records `261115-player-identity-polish` and `261114-postgresql-support`. Current CodeKB: `aidlc/spaces/default/codekb/JustChess/`. App configuration and runtime limits: README.md. Keep this checkpoint current after every milestone/result so another AI tool can resume without overlapping finished work.
