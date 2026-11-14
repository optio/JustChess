# Unit Test Instructions — u4-blunder-warnings

## Test framework setup and configuration

- **Python:** pytest with FastAPI's TestClient. It uses the core conftest fixtures (temporary database, Stockfish patched out).
- **JavaScript:** Node's built-in test runner, loaded through `tests/js/index.js`.
- **Optional browser run:** the existing headless Chromium harness. It skips, with a reason, when Chromium is missing.

## How to run this unit's tests

From the project root:

```bash
uv run --frozen pytest tests/test_analysis.py tests/test_check_move_api.py -q
node --test tests/js/
```

The whole suite, which is the command the unit checkpoint runs:

```bash
uv run --frozen pytest -q
```

## Tests (Standard strategy: 5–8 per component, plus key boundaries)

| File | Component | Count | Covers |
|---|---|---|---|
| `tests/test_analysis.py` | Analysis | 8–14 | mate allowed; back-rank mate; hanging knight and queen; even trade; defended but losing; already hanging; every move allows mate; mate dropped but hanging still reported; existing threat; mover in check; priority; most valuable piece; pinned defender; promotion offset; castling and en passant; mating move |
| `tests/test_check_move_api.py` | Route | 8 + timing | clean, mate, hanging; 403 token and turn; 409 version with snapshot; 400 illegal; 409 game over; foreign origin; version unchanged; timing ≤ 300 ms for a busy middlegame and for "every move allows mate" |
| `tests/js/blunder.test.mjs` | Hook and text | 8–10 | text for 3 warning shapes; setting off; no warning; confirm and cancel; timeout and network go ahead; 409 snapshot; 403 message; malformed 200; thrown settings read |
| `tests/js/room-flow.test.mjs` (extended) | Widened contract | +3 | object result shows the message, applies the snapshot, and refuses the board move |
| `tests/test_game_screen.py` (extended) | Integration | +1–2 | new imports resolve; optional browser run of the dialog |

All existing tests must stay green.

## Expected coverage targets

The refactor scope sets no coverage floor. The Standard strategy's test volume per component is met.

## Mocking and stubbing guidance

- **Analysis:** tested directly on `chess.Board(fen)`. No mocks.
- **Timing tests:** use `time.perf_counter`, with each sample taken over 5 runs. They assert on the median and on the maximum, so one Pi stall cannot fail the test spuriously while the budget is still enforced.
- **Hook tests:** the `api` (fetch), `settings` and `openDialog` are fakes, and the timers are injected.

## Test data management

Positions are FEN strings written in the test files, with a short comment saying what each one shows.
