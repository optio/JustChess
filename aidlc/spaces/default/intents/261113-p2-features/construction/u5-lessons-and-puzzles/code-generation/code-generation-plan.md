# Code Generation Plan — u5-lessons-and-puzzles

This plan builds U5 from these sources:
- `construction/u5-lessons-and-puzzles/functional-design/` (`entities.md`, `rules.md` BR1.1–BR3.4, `functional-spec.md` W1–W5);
- `inception/units-generation/unit-of-work.md` (U5);
- requirements FR7.1–FR7.3, FR8.1, FR8.3–FR8.6, NFR4 and NFR6;
- ADR-004.

The work is brownfield in `justchess/` (`lessons.py`, `api.py`, a new `puzzles.py`), `lessons/`, a new `puzzles/` directory, `scripts/`, `static/js/training/` and `templates/`.

## Testing Contract

```json
{
  "version": 1,
  "methodology": "test-after",
  "source": "org",
  "ordering": "implement each applicable testable layer, then write and run that layer's tests.",
  "scope": "refactor",
  "test_strategy": "standard",
  "project_type": "brownfield",
  "applicable_notes": [
    {
      "layer": "org",
      "text": "We treat tests as a first-class deliverable in every Bolt. The specific\nmethodology (TDD, BDD, ATDD, or classic test-after) is affirmed at\npractices-discovery and recorded in `team.md` under this heading with explicit\n`Methodology` and `Ordering` fields; Code Generation resolves those fields\nindependently from coverage, tooling, and scope notes.\n\nWhen no posture has been affirmed, our default per scope is:\n- **Methodology**: test-after\n- **Ordering**: implement each applicable testable layer, then write and run\n  that layer's tests.\n- `mvp`, `enterprise`, `feature`, `infra`, `classic` add an 80% line-coverage\n  floor and CI execution before merge.\n- `bugfix`, `security-patch` add a targeted regression for the specific\n  bug/vulnerability and require the existing suite to remain green.\n- `express` uses the Minimal strategy: requirement-driven unit tests (one per\n  requirement, with a happy-path floor per component); existing tests remain\n  green.\n- `poc`, `refactor`, `workshop` add no extra new-test floor and require the\n  existing suite to remain green.\n\nThe active `Test Strategy` still applies in every scope and determines test\nvolume/types. Scope floors are additive; they never reduce or replace the\nselected strategy.\n\nBuild and Test verifies defined coverage floors and affirmed quality targets;\nthey may not be weakened to make a step pass.\n\nAffirm a stricter posture in `team.md` if the team commits to one."
    }
  ],
  "obligations": {
    "strategy": "standard",
    "strategy_volume": [
      "Five to eight tests per component.",
      "Unit tests plus integration tests for key boundaries.",
      "Add E2E, performance, or security tests when requirements demand them."
    ],
    "scope_floor": [
      "Keep the existing test suite green.",
      "This scope adds no extra new-test floor beyond the selected test strategy."
    ],
    "combination_rule": "Apply every selected-strategy obligation and every scope-floor obligation; neither replaces the other, and a targeted scope regression may add the narrowest necessary test type beyond the strategy default."
  },
  "plan_profile": {
    "methodology": "test-after",
    "runner_step": "Verify the existing test runner/configuration and record the exact unit-scoped command.",
    "runner_ready_before_first_test": true,
    "testable_layers": [
      "Data model / database behavior",
      "Repository / data access",
      "Business logic",
      "API / endpoint",
      "Frontend behavior"
    ],
    "steps": [
      "Project structure and production configuration skeleton.",
      "Verify the existing test runner/configuration and record the exact unit-scoped command.",
      "Data model / database behavior - implement.",
      "Data model / database behavior - write and run its tests after implementation.",
      "Repository / data access - implement.",
      "Repository / data access - write and run its tests after implementation.",
      "Business logic - implement.",
      "Business logic - write and run its tests after implementation.",
      "API / endpoint - implement.",
      "API / endpoint - write and run its tests after implementation.",
      "Frontend behavior - implement.",
      "Frontend behavior - write and run its tests after implementation.",
      "Environment/build configuration.",
      "Documentation and traceability."
    ]
  },
  "input_sha256": "sha256:322f3cce51ad835b556974215be0ae0a5aba55c673c92ff6b1b327e7eb2426e8",
  "contract_sha256": "sha256:84a32ec0d9dd634774d2a290b523e6e0d5e6f77259469f3112500519cb132392"
}
```

