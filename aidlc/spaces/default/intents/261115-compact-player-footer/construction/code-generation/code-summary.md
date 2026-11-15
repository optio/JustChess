# Compact Player Footer — Code Summary

## Implementation

Frontend-only changes in templates/index.html, static/js/player-identity.js and static/css/app.css replace the larger form/action block with a subtle separated footer. Saved nicknames display as text plus a pencil; empty/edit mode has an inline checkmark. Editing focuses/selects the input, Enter saves, failures preserve the draft and saved profile, pending saves prevent duplicate requests, and profile refresh does not erase a draft.

Copy player link is the single primary recovery action. Clipboard failure opens a styled help dialog with a selectable private field and Bookmark my player link. A compact ? control opens the same help, explaining account-free identity, cross-device games, privacy, regeneration and why the cleaned ordinary address is not the bookmark. New link opens a styled confirmation dialog, retaining current session semantics, explicit cancel/confirm, pending protection and readable errors. Native window.confirm is removed. Dialogs use the existing share-dialog design, native modal inertness plus explicit focus cycling/Escape/backdrop handling and trigger focus return.

Backend, schema, dependency, player credential/session/recovery APIs and game behavior are unchanged. No production data/configuration was accessed. No commit, push or deployment occurred.

## Traceability

| ID | Implementation / verification |
|---|---|
| FR1 | Responsive footer CSS; browser width checks and screenshots at 320/375/1280 plus dark375 |
| FR2 | createNicknameEditor and footer wiring; two new Node state tests and real-browser display/edit/clear/validation/draft/Enter/pending checks |
| FR3 | Copy action and manual/bookmark dialog fallback; actual Chromium denied-clipboard selection and preserved cross-device restoration |
| FR4 | Styled regeneration confirmation; actual cancel/Escape/backdrop/focus/pending/error/success checks, existing old-link rejection flow |
| FR5 | ? help modal; help content, keyboard focus containment, Escape/Close/return-focus checks |
| NFR1 | Existing 44px touch-target check, keyboard game/browser checks; unchanged identity APIs and recovery transport tests |
| NFR2 | HANDOVER updated after baseline, implementation, findings and each meaningful verification checkpoint |

## Verification

- Baseline Python: 421 passed, 8 skipped, 1 pre-existing lesson-trainer navigation/log failure (207.24s), before app edits. Unchanged isolated retry passed (1 test, 6.33s).
- Baseline Node: 224 passed.
- Focused Node editor/identity: 5 passed. Final full Node: 226 passed.
- Existing feature/accessibility browser command: 4 passed (21.62s).
- Three new detailed footer Chromium scenarios: 3 passed (10.96s).
- Saved-name/regeneration screenshot rerun: 2 passed (7.31s).
- Browser findings resolved: return focus immediately rather than relying only on native dialog's queued close event; Enter harness now sends the actual carriage-return key text.
- Two longer attempts ended with unexplained external SIGTERM (143), including a final monolithic regression at approximately 66% without assertion failures. These interrupted runs are not counted as passes. Root and developer issued no process-group cleanup/termination.

Final regression completed in five disjoint explicit file batches covering all 433 cases in 50 files, without weakening selection: **425 passed, 8 skipped**. Seven skips are optional PostgreSQL cases with no dedicated URL (backend unchanged); one is existing real external Web Push E2E. No final batch failed. The Node suite separately passed all **226** tests; its pytest bridge is already included in the Python total, so those counts are not added together.

| Batch | Result |
|---|---|
| 1 — tests/core/ (15 files) | 136 passed, 47.96s |
| 2 — main game/identity/accessibility browser (3 files) | 17 passed, 54.46s |
| 3 — U1–U6 browser files (6 files) | 13 passed, 59.42s |
| 4 — engine/NFR/installer (5 files) | 27 passed, 14.79s |
| 5 — remaining nonbrowser cases (21 files) | 232 passed, 8 skipped, 46.68s |

## Collection Verification

Collection-only validation confirmed 433 total tests; the five batches partition all 50 files. The collection command needed approved uv-cache access; its approval delayed progress, not a running/stalled test.

## Exact Final Regression Commands

### Batch 1

`uv run --frozen pytest -q tests/core/test_api.py tests/core/test_computer_api.py tests/core/test_computer_draws.py tests/core/test_computer_rooms.py tests/core/test_db.py tests/core/test_endgames_api.py tests/core/test_games.py tests/core/test_join_requests.py tests/core/test_join_requests_api.py tests/core/test_live.py tests/core/test_pass_along.py tests/core/test_reply_race.py tests/core/test_rooms.py tests/core/test_summaries.py tests/core/test_takeback.py`

### Batch 2

`uv run --frozen pytest -q tests/test_accessibility_browser.py tests/test_game_screen.py tests/test_player_identity_browser.py`

### Batch 3

