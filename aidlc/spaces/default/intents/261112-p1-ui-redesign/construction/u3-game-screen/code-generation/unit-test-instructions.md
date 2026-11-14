# Unit Test Instructions — u3-game-screen

## Test framework setup and configuration

- **JavaScript:** Node's built-in test runner, as in U2. `tests/js/index.js` loads every `*.test.mjs` file. There is no npm install.
- **Python:** pytest, with FastAPI's TestClient. `tests/test_frontend_js.py` from U2 already runs the Node suite inside pytest.
- **Browser run (optional):** headless Chromium, if it is present on the machine, driven from Python. The test starts uvicorn on a free port with a temporary `JUSTCHESS_DB` and skips with a stated reason when Chromium is missing.

## How to run this unit's tests

From the project root:

```bash
node --test tests/js/
uv run --frozen pytest tests/test_game_screen.py tests/core -q
```

The whole suite, which is the recorded unit checkpoint command:

```bash
uv run --frozen pytest -q
```

## Tests (Standard strategy: 5–8 per component, plus key boundaries)

| File | Component | Count | Covers |
|---|---|---|---|
| `tests/js/view-model.test.mjs` | view model | 8 | status order; claim visibility; scoresheet and newest move; result glyphs; score across a colour swap; end titles and fallback; rematch states; announcement |
| `tests/js/screen-state.test.mjs` | screen reducer | 8 | lobby, joining and the results of joining; reconnecting as a flag in each view; a snapshot after a gap (finished game, new game); seat-moved from every room view, including joining; a seat 403 leading to watching; a new game during the sequence; notFound back to the lobby |
| `tests/js/api.test.mjs` | API client | 6 | 200; 409 with a snapshot; 400 and 403; network failure; header on state reads; no token in URLs |
| `tests/js/live.test.mjs` | live client | 6 | backoff schedule; hello with and without a token; pings; visibility; seat-moved; older snapshots ignored |
| `tests/js/seat-store.test.mjs` | seat store | 5 | storage that throws; set, get and remove; key format; fragment parsing, valid and invalid |
| `tests/js/share.test.mjs` | share | 3 | share sheet; clipboard; field fallback |
| `tests/js/contrast.test.mjs` (extended) | tokens | +3 | labels under the last-move highlight on 3 boards, at 4.5:1 or more |
| `tests/test_game_screen.py` | integration | 6–7 | shell routes; every referenced asset and import resolves; old client files gone; HTTP flow snapshot has `claimableDrawReason` and no legacy fields; optional two-player browser game |
| `tests/core/test_games.py` (extended) | Games | +2 | `claimableDrawReason` for threefold, 50-move and null |

All existing tests must stay green. U1 tests that read the legacy fields are updated to read the new fields.

## Expected coverage targets

The refactor scope sets no coverage floor. Test volume follows the Standard strategy.

## Mocking and stubbing guidance

- `fetch`, `WebSocket`, timers, `navigator` and `storage` are all injected into the pure modules. Tests pass fakes.
- The pytest flow uses TestClient with a temporary database and Stockfish patched to a no-op, as in U1's conftest.

## Test data management

- Snapshots in the Node tests are small object literals built by a helper in each test file.
- The browser run creates its own room, and its database is thrown away afterwards.
