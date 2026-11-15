# Player Identity and Game Polish — Code Summary

## Implemented

Anonymous players now receive an automatically persisted session, a private reusable recovery bookmark and an optional nickname. The footer exposes save/copy/regenerate controls and a plain-language private-link warning. Restoring on another device replaces its active identity and saved seats, preserving the original device's authority. Regenerating recovery invalidates old bookmarks without revoking sessions.

Selected pieces retain their highlight and grow without changing squares or hit targets. Online/computer results say You won!/You lost and name the opponent when available, retaining colour/reason information. Winners receive finite confetti only on a newly observed finish; draws/watchers/pass-along/reopened results remain neutral or suppress confetti. Reduced motion suppresses confetti; navigation cancellation removes it.

## Files and Design

- justchess/db.py: schema version 5 adds players, hashed player sessions and optional seat ownership. SQLite retains archive/recreate behavior. PostgreSQL initializes empty schemas and refuses incompatible occupied/versioned schemas unchanged; use a new/recreated app database rather than dropping unrelated tables.
- justchess/players.py: profile creation/read, separate hashed recovery/session credentials, regeneration, authorized seat attachment and English nickname validation. A player session can authorize only seats associated with its player. Original room tokens continue working; no plaintext recovery or room token needs server-side storage. A maximum of 100 sessions/player bounds recovery accumulation; at most 50 recent seats are returned.
- justchess/api.py: bounded origin-protected player action endpoints, rate limiting, no-store responses and nickname snapshot broadcasts.
- justchess/rooms.py and summaries.py: recognize authorized player sessions for linked room seats and summaries. A room-specific continue transfer detaches the prior player ownership; private player recovery does not transfer the seat away.
- static/js/player-identity.js: resilient local credential storage, fragment/body-only recovery, explicit identity replacement, private footer controls, focus-time profile refresh. Restoring is explicit; invalid recovery keeps the current identity and shows a useful error.
- static/js/api.js and app.js: attach newly obtained seats, restore local game entries and initialize identity before room/lobby routing; accepted join-request seats are linked as well.
- templates/index.html and static/css/app.css: footer and accessible 44px link/control targets; confetti presentation.
- static/css/board.css: independent CSS scale for selected stationary pieces, avoiding movement animation transforms.
- static/js/view-model.js and screens/win-sequence.js: personalized outcome copy and bounded/cancellable winner-only confetti.
- gameplay.yaml, justchess/gameplay.py and static/js/gameplay.js: selected size, confetti duration and player-request rate configuration.
- README.md and HANDOVER.md: current behavior, reset policy, link security, moderation limits and pending checkpoint.

No account service, external moderation API, dependency installation, multi-worker support or legacy data migration was added. No real database or .env file was opened or reset by implementation tools. No commit, push or deployment occurred.

## Requirement and Test Mapping

| IDs | Verification |
|---|---|
| FR1 | tests/test_player_identity_browser.py measures selected piece scale and deselection; existing keyboard/browser checks remain green |
| FR2–FR4 | tests/test_players.py and tests/test_player_api.py exercise unique identities, hashed secrets, authorized linked seats, both devices, stale moves, bookmark regeneration and session continuity; Chromium restores nickname/game access and verifies old-link rejection |
| FR5 | model/API cases cover case/Unicode/simple obfuscations, invalid input, retained previous name and innocent substring names; Chromium checks nickname persistence and named outcomes |
| FR6–FR7 | updated view-model/computer expectations and Chromium check named win/loss, bounded winner-only confetti, reopened finished game and reduced-motion suppression |
| NFR1 | API tests cover forged credentials, foreign origin, body limits, rate limits and non-echoed sentinel; Node verifies fragment/body-only secret transport and replacement semantics |
| NFR2 | real PostgreSQL identity/domain parity, isolated SQLite and full regression suites; real Chromium feature/accessibility checks |

## Validation

- Baseline before application edits: `uv run --frozen pytest -q` — 399 passed, 7 skipped, 187.70s; `node --test tests/js/` — 221 passed.
- First identity model run: 17 passed. Targeted schema/model/API/existing game-browser run: 51 passed.
- Real PostgreSQL 17 + identity/model/API targeted command: `env JUSTCHESS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/justchess_test uv run --frozen pytest -q tests/test_postgres.py tests/test_players.py tests/test_player_api.py` — 40 passed, 7.37s.
- New real Chromium feature run: 3 passed, 19.70s. Final feature/accessibility rerun after footer fix: `uv run --frozen pytest -q tests/test_player_identity_browser.py tests/test_accessibility_browser.py` — 4 passed, 24.16s.
- Full first pass found a real footer-link touch-target regression and an old computer-result text expectation. Link target fixed to 44px; intentional expectation changed to You lost, with resignation reason still in subtitle. Targeted accessibility/computer rerun: 2 passed. Core suite: 138 passed.
- Final full command: `env JUSTCHESS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/justchess_test uv run --frozen pytest -q` — **429 passed, 1 skipped**, 212.51s. PostgreSQL cases executed; only existing real push E2E skipped.
- Final Node suite: **224 passed**.
- Implementation-scoped git diff --check passed.

The PostgreSQL service used the already available postgres:17 Docker image, loopback port 55439 and tmpfs data; test fixtures created and removed dedicated schemas. Container was stopped/automatically removed afterward. No production configuration or database was a test input.

## Limits

The local English filter is intentionally bounded and cannot detect every abusive nickname. Existing signed-in devices remain valid when a bookmark is regenerated; this is recovery-link revocation, not a sign-out-all-devices feature. Other devices may retain an outdated cached bookmark until requesting a replacement. Only recent 50 room seats are restored; ordinary room expiry still applies. Real external Web Push E2E remains skipped. Existing python-chess/websockets deprecation warnings remain. Remote-database latency and production monitoring/deployment were not claimed or performed.