`uv run --frozen pytest -q tests/test_u1_polish_browser.py tests/test_u2_your_games_browser.py tests/test_u3_pass_along_browser.py tests/test_u4_computer_browser.py tests/test_u5_trainer_browser.py tests/test_u6_endgame_browser.py`

### Batch 4

`uv run --frozen pytest -q tests/test_engine.py tests/test_engine_rate_limit.py tests/test_engine_real.py tests/test_nfr_integration.py tests/test_stockfish_install.py`

### Batch 5

`uv run --frozen pytest -q tests/test_analysis.py tests/test_check_move_api.py tests/test_computer.py tests/test_curate_puzzles.py tests/test_endgame_judge.py tests/test_endgames.py tests/test_endgames_content.py tests/test_envfile.py tests/test_frontend_js.py tests/test_gameplay.py tests/test_lessons.py tests/test_lessons_api.py tests/test_notifications.py tests/test_player_api.py tests/test_players.py tests/test_postgres.py tests/test_push_api.py tests/test_push_e2e.py tests/test_puzzles.py tests/test_puzzles_api.py tests/test_rate_limit.py`

## Visual Review

Credential-masked screenshots in screenshots/: footer/help at 320, 375 and 1280px; dark footer at 375px; saved-name desktop and regeneration desktop. Visually inspected representative narrow, desktop, dark, saved-name and modal images: compact hierarchy, aligned/wrapped controls, readable help, no overflow. Screenshots use isolated test identities, and the private URL field is replaced with a review placeholder before capture. The test server intentionally disables Stockfish; its unavailable-engine notice in the background is fixture state.

## Limits

Existing optional PostgreSQL cases skip without the dedicated test URL; no new PostgreSQL run was performed for unchanged backend code. Existing real external Web Push E2E remains optional. The monolithic full-suite attempt was externally interrupted, so the complete disjoint batches above are the final evidence. Existing python-chess/websockets deprecations remain. No numerical coverage target was changed. Implementation-scoped git diff --check passed. All plan steps are complete; Code Generation approval is the next human checkpoint.

## Authorized Vercel Extension (f59f2390)

The earlier sections are the preserved footer checkpoint. This extension supersedes their backend-unchanged and next-stage statements. V1–V6 code work is complete; actual Preview deployment and smoke verification remain root's later deployment-stage responsibility.

### Changes and decisions

- `justchess/db.py`: add coordination/outbox tables with CREATE IF NOT EXISTS over schema5, retaining existing rooms/profiles/subscriptions. Existing unsupported-version refusal remains. SQL transaction advisory room locks serialize independent instances. Room invalidations are NOTIFY'd inside the state transaction; payloads contain only room codes and channels are schema-isolated hashes.
- `justchess/coordination.py`, `live.py`: each WebSocket owns an async direct-PG listener which closes/cancels with the socket. Listener reconnect establishes LISTEN before authoritative resync. Shared expiring presence updates on hello/ping/visibility and removes on leave; abandoned rows expire. Broadcast revalidates credentials so a transferred seat on another instance loses its old privilege. PostgreSQL shared fixed-window rate caps and hashed-address join-decline cooldowns preserve cross-instance behavior; SQLite retains local sliding windows/one-worker behavior.
- `justchess/work.py`, `api.py`: Vercel replies are awaited within the request (30s bound), guarded by durable60s game/version leases and SQL/version revalidation. Interrupted ownership expires and can retry; stale results cannot commit after a resign/rematch. Existing hint and trainer work already awaits bounded searches. Startup awaits verified engine preparation on Vercel; no autonomous housekeeping loop is started there. Local behavior remains asynchronous.
- `justchess/outbox.py`: game actions enqueue atomically; joins/join requests also enqueue in their mutation. Initial post-response ASGI work attempts the intended event directly. Durable jobs retain failed sends, attempts, availability and expiring ownership. Each endpoint has an acknowledgement to avoid known-success replay. Obsolete turn jobs coalesce and relevance is rechecked before sending. Concurrent direct/global dispatch claims cannot send the same healthy lease twice. Global maintenance processes at most2 jobs/25s, endpoint timeout3s, max5 attempts, retains terminal failures. Turn jobs expire after5m; end jobs after1h. Remote-acceptance interruption retains unavoidable at-least-once ambiguity, mitigated by stable notification tags.
- `/api/cron/maintenance`: constant-time Bearer CRON_SECRET verification, bounded global drain, request lapse, at-most20-room cleanup and expired coordination cleanup. `vercel.json` schedules daily03:17UTC, FastAPI preset, uv frozen runtime dependencies,300s max duration and explicit static/templates/training includes. `.vercelignore` excludes .env, databases, engine downloads, framework/test/runtime/tool configuration and key files.
- `app.py`: Vercel ignores local .env, requires DATABASE_URL without SQLite fallback, and resolves engine storage beneath temporary writable storage. Existing pinned Stockfish SHA256 validation/extraction remains unchanged. README/.env.example document secrets/configuration and runtime bounds; no dependencies added.

