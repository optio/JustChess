# Unit Test Instructions — u5-lessons-and-puzzles

## Framework
- **Python:** pytest, run with `uv run --frozen`. Puzzle tests point `JUSTCHESS_PUZZLES_DIR` at `tmp_path` fixtures, except the shipped-set tests, which read `puzzles/`.
- **JS:** `node:test`, with test files in `tests/js/*.test.mjs`.
- **Browser:** headless Chromium through the CDP helpers in `tests/test_game_screen.py`. These tests skip with a reason when Chromium is missing.

## Commands for this unit only
```bash
uv run --frozen pytest -q tests/test_lessons.py tests/test_lessons_api.py tests/test_puzzles.py tests/test_puzzles_api.py tests/test_curate_puzzles.py tests/test_u5_trainer_browser.py
node --test tests/js/hub-tabs.test.mjs tests/js/trainer-progress.test.mjs tests/js/puzzle-state.test.mjs tests/js/trainer-state.test.mjs
```

The project-wide check stays `uv run --frozen pytest -q`.

## Scope (Standard strategy)

| Component | File | Tests |
|---|---|---|
| lessons.py kind + shipped lessons | tests/test_lessons.py | 4 new |
| lessons API filter | tests/test_lessons_api.py | 2 new |
| puzzles.py validators + shipped set | tests/test_puzzles.py | 9 |
| puzzle API | tests/test_puzzles_api.py | 8 |
| curation script | tests/test_curate_puzzles.py | 4 |
| hub-tabs.js | tests/js/hub-tabs.test.mjs | 5 |
| trainer-progress.js | tests/js/trainer-progress.test.mjs | 5 |
| puzzle-state.js | tests/js/puzzle-state.test.mjs | 7 |
| trainer-state.js progress | tests/js/trainer-state.test.mjs | 1 new |
| hub and puzzle (browser) | tests/test_u5_trainer_browser.py | 2 |

## Test data
- **Fixture CSV:** `tests/fixtures/puzzles_sample.csv` contains about 40 hand-checked rows in Lichess format, including deliberately broken rows.
- **Fixture puzzle directory:** for the API and browser tests, a small directory written to `tmp_path` with 2 puzzles per theme.
- **Shipped-set tests:** read the committed `puzzles/` directory.

## Coverage
This refactor scope has no coverage floor. Every new public function has tests, and the existing suite must stay green.
