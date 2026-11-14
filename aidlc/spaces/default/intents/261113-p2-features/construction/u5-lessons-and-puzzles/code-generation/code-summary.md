# Code Summary — u5-lessons-and-puzzles

All 12 plan steps are done. Step 12's README part was done by the build. This summary and the two traceability files complete it. The build was interrupted once by an API usage limit, then resumed from the ticked steps.

## Files

**Created**
- **Puzzles:** `puzzles/fork.json`, `pin.json`, `skewer.json`, `discoveredAttack.json`, `mateIn1.json`, `mateIn2.json` and `LICENSE.md`. They hold 1,800 puzzles taken from the Lichess puzzle database (CC0), 281,135 bytes in total.
- **Lessons (16 new):**
  - Openings: `ruy-lopez`, `sicilian`, `french`, `caro-kann`, `queens-gambit`, `london`, `kings-indian`, `scandinavian`.
  - Traps: `legals-mate`, `fried-liver`, `fishing-pole`, `englund-gambit-trap`.
  - Defence: `scholars-mate-defence`, `fried-liver-defence`, `early-queen-raids`, `wayward-queen`.

  Every line replays legally, and every move has a note written in our own words.
- **Code:**
  - `justchess/puzzles.py`: validators, the in-memory store, `check` and `hint`.
  - `scripts/curate_puzzles.py`.
  - In `static/js/training/`: `hub-tabs.js`, `trainer-progress.js`, `puzzle-state.js`, `puzzle.js`, `hub.js`.
- **Tests:**
  - Python: `tests/test_puzzles.py` (9), `tests/test_puzzles_api.py` (8), `tests/test_curate_puzzles.py` (4), `tests/test_u5_trainer_browser.py` (2).
  - JS: `tests/js/hub-tabs.test.mjs` (5), `trainer-progress.test.mjs` (5), `puzzle-state.test.mjs` (7).
  - Fixtures: `tests/fixtures/puzzles_sample.csv` (28 hand-checked rows), `tests/fixtures/puzzle_set.py` (test-only).
- `data/lichess_db_puzzle.csv.zst`, the 310 MB download. It is ignored by git and can be deleted.

**Modified**
- `.gitignore` (adds `data/`), `.env.example` (`JUSTCHESS_PUZZLES_DIR`), `README.md`, `static/ASSETS.md`.
- `justchess/lessons.py` (`kind`) and `justchess/api.py` (the lesson filter, puzzle routes, `/learn/tactics/{theme}`, loading the store at start-up).
- `static/js/app.js`, `static/js/training/trainer-state.js` (`arrowShown`, progress effect), `trainer.js`, `lessons-api.js`, `static/css/training.css`.
- Tests: `test_lessons.py` (+4), `test_lessons_api.py` (+2), `test_envfile.py`, `test_game_screen.py`, `tests/js/trainer-state.test.mjs` (+1).

## Curation run

The script used seed 20261113, kept puzzles with popularity ≥ 80, plays ≥ 500 and rating 600–2200, and validated every candidate before sampling.

| Theme | Candidates | Valid | Kept |
|---|---|---|---|
| fork | 361,993 | 357,858 | 300 |
| pin | 171,820 | 169,673 | 300 |
| skewer | 62,841 | 61,351 | 300 |
| discoveredAttack | 151,998 | 150,682 | 300 |
| mateIn1 | 227,643 | 227,643 | 300 |
| mateIn2 | 324,907 | 324,907 | 300 |

## Deviations from the plan
1. **Existing tests changed for `kind`.** The lesson API key lists and the "exactly two lessons" check were updated, and the lesson detail now carries `kind`.
2. **Old trainer browser test updated.** `test_lesson_trainer_browser_run` now goes through the hub, since `/learn` is the hub.
3. **Puzzle answers carry extra fields** (legal moves, FENs after each move, check flags), so the browser needs no chess engine. A checkmate on any player move counts as solved.
4. **No new client file for puzzles.** The puzzle client calls live in the existing `lessons-api.js`.
5. **The Tactics tab total counts puzzles, not themes,** for example "0/1800", as BR3.2 says. The mockup counted themes.
6. **Templates unchanged.** `training.css` was already linked.
7. **`mkdir -p data`** was run before the authorized download.

## Tests

| Command | Result |
|---|---|
| Baseline `uv run --frozen pytest -q` | 211 passed, 1 skipped |
| `uv run --frozen pytest -q` (full) | 243 passed, 1 skipped (the existing push end-to-end skip) |
| Node suite inside pytest | 196 passed (166 before) |

All three trainer browser tests ran in headless Chromium, none skipped. Every test written was run.
