# Unit Test Instructions — u2-data-and-your-games

## Framework
- **Python:** pytest, using the existing fixtures in `tests/core/conftest.py` (temporary database, FastAPI TestClient). Run it through `uv run --frozen`.
- **JS:** Node's built-in `node:test`. The test files are `tests/js/*.test.mjs`.
- **Browser:** headless Chromium, using the CDP helpers from `tests/test_game_screen.py`. The browser test skips with a reason when Chromium is missing.

## Commands for this unit only
```bash
uv run --frozen pytest -q tests/core/test_db.py tests/core/test_rooms.py tests/core/test_games.py tests/core/test_summaries.py tests/test_notifications.py tests/test_u2_your_games_browser.py
node --test tests/js/your-games.test.mjs tests/js/seat-store.test.mjs
```

The project-wide check stays `uv run --frozen pytest -q`.

## Scope (Standard strategy)

| Component | File | Tests |
|---|---|---|
| db.py schema v4 | tests/core/test_db.py | 8 |
| rooms.py modes | tests/core/test_rooms.py | 2 new |
| games.py capture info | tests/core/test_games.py | 5 new |
| summaries route | tests/core/test_summaries.py | 10 |
| your-games.js | tests/js/your-games.test.mjs | 8 |
| seat-store.js | tests/js/seat-store.test.mjs | 2 new |
| Lobby list (browser) | tests/test_u2_your_games_browser.py | 1 |

## Mocking and test data
- **Databases:** always `tmp_path`. For the old-version files, the tests write small SQLite files at version 2 or 3 (the schema version row only) and a non-SQLite garbage file.
- **Join requests:** pending rows are inserted directly, since U3 builds their lifecycle.
- **Log checks:** use pytest's `caplog` to assert that no submitted token appears in the logs.
- **JS:** summaries are plain objects. `now` is passed in, so time-based tests are deterministic.

## Coverage
The refactor scope sets no coverage floor. Every new public function has tests, and the existing suite must stay green.