### Extension verification

Baseline before backend edits: `uv run --frozen pytest -q tests/core tests/test_computer.py tests/test_notifications.py` **181 passed47.94s**; full Node **226 passed**. An earlier command referenced nonexistent tests/test_live.py and ran no tests, then was corrected. Prior approved full footer Build/Test baseline425 passed/8 skips was preserved.

Real PostgreSQL17 ran in disposable tmpfs container `justchess-vercel-verification`, localhost55439; every PG test creates/drops only a unique schema via dedicated JUSTCHESS_TEST_DATABASE_URL. Existing PG20 cases passed3.04s before expanded verification. Final full regression covers all447 unique cases: **446 passed,1 skipped** (external real Web Push E2E only). The original five-batch complete-suite approach was retained to avoid the earlier external monolithic termination; no assertions were weakened.

| Disjoint final batch | Result |
|---|---|
| A — core + computer + notifications + push + PG + first11 serverless tests |223 passed71.55s|
| B — remaining nonbrowser files |163 passed,1 skipped46.40s|
| C — main game/identity/accessibility Chromium |17 passed61.58s|
| D — U1–U6 Chromium |13 passed63.34s|
| E — engine/NFR/installer |27 passed20.44s|
| Additional3 serverless cases added after A |Two pass within13-case focused run13.09s; final failure-backoff regression passes in narrow2-case run2.22s (one overlap)|

Focused `tests/test_serverless.py`:13 passed13.09s, followed by `-k 'serverless_computer_reply or serverless_failed_reply'`:2 passed/12 deselected2.22s after adding the final durable-backoff regression. The file now collects14 cases. Covers real PG two app instances/conflicting same-version moves, cross-instance event delivery/shared presence/reconnect/cleanup, duplicate engine reply and other-instance resign race, abandoned engine claim retry, shared rate/decline limits, SQLite+PG notification partial-success/retry/expired-lease/freshness, concurrent dispatch, coalescing, cron auth and Vercel temp-engine/no-env/no-fallback entrypoint. Final review preserved shared failure cooldown through the durable lease and maps bounded-await timeout to a friendly retry response, rather than an unhandled500. Existing installer cases verify pinned checksum extraction into temporary test storage; real installed Stockfish engine tests passed. Push API crash expectation intentionally changes from never-retry claimed to failed diagnostics plus durable pending attempt; the request remains successful.

Exact batch A: `env JUSTCHESS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/justchess_test uv run --frozen pytest -q tests/test_serverless.py tests/core tests/test_computer.py tests/test_notifications.py tests/test_push_api.py tests/test_postgres.py`

Exact batch B: `uv run --frozen pytest -q tests/test_analysis.py tests/test_check_move_api.py tests/test_curate_puzzles.py tests/test_endgame_judge.py tests/test_endgames.py tests/test_endgames_content.py tests/test_envfile.py tests/test_frontend_js.py tests/test_gameplay.py tests/test_lessons.py tests/test_lessons_api.py tests/test_player_api.py tests/test_players.py tests/test_push_e2e.py tests/test_puzzles.py tests/test_puzzles_api.py tests/test_rate_limit.py`

Exact batches C/D/E are the original Batch2/3/4 commands above. Final focused: `env JUSTCHESS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/justchess_test uv run --frozen pytest -q tests/test_serverless.py`. Disposable PostgreSQL container was stopped/removed after verification. `uv sync --frozen --check` would make no changes; final `git diff --check` passed. The pytest Node bridge passes226 cases and is included in Python totals; separate Node226 passed before edits. Existing deprecation warnings remain.

### External status and remaining limits

Root reports remote productionBranch=production with optio/JustChess retained, and CRON_SECRET safely synchronized alongside existing DATABASE_URL/VAPID Secret values for Preview+Production. Worker performed no remote mutation/deploy, no .env/normal database reads/reset and no commits/push. Root source dry-run confirmed FastAPI bundle145files/~2.14MB before final additional tool-config/key excludes. Repeat upload inspection before actual Preview.

VFR6 is partial until Preview URL/smoke exists. VFR1 local implementation is verified; remote writable Stockfish download/execution, lifespan/static/training/WebSocket behavior must be proven on Preview. [Current Vercel docs](https://vercel.com/docs/functions/websockets) support native FastAPI ASGI WebSockets on all plans with Fluid Compute; sockets end at function duration and reconnect to authoritative state. One direct listener connection per socket limits Neon concurrency. Engine queues/hint flags remain local; durable game state is protected by claims/SQL/version validation. Daily cron provides eventual retry, not prompt delivery without traffic. Real phone closed-tab delivery remains manual. No claim of verified Preview or Production deployment is made.
