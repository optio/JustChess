# Unit Test Instructions — u6-training

## Test framework setup and configuration

- **Python:** pytest with FastAPI's TestClient. The loader tests use `tmp_path` lesson folders passed through `JUSTCHESS_LESSONS_DIR`. The shipped `lessons/` folder is read only by the test that checks it.
- **JavaScript:** Node's built-in test runner, through U2's `tests/js/index.js` loader.
- **Browser run (optional):** the same headless Chromium harness as U3. It is skipped, with the reason, when Chromium is missing.

## How to run this unit's tests

From the project root:

```bash
uv run --frozen pytest tests/test_lessons.py tests/test_lessons_api.py -q
node --test tests/js/
```

The whole suite, which is the unit checkpoint command:

```bash
uv run --frozen pytest -q
```

## Tests (Standard strategy: 5–8 per component, plus key boundaries)

| File | Component | Count | Covers |
|---|---|---|---|
| `tests/test_lessons.py` | loader | 8 | shipped lessons load and replay; missing field; illegal SAN; SAN and UCI disagree; duplicate id; oversized file and symlink; JSON and YAML; reload when a file is added |
| `tests/test_lessons_api.py` | routes | 8 | list shape and order; detail shape with the old keys gone; 404 for malformed and unknown ids; position move legal, illegal, invalid FEN, bad uci, promotion and checkmate outcome; foreign origin |
| `tests/js/trainer-state.test.mjs` | trainer reducer | 8–12 | walkthrough limits; correct, illegal and off-line judging; misses and arrow; trainer replies; side switch; free play in and out; completion; Other-lessons exits; timers cancelled |
| `tests/js/arrow.test.mjs` | arrow geometry | 3 | white orientation; black orientation; knight move |
| `tests/js/board-rejected-tap.test.mjs` | U2 board addition | 6 | fires on an empty or enemy non-target; never on deselect, Escape, reselecting another own piece, while not interactive or while pending |
| `tests/js/room-flow.test.mjs` | carried U3 flows | 7 | stale-seat notice; 409 full; continue redeem and its 403; seat 403 leading to watching; move refused with 400 and with 409 plus snapshot; beforeMove throwing |
| `tests/js/contrast.test.mjs` (extended) | tokens | +1 | arrow against all six squares in both themes, at 3:1 or more |
| `tests/test_game_screen.py` (extended) | integration | +2 | `/learn` shell and its imports; optional browser run of the lesson |

All existing tests must stay green.

## Expected coverage targets

The refactor scope sets no coverage floor. The Standard strategy's volume is met per component.

## Mocking and stubbing guidance

- **Lesson folder:** `JUSTCHESS_LESSONS_DIR` points at `tmp_path`.
- **Trainer reducer:** timers, `fetch` and the board are injected. The reducer only emits effects.
- **Room flow:** the api, storage and live clients are fakes.

## Test data management

Lesson fixtures are short YAML or JSON strings written into `tmp_path` by each test. The shipped lesson files are not changed by any test.
