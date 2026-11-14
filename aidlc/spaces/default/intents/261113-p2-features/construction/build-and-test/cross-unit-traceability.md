# Cross-Unit Traceability — JustChess P2

**Source:** `aidlc engine sensor-traceability --stage build-and-test` (2026-11-14).

**Verdict: PASS for every functional requirement.** All 45 FR IDs are built by at least one Unit.

The sensor lists the NFRs as uncovered, because no Unit traceability file carried NFR IDs: the per-unit functional designs traced FRs only. Each NFR is shown below with the Unit that delivers it and its test evidence. They are also verified in the Target Verification Matrix in `build-and-test-summary.md`.

## Functional requirements

| ID | Built in |
|---|---|
| FR1.1 | U2 static/js/your-games.js |
| FR1.2 | U2 justchess/summaries.py |
| FR1.3 | U2 static/js/screens/lobby.js |
| FR1.4 | U2 justchess/summaries.py |
| FR1.5 | U4 static/js/screens/lobby.js |
| FR2.1 | U1 static/js/board/board.js; U2 justchess/games.py |
| FR2.2 | U1 static/js/board/board.js |
| FR2.3 | U1 tests/test_u1_polish_browser.py |
| FR3.1 | U3 justchess/rooms.py |
| FR3.2 | U3 justchess/games.py |
| FR3.3 | U3 justchess/api.py |
| FR3.4 | U3 justchess/notifications.py |
| FR3.5 | U3 justchess/rooms.py |
| FR3.6 | U3 static/js/pass-along.js |
| FR3.7 | U3 tests/core/test_join_requests.py |
| FR3.8 | U3 justchess/games.py |
| FR3.9 | U3 tests/core/test_pass_along.py |
| FR4.1 | U1 static/css/app.css |
| FR4.2 | U1 static/js/layout.js |
| FR4.3 | U1 static/css/app.css |
| FR5.1 | U1 static/js/share-dialog.js |
| FR5.2 | U1 static/js/share-dialog.js |
| FR5.3 | U1 static/js/share.js |
| FR5.4 | U1 static/js/qr-canvas.js |
| FR5.5 | U1 static/js/share-dialog.js |
| FR6.1 | U4 static/js/screens/lobby.js |
| FR6.2 | U4 justchess/computer.py |
| FR6.3 | U4 justchess/games.py |
| FR6.4 | U4 justchess/api.py |
| FR6.5 | U4 justchess/rooms.py |
| FR6.6 | U4 tests/test_u4_computer_browser.py |
| FR6.7 | U4 justchess/engine.py; U6 tests/core/test_endgames_api.py |
| FR6.8 | U4 justchess/games.py |
| FR6.9 | U4 tests/core/test_computer_rooms.py |
| FR7.1 | U5 lessons/ruy-lopez.yaml (and the other opening files) |
| FR7.2 | U5 lessons/legals-mate.yaml (and the other trap files) |
| FR7.3 | U5 tests/test_lessons.py |
| FR8.1 | U5 static/js/training/hub.js; U6 static/js/training/endgame-state.js |
| FR8.2 | U6 justchess/endgames.py |
| FR8.3 | U5 justchess/puzzles.py |
| FR8.4 | U5 lessons/scholars-mate-defence.yaml (and the other defence files) |
| FR8.5 | U5 static/js/training/trainer-progress.js |
| FR8.6 | U5 puzzles/LICENSE.md |
| FR9.1 | U3 .env.example (and envfile.py, built before construction) |
| FR9.2 | U3 tests/test_envfile.py |

## Non-functional requirements (not in Unit traceability; verified here)

| ID | Delivered by | Evidence |
|---|---|---|
| NFR1 | U4 justchess/engine.py; U6 endgame refusal threshold | tests/test_engine.py (one search at a time, FIFO, cap, restart, overrun); tests/test_engine_real.py; 20-reply sample: p95 1.004 s |
| NFR2 | U1 static/js/board/board.js (260 ms) | tests/test_u1_polish_browser.py capture and reduced-motion tests (Chromium) |
| NFR3 | U1 static/js/layout.js, app.css | tests/test_u1_polish_browser.py::test_board_fits_the_viewport_at_the_fr41_sizes (Chromium) |
| NFR4 | U2 summaries, U3 rooms, api and ratelimit, U1 share, U5 loaders | tests/core/test_join_requests_api.py (no token in logs, creator-only answers, 429); tests/test_rate_limit.py; tests/js/share.test.mjs; tests/test_puzzles.py and tests/test_lessons.py (bad file skipped and logged) |
| NFR5 | U1 share dialog; tap targets in U1 and U4 | tests/test_u1_polish_browser.py share-dialog focus and Escape; tap-target checks in tests/test_u1_polish_browser.py and tests/test_u4_computer_browser.py (Chromium) |
| NFR6 | U5 puzzles/ | `du -sh puzzles` = 296 KB, well under 5 MB; nothing is downloaded for trainers at start-up (tests/test_puzzles.py loads from disk) |
| NFR7 | U2 justchess/db.py | tests/core/test_db.py (older versions moved to .old; fresh schema v4; tests use temporary databases only) |
| NFR8 | all Units | full suite 386 passed, 1 skipped (pre-existing); every FR has at least one automated test (table above) |

## Uncovered elements
None among the FRs. The NFR rows are a traceability-format gap and not a delivery gap: the Unit designs traced FRs only. They are raised at the approval gate.
