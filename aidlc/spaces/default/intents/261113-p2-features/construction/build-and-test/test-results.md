# Test Results — JustChess P2 (2026-11-14, Raspberry Pi)

## Build
No compile step. `uv sync --frozen` is already satisfied. The app imports and starts inside every server-backed test.
**Status: success.**

## Unit-scoped commands (each distinct command run once)

| Unit | Command | Result | Exit |
|---|---|---|---|
| U1 | `node --test tests/js/captures.test.mjs tests/js/layout.test.mjs tests/js/share.test.mjs tests/js/qr.test.mjs` | 29 passed, 0 failed | 0 |
| U1 | `uv run --frozen pytest -q tests/test_u1_polish_browser.py` | 7 passed | 0 (no failures reported) |
| U2 | `uv run --frozen pytest -q tests/core/test_db.py tests/core/test_rooms.py tests/core/test_games.py tests/core/test_summaries.py tests/test_notifications.py tests/test_u2_your_games_browser.py` | 88 passed | 0 (no failures reported) |
| U2 | `node --test tests/js/your-games.test.mjs tests/js/seat-store.test.mjs` | 15 passed | 0 |
| U3 | `uv run --frozen pytest -q tests/core/test_pass_along.py … tests/test_u3_pass_along_browser.py` | 73 passed | 0 (no failures reported) |
| U3 | `node --test tests/js/pass-along.test.mjs tests/js/room-flow.test.mjs` | 19 passed | 0 |
| U4 | `uv run --frozen pytest -q tests/core/test_computer_rooms.py … tests/test_u4_computer_browser.py` | 64 passed | 0 |
| U4 | `node --test tests/js/computer.test.mjs tests/js/computer-panel.test.mjs` | 14 passed | 0 |
| U5 | `uv run --frozen pytest -q tests/test_lessons.py … tests/test_u5_trainer_browser.py` | 65 passed | 0 |
| U5 | `node --test tests/js/hub-tabs.test.mjs tests/js/trainer-progress.test.mjs tests/js/puzzle-state.test.mjs tests/js/trainer-state.test.mjs` | 30 passed | 0 |
| U6 | `uv run --frozen pytest -q tests/test_endgames_content.py … tests/test_u6_endgame_browser.py` | 56 passed | 0 |
| U6 | `node --test tests/js/endgame.test.mjs tests/js/endgame-tab.test.mjs` | 11 passed | 0 |

The first three Python commands were run in zsh, where the pipe exit status was not captured. Their output shows only passes and no failure or error lines.

## Project-wide runs

| Command | Result | Exit |
|---|---|---|
| `uv run --frozen pytest -q` | 386 passed, 1 skipped, 3 warnings (deprecations in python-chess and websockets) | 0 |
| `node --test tests/js/` | 221 passed, 0 failed, 0 skipped | 0 |

**The skip** is `tests/test_push_e2e.py`. This Chromium cannot subscribe to a push service, so the push delivery end-to-end check cannot run here. The push API and payload logic are covered by `tests/test_push_api.py` and `tests/test_notifications.py`. This skip predates P2.

## Browser evidence
All browser tests run in **headless Chromium** (a real browser engine), driven over CDP against a live Uvicorn server: U1 polish, U2 Your games, U3 pass-along, U4 computer game, U5 trainer and U6 endgame. None of the browser evidence comes from Node or a DOM emulator.

## NFR1 timing sample (in-stage check)
I ran 20 consecutive Maximum-level replies with the real Stockfish sf_19 on the Pi, through `justchess.engine.Engine`:
- p50 1.002 s
- p95 1.004 s
- max 1.062 s

The target is 3 s or less at p95. `tests/test_engine_real.py` also checks a single reply in under 3 s.

## Coverage
No coverage floor applies. The refactor scope sets none, and the Testing Contract has no coverage obligation. No coverage tool is configured.

## Failures
None.