U5 has no database layer. The "data access" layer here is the file loaders for lessons and puzzles.

## Steps

- [x] **Step 1 — Structure.** Create the skeleton files, each with a header comment:
  - `justchess/puzzles.py`
  - `scripts/curate_puzzles.py`
  - `static/js/training/hub-tabs.js`
  - `static/js/training/trainer-progress.js`
  - `static/js/training/puzzle-state.js`
  - `static/js/training/puzzle.js`
  - `static/js/training/hub.js`

  Also add `data/` to `.gitignore` for the downloaded Lichess file. The `.gitignore` changes; the plan names this change.
- [x] **Step 2 — Runner check.** Confirm `uv run --frozen pytest -q tests/test_lessons.py` and `node --test tests/js/trainer-state.test.mjs` run, and record the unit commands in `unit-test-instructions.md`.
- [x] **Step 3 — Loaders: implement** (BR1.1, BR2.1).
  - `lessons.py`:
    - add `kind` to `KNOWN_FIELDS`;
    - validate it against opening, trap and defence, defaulting to opening;
    - include it in `summaries()`;
    - add a `kind` filter helper.
  - `puzzles.py`:
    - `JUSTCHESS_PUZZLES_DIR`, defaulting to `puzzles/`;
    - load every theme file;
    - shared `validate_puzzle()` covering legality, the mate check, player-move counts and the theme match;
    - a `PuzzleStore` that keeps puzzles in memory sorted by rating;
    - each skipped puzzle logs its id.
- [x] **Step 4 — Loaders: tests.**
  - `tests/test_lessons.py`, 3 new tests: the default kind, a bad kind being skipped, and the counts per kind.
  - `tests/test_puzzles.py`, validator part, 6 tests: an illegal move, a mate theme without mate, a wrong player-move count, a wrong theme, a valid puzzle, and a missing directory.
- [x] **Step 5 — Curation and content** (BR1.3, BR2.2). Two parts.

  **Puzzles**
  - Write `scripts/curate_puzzles.py`. It reads the CSV (PuzzleId, FEN, Moves, Rating, Popularity, NbPlays, Themes) from a path or from stdin, filters, runs `validate_puzzle()`, samples 300 per theme with a fixed seed, and writes `puzzles/<theme>.json` and `puzzles/LICENSE.md`. It fails if a theme ends under 250 puzzles or the total exceeds 5 MB.
  - Download the source once: `curl -L -o data/lichess_db_puzzle.csv.zst https://database.lichess.org/lichess_db_puzzle.csv.zst` (about 250 MB, git-ignored).
  - Run `zstd -dc data/lichess_db_puzzle.csv.zst | uv run --frozen python scripts/curate_puzzles.py -` and commit the output.
  - If the download is unavailable, stop and report it. No unverified puzzles are shipped.

  **Lessons** (original wording, standard theory lines, a note on every move)
  - 8 openings: `ruy-lopez`, `sicilian`, `french`, `caro-kann`, `queens-gambit`, `london`, `kings-indian`, `scandinavian`.
  - 4 traps: `legals-mate`, `fried-liver`, `fishing-pole`, `englund-gambit-trap`.
  - 4 defence lessons: `scholars-mate-defence`, `fried-liver-defence`, `early-queen-raids`, `wayward-queen`.
  - Credit the Lichess data in `static/ASSETS.md`.
