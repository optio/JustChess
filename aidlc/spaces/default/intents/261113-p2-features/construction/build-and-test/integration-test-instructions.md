# Integration Test Instructions — JustChess P2

## Framework
- **pytest with FastAPI's TestClient** against a temporary database (`tests/core/conftest.py`). No test opens the real `justchess.sqlite3`.
- **A fake UCI engine** (`tests/fakes/fake_uci.py`) is injected through `create_app` for every engine path, apart from `tests/test_engine_real.py`.
- **Headless Chromium through CDP** (`tests/test_game_screen.py` helpers), against a live Uvicorn server, for the end-to-end checks. These run in a real browser engine.

## Cross-unit boundaries and where they are tested

| Boundary | Units | Tests |
|---|---|---|
| Schema v4 columns used by pass-along, computer rooms and summaries | U2 → U3, U4 | tests/core/test_db.py, test_pass_along.py, test_computer_rooms.py, test_summaries.py |
| Your games list shows friend, pass-along and computer rooms | U2 ↔ U3, U4 | tests/test_u2_your_games_browser.py, tests/js/your-games.test.mjs |
| Join-request rate limiter reused by the engine routes | U3 → U4, U6 | tests/test_rate_limit.py, tests/test_engine_rate_limit.py, tests/core/test_endgames_api.py |
| One Engine queue shared by replies, hints and endgame defence (refusal thresholds) | U4 ↔ U6 | tests/test_engine.py, tests/core/test_computer_api.py, tests/core/test_endgames_api.py |
| Shared engine wait helper (hint and endgame) | U4 ↔ U6 | tests/core/test_computer_api.py (unchanged hint behaviour), tests/core/test_endgames_api.py |
| gameplay.yaml read by rooms, engine, endgames and the client | U4 → all | tests/test_gameplay.py |
| Trainer hub tab registry hosting the Endgames tab | U5 → U6 | tests/js/hub-tabs.test.mjs, tests/js/endgame-tab.test.mjs, tests/test_u5_trainer_browser.py |
| Capture animation and board layout on every game screen, including computer games | U1 → U3, U4 | tests/test_u1_polish_browser.py, tests/test_u4_computer_browser.py |

## How to run
```bash
uv run --frozen pytest -q tests/core                      # domain and HTTP integration
uv run --frozen pytest -q -k browser                      # the real-browser end-to-end checks
uv run --frozen pytest -q                                  # everything
```

## Coverage expectations
The refactor scope has no coverage floor. At Standard strategy each component has 5 to 8 tests, and the key boundaries above have integration tests. The existing suite must stay green.

## Test data
- Each test creates its own rooms in a temporary database.
- Endgame tests can pass their own folder to `create_app`.
- The rate-limit and wait-limit tests use low limits set in a test gameplay file, or a fake clock.
