# Code Summary — u6-endgame-trainer

All 12 plan steps are done. The build covered steps 1 to 11 and the README part of step 12. This summary, `source-manifest.json` and `traceability.json` complete step 12.

## Files

**Created**
- `justchess/endgames.py`: the catalog loader and the judge.
  - The loader reads the four fixed category files and validates each position. A bad position is skipped with a warning. A missing folder marks the trainer not installed.
  - `judge` decides mate, promote and draw goals, including a defender checkmated, the specific draw reasons, `pawns_lost`, `too_long` and the finished-board catch-all.
  - `needs_defender(board, verdict, player_colour)` says whether the computer should reply.
- `endgames/queen-mate.yaml`, `rook-mate.yaml`, `king-pawn.yaml`, `opposition.yaml`: 12 positions, 3 per category, with titles and hints in our own words.
  - Every FEN was checked with python-chess.
  - Every goal was checked with the local Stockfish (depth 22).
    - The six mate positions are forced mates.
    - Five of the king-and-pawn and opposition positions have a single key move.
    - `kp-king-leads` has three winning first moves (the king steps forward). Its hint covers all three.
- `static/js/training/endgame-state.js`: pure logic, testable in Node:
  - status texts, the move counter and the verdict messages;
  - the attempt in session storage;
  - the 503 and 429 texts;
  - the Endgames tab loader and a small HTTP client.
- `static/js/training/endgame.js`: the endgame screen.
- 7 test files (listed under Tests).

**Modified**
- `justchess/api.py`:
  - `GET /api/endgames`, `GET /api/endgames/{id}`, `POST /api/endgames/{id}/play` and the page route `/learn/endgames/{id}`;
  - a shared wait helper, `_await_engine`, with `ClientGone` and `EngineWaitTimeout`, which the hint route now uses unchanged;
  - the endgame rate limiter;
  - `create_app(endgames_dir=...)`.
- `justchess/gameplay.py` and `gameplay.yaml`: a new `endgames` section, validated. `refusal_queue` may not exceed `queue_cap`.
- `static/js/app.js`: the tab registration and the endgame routes.
- `static/js/training/hub.js`: an optional `context` passed to the tab loaders.
- `static/css/training.css`, `static/ASSETS.md`, `README.md` (the new "Endgame trainer" section, plus updates to "Tuning gameplay" and "Trainer hub").
- Tests: `tests/test_gameplay.py` (+1), and `tests/test_u5_trainer_browser.py` (the expected tab list now includes endgames).

There are no schema changes.

## Deviations from the plan
1. **Extra fields for the board.** The page board has no chess rules of its own, so the responses carry the board state and the legal moves:
   - the position response adds `side`, `legalMoves`, `check`, `categoryLabel` and `next`;
   - the play answer adds `playerFen`, `playerCheck`, `fen`, `legalMoves` and `check`.
2. **`needs_defender` signature.** It takes the verdict and the player's colour, because the board alone can't say whether the attempt is still playing.
3. **When a board counts as finished (BR2.6).** The catch-all counts only draws that have actually happened. A draw that could merely be claimed on the next move does not end the attempt. This matches the U4 automatic-draw rule.
4. **Where the tab loader lives.** It sits in `endgame-state.js`, which uses no DOM, so Node can test it.
5. **Small changes outside the plan.** The U5 hub gains an optional `context` setting, and one U5 browser assertion is updated for the new tab.
6. **Wording.**
   - 400 messages name the move ("Illegal move (move n)").
   - A client that disconnects while waiting gets 409 "The move was cancelled".
   - Hub rows show the category and goal as a subtitle.

## Tests
| File | Tests | Result |
|---|---|---|
| tests/test_endgames_content.py | 4 | passed |
| tests/test_endgames.py | 6 | passed |
| tests/test_endgame_judge.py | 10 (11 runs) | passed |
| tests/core/test_endgames_api.py | 9 | passed |
| tests/test_gameplay.py | +1 | passed |
| tests/js/endgame.test.mjs | 8 | passed |
| tests/js/endgame-tab.test.mjs | 3 | passed |
| tests/test_u6_endgame_browser.py | 1 | passed in headless Chromium |

| Run | Result |
|---|---|
| Baseline `uv run --frozen pytest -q` | 354 passed, 1 skipped |
| Full `uv run --frozen pytest -q` after the build | 386 passed, 1 skipped (the existing push end-to-end skip) |
| Node suite | 221 passed |
| U4 hint tests after the wait-helper change | passed, unchanged |

Every test that was written was also run.