- [x] **Step 6 — Curation and content: tests.**
  - `tests/test_curate_puzzles.py`, 4 tests on a small fixture CSV in `tests/fixtures/`: filtering, validators applied before sampling, the output shape, and the failure on fewer than 250.
  - `tests/test_puzzles.py`, shipped-set part, 3 tests: every puzzle loads, 250–400 per theme, at most 5 MB in total, and `LICENSE.md` is present.
  - `tests/test_lessons.py`: every shipped lesson loads with no skips (1 test).
- [x] **Step 7 — API: implement** (BR1.2, BR2.4, W3).
  - `GET /api/lessons?kind=` returns 400 for an unknown kind.
  - Puzzle routes:
    - `GET /api/puzzles`;
    - `GET /api/puzzles/{theme}`;
    - `GET /api/puzzles/{theme}/{id}`, without the solution;
    - `POST …/check` with `{ply, uci}`;
    - `POST …/hint` with `{ply, level}`.
  - All routes are origin-checked, size-limited and read-only.
  - Page route `GET /learn/tactics/{theme}`.
  - Load the puzzle store at startup.
- [x] **Step 8 — API: tests.**
  - `tests/test_lessons_api.py`: 2 new tests for the filter and the 400.
  - `tests/test_puzzles_api.py`, 8 tests:
    - list themes;
    - list a theme;
    - detail without the solution;
    - check: correct with a reply, solved, wrong (no solution leaked), and an alternative mate counted as solved;
    - hint at each level, plus the 404 and 400 cases;
    - the page route returns 200.
- [x] **Step 9 — Front end: implement** (BR2.3, BR2.5, BR3.1–BR3.4).
  - `hub-tabs.js`: a registry with `registerTab`, plus ARIA tablist keyboard logic.
  - `trainer-progress.js`: a per-device store with try/catch around storage.
  - `puzzle-state.js`: the state machine from W5.
  - `puzzle.js`: the screen, built from the board module, the status line, the arrow module and the credit line.
  - `hub.js`: the `/learn` hub with lesson tabs by kind, a Tactics theme list and progress counts.
  - `trainer-state.js`: an `arrowShown` flag and a progress effect on completion.
  - `lessons-api.js`: `isSummary` accepts `kind`.
  - The game-screen drawer lists `kind=opening` only.
  - CSS goes in `training.css`.
- [x] **Step 10 — Front end: tests.**
  - `tests/js/hub-tabs.test.mjs`: 5 tests.
  - `tests/js/trainer-progress.test.mjs`: 5 tests.
  - `tests/js/puzzle-state.test.mjs`: 7 tests.
  - `tests/js/trainer-state.test.mjs`: 1 new test for the progress effect.
  - Browser test `tests/test_u5_trainer_browser.py`: the tabs work by keyboard, the Tactics list shows, and a fixture puzzle is solved (2 tests).
  - Then run the full suite.
- [x] **Step 11 — Config.** The new optional setting `JUSTCHESS_PUZZLES_DIR` is added to `.env.example`, the env-file test's allowed list and the README.
- [x] **Step 12 — Docs and traceability.**
  - README: the trainer hub, how to re-run curation, and the CC0 credit.
  - Write `code-summary.md` and `traceability.json`.

## Requirement-to-step map

| ID | Steps |
|---|---|
| FR7.1 | 3, 4, 5, 6, 7, 8 |
| FR7.2 | 3, 5, 6 |
| FR7.3 | 5, 6 |
| FR8.1 | 9, 10 |
| FR8.3 | 3, 4, 5, 6, 7, 8, 9, 10 |
| FR8.4 | 3, 5, 6, 7 |
| FR8.5 | 9, 10 |
| FR8.6 | 5, 9 |
| NFR4 | 3, 7, 8 |
| NFR6 | 5, 6 |

## Constraints
- **Allowed download:** only the public Lichess puzzle file, once, into the git-ignored `data/` directory. The app downloads nothing at runtime.
- **Lesson content:** the text is original. Lines and trap sequences are standard chess theory.
- **Database:** no test touches `justchess.sqlite3`.
- **File writes:** files are written with file tools. The download and curation commands run as written above.
