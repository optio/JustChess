# Unit Test Instructions — u4-play-the-computer

## Framework
- **Python:** pytest, using the fixtures in `tests/core/conftest.py` (temporary database, TestClient). Run with `uv run --frozen`.
- **Fake engine:** `tests/fakes/fake_uci.py`, started through the engine factory injected into `create_app` (or straight into `Engine` in the engine tests). Its flags make it answer, delay, crash, hang or return an illegal move.
- **Real engine:** `tests/test_engine_real.py` uses the Stockfish found by `stockfish_install.resolve_existing` and skips with a reason when there is none.
- **JS:** `node:test`.
- **Browser:** headless Chromium through the CDP helpers in `tests/test_game_screen.py`, with the fake engine. It skips with a reason when Chromium is missing.

## Commands for this unit only
```bash
uv run --frozen pytest -q tests/core/test_computer_rooms.py tests/core/test_takeback.py tests/core/test_computer_draws.py tests/test_engine.py tests/test_computer.py tests/test_engine_real.py tests/core/test_computer_api.py tests/core/test_reply_race.py tests/test_engine_rate_limit.py tests/test_u4_computer_browser.py
node --test tests/js/computer.test.mjs tests/js/computer-panel.test.mjs
```

The project-wide check stays `uv run --frozen pytest -q`.

**Runner check (Step 2, 2026-11-14):** `uv run --frozen pytest -q tests/core/test_rooms.py` ran 11 passed, and `node --test tests/js/room-flow.test.mjs` ran 12 passed (Node v24.6.0). Both runners work as configured, so the unit commands above are used unchanged. Baseline before any U4 change: `uv run --frozen pytest -q` gave 276 passed, 1 skipped.

## Scope (Standard strategy)

| Component | File | Tests |
|---|---|---|
| Computer rooms | tests/core/test_computer_rooms.py | 8 |
| Takeback | tests/core/test_takeback.py | 7 |
| Automatic draws and resign | tests/core/test_computer_draws.py | 5 |
| Engine queue and health | tests/test_engine.py | 8 |
| Levels and coordinator | tests/test_computer.py | 6 |
| Real Stockfish (NFR1 timing) | tests/test_engine_real.py | 2 (skipped without Stockfish) |
| Computer HTTP flows | tests/core/test_computer_api.py | 8 |
| Reply race | tests/core/test_reply_race.py | 6 |
| Engine route limits | tests/test_engine_rate_limit.py | 3 |
| computer.js | tests/js/computer.test.mjs | 8 |
| Lobby panel | tests/js/computer-panel.test.mjs | 4 |
| Short game (browser) | tests/test_u4_computer_browser.py | 1 |

## Mocking and test data
- **Time:** a fake clock is used for the backoff and the rate windows. The engine timeout tests use short think times (0.05 s) and a short configurable grace, so no test waits seconds.
- **Races:** the fake engine's delay flag holds a reply in flight while the test takes back, resigns or starts a rematch. Each test then waits for the coordinator's task to finish before asserting.
- **Random colour:** an injected chooser makes it deterministic.
- **Logs:** `caplog` asserts that no token appears in any log line.

## Coverage
The refactor scope sets no coverage floor. Every new function has tests, and the existing suite must stay green.
