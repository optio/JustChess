# Test Results — Build and Test (P1 redesign)

## Run 1 — 2026-11-13T11:34Z (before loop-back 1)

### Build

There is no compile step: the backend runs from source with `uv`, and the frontend uses native ES modules. `uv sync --frozen` is satisfied by the lock file, and the app imports cleanly. All tests import it through `justchess.api.create_app`.

### Unit and integration tests

| Command | Result |
|---|---|
| `uv run --frozen pytest -q` (the whole Python suite; this covers every unit's command and runs the Node suite through `tests/test_frontend_js.py`) | **1 failed, 176 passed, 1 skipped** |
| `node --test tests/js/` | **130 passed, 0 failed** |

The per-unit commands are all subsets of the whole-suite run, so each was counted once:
- `uv run --frozen pytest tests/core -q`
- `node --test tests/js/`
- `uv run --frozen pytest tests/test_game_screen.py tests/core -q`
- `uv run --frozen pytest tests/test_lessons.py tests/test_lessons_api.py -q`
- `uv run --frozen pytest tests/test_analysis.py tests/test_check_move_api.py -q`
- `uv run --frozen pytest tests/test_notifications.py tests/test_push_api.py tests/core/test_db.py -q`

### New Build and Test checks (added at this stage)

| File | Engine | Result |
|---|---|---|
| `tests/test_nfr_integration.py` | Real uvicorn server, real threads and sockets | **3 passed**. Concurrent joins seat exactly one Black: 8 joiners × 5 rounds, each round 1×200 and 7×409, never a 500. Concurrent moves on one version apply exactly one: 4 moves × 5 rounds, each round 1×200 and 3×409, each 409 carrying a snapshot. Opponent delivery on the host over 40 moves: **median 18.4 ms, p95 22.7 ms, max 47.4 ms** |
| `tests/test_accessibility_browser.py` | Headless Chromium, 390 × 844 phone viewport | **1 failed**. Touch targets under 44 × 44 px: all 64 board squares are **42.5 × 42.5 px**, and the top-bar `home-link` is **124 × 28 px** (28 × 28 in the lobby). The square labels and keyboard play were not reached, because the touch-target assertion failed first. |
| `tests/test_push_e2e.py` | Headless Chromium against a real push service, with a VAPID key generated in `tmp_path` | **Skipped**: `AbortError: Registration failed - permission denied`. This Chromium build (Debian `/usr/bin/chromium`, headless) cannot subscribe to a push service, even with notification permission granted and network access to `fcm.googleapis.com`. |

### Failure details

`tests/test_accessibility_browser.py::test_touch_targets_labels_and_keyboard_play_at_phone_width`:
- `AssertionError`: the game screen lists 65 targets under 44 px: board squares a1–h8 at 42.5 × 42.5, and `home-link` at 124.3 × 28.
- The lobby lists `home-link` at 28 × 28.

### Coverage

No coverage floor applies. The refactor scope sets none, and no team or project rule adds one.

## Run 2 — 2026-11-13T12:18Z (after loop-back 1)

| Command | Result |
|---|---|
| `uv run --frozen pytest -q` (whole suite, run once; it contains every unit's command and the Node suite) | **177 passed, 1 skipped**, exit 0 |
| `node --test tests/js/` | **130 passed, 0 failed** |
| `tests/test_accessibility_browser.py` (Chromium, 390 × 844) | **passed**. Squares 46 × 46 px (44.25 px with frame labels); `home-link` 44 × 44; 64 square labels; keyboard Enter and arrows play e2–e4 |
| `tests/test_nfr_integration.py` | **3 passed**. Delivery p95 about 23 ms |
| `tests/test_push_e2e.py` | **skipped**: `AbortError: Registration failed - permission denied` (this Chromium build has no usable push service) |
| Private-key scan (`grep -rIl -e "BEGIN EC PRIVATE KEY" -e "BEGIN PRIVATE KEY"`, excluding .venv, .git, aidlc and .claude) | no matches |

Verdicts: see the Target Verification Matrix in `build-and-test-summary.md`. Every target is Met or N/A except **NFR3-PUSH, which is Unverified**. The failure ladder applies: the root cause is the test environment's browser, not the generated code. An in-stage fix would need a browser with a push service, which means installing a package the plan does not name, so the person is asked.

### Accepted failure (2026-11-13)

The person chose **Accept failure** for NFR3-PUSH (live Web Push on localhost), which stays **Unverified**. They will run the push check themselves on a desktop browser that has a push service, following the steps in `build-instructions.md`.

## Loop-Back Log

### Loop-back 1 — 2026-11-13T11:34:26Z

- **Diagnosis:** NFR6 (touch targets of at least 44 × 44 px) and the accessibility checklist's "smallest square 46 px on 374 px boards" are not met at 390 px phone width.
  - The game grid leaves the board frame 374 px wide, but the frame keeps its desktop padding, so each square is (374 − 34) / 8 = 42.5 px.
  - The top-bar logo link `home-link` is 28 px tall.
  - Both are styling choices in the game screen.
- **Root-cause stage:** Code Generation for **u3-game-screen**. The game layout and top-bar styles live in `static/css/app.css`. The board frame padding comes from U2's `board.css`, but U3 owns the phone layout that sizes it.
- **Planned fix:**
  - In `static/css/app.css`, below 768 px, reduce the game board frame's padding to 3 px (inside-label mode) so the squares are at least 46 px on a 390 px screen. Frame-label mode must still keep squares of at least 44 px and the whole frame at 374 px or wider.
  - Give `home-link` a minimum hit area of 44 × 44 px, using padding with the visual mark unchanged.
  - Keep `tests/test_accessibility_browser.py` as the check. Extend U3's layout test so it asserts square size of at least 44 px (inside labels: 46 px or more) at 390 px.
- **Estimated impact:**
  - Effort: small, about 20 lines of CSS plus 2 test assertions, in one unit.
  - Financial cost: none.
  - Risk: low. Visual only, with no logic change, and the existing layout and browser tests guard the board size.

## Target Verification Matrix (run 1)

See `build-and-test-summary.md`. NFR6 is **Not Met** in run 1 and NFR3 (push on localhost) is **Unverified**. Everything else is Met.
