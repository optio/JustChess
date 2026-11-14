# Code Generation Plan — u6-endgame-trainer

## Sources
- The functional design in `construction/u6-endgame-trainer/functional-design/`: `entities.md`, `rules.md` (BR1.1–BR1.2, BR2.1–BR2.6, BR3.1–BR3.3, BR4.1–BR4.2) and `functional-spec.md` (W1–W3, with the review fixes).
- `inception/units-generation/unit-of-work.md` (U6).
- Requirements FR8.1, FR8.2, FR6.7 and NFR1.

## What changes
The work is brownfield. It builds on U4's Engine and `gameplay.yaml`, and on U5's trainer hub.
- **Back end:**
  - new `justchess/endgames.py` (catalog and judging);
  - new content files `endgames/queen-mate.yaml`, `rook-mate.yaml`, `king-pawn.yaml` and `opposition.yaml`;
  - changes to `justchess/api.py` (routes and the page route), `justchess/gameplay.py` and `gameplay.yaml` (a new `endgames` section).
- **Front end:**
  - new `static/js/training/endgame.js` (screen logic) and `static/js/training/endgame-state.js` (pure state and texts);
  - registration of the Endgames tab in the hub;
  - small changes to `templates/index.html` and the CSS where needed.

There are no schema changes.

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

No database is involved. The data-access layer is the YAML catalog loader, and the business-logic layer is the judge.

## Steps

- [x] **Step 1 — Structure.** Create skeletons with header comments: `justchess/endgames.py`, `static/js/training/endgame-state.js`, `static/js/training/endgame.js`, and an empty `endgames/` folder holding its README line in `static/ASSETS.md` (own content, no licence needed).
- [x] **Step 2 — Runner check.** Confirm `uv run --frozen pytest -q tests/test_puzzles.py` (or the nearest existing trainer test) and `node --test tests/js/hub-tabs.test.mjs` run, then record the unit commands in `unit-test-instructions.md`.
- [x] **Step 3 — Catalog and content: implement** (BR1.1, BR1.2).
  - `endgames.py`: `load_catalog(folder)` reads the four fixed category files only, validates each position (legal FEN, not over, player to move, goal-appropriate material, unique id, text lengths), skips bad ones with a warning, and marks the catalog not installed when the folder is missing.
  - Write the content: at least 3 positions per category, each with a hint in our own words.
    - queen-mate: KQ v K, 3 positions;
    - rook-mate: KR v K, 3 positions;
    - king-pawn: KP v K, with promote and draw goals, 3 positions;
    - opposition: K+P positions where opposition decides, with promote or draw goals, 3 positions.

    Each FEN is checked with python-chess while writing.
- [x] **Step 4 — Catalog: tests.**
  - `tests/test_endgames_content.py` (4):
    - every shipped position loads and none is skipped;
    - there are at least 3 per category;
    - every goal fits its category;
    - every hint is present.
  - `tests/test_endgames.py` (6):
    - a bad FEN, a finished position, the wrong side to move and a duplicate id are each skipped with a warning;
    - a missing folder means not installed;
    - an extra unknown file is ignored.
- [x] **Step 5 — Judge: implement** (BR2.1–BR2.4, BR2.6).
  - `judge(board, goal, player_colour, player_moves, settings)` returns `playing`, `passed` or `failed`, with a reason.
  - It covers the mate, promote and draw goals, the defender checkmated (passed for every goal), the specific draw reasons, `pawns_lost` and `too_long`, and the finished-board catch-all.
  - `needs_defender(board)` is true only when the attempt is playing and the defender has legal moves.
- [x] **Step 6 — Judge: tests.** `tests/test_endgame_judge.py` (10). Each test sets up a FEN and moves:
  - mate passes;
  - stalemate fails a mate goal;
  - repetition fails a mate goal and passes a draw goal;
  - promotion passes;
  - losing all pawns fails;
  - the defender checkmated passes a promote goal and a draw goal;
  - 30 player moves held passes;
  - the player mated fails;
  - too long fails;
  - a finished board never needs the defender.
- [x] **Step 7 — API: implement** (BR2.5, BR3.1–BR3.3).
  - Add `gameplay.yaml` section `endgames` (defender_skill 20, defender_think_seconds 1.0, hold_moves 30, max_plies 300, play_per_minute 30, refusal_queue 16, wait_limit_seconds 30), with comments, and extend the loader's validation and defaults.
  - **Routes:**
    - `GET /api/endgames` returns `installed`, `available` and `reason` (from Engine status) and the categories;
    - `GET /api/endgames/{id}` gives 404 for an unknown id;
    - `POST /api/endgames/{id}/play`.
  - **The play route:**
    - it is origin-checked and uses the default 4 KB body limit;
    - it validates the moves (UCI shape, legal in order, odd length, at most max_plies);
    - it judges, and when `needs_defender` is true:
      - it refuses as busy when `queued_count() >= refusal_queue` or Engine raises Busy, and answers 503 when Engine is unavailable;
      - it submits with skill 20 for 1 s with no depth or randomness, and waits through a neutral wait helper shared with hints (cancel on disconnect, a 30 s limit answered as busy);
      - it checks that the defender's move is legal, applies it and judges again;
    - it is rate-limited at 30 per minute per address (429);
    - it answers with the verdict.
  - Extract the hint's wait into the neutral helper without changing the hint's behaviour or messages.
  - **Page route:** `/learn/endgames/{id}` serves the app shell.
- [x] **Step 8 — API: tests.** `tests/core/test_endgames_api.py` (9), using the fake engine:
  - list and get, plus 404;
  - a play round trip returns the reply and the verdict;
  - the player's finishing move does not ask the engine;
  - illegal move, even length and too long give 400;
  - an oversized body gives 413;
  - 503 when unavailable;
  - 503 when the queue is at the refusal threshold;
  - the wait limit cancels the engine request and answers busy;
  - 429.

  Also run the existing U4 hint tests to confirm the extracted wait helper changed nothing.
- [x] **Step 9 — Front end: implement** (BR4.1, BR4.2).
  - `endgame-state.js` (pure):
    - goal status texts;
    - the "Move n of 30" counter;
    - verdict messages (done with mate, promotion or draw held; escaped; computer won);
    - the attempt's session-storage round trip, inside try/catch;
    - the error texts for 503 and 429.
  - `endgame.js` (screen):
    - loads the position and orients the board;
    - sends each move, shows "Computer is thinking…" and locks the board meanwhile;
    - plays the reply;
    - handles the verdict, marks the position solved (trainer-progress group `endgames`) and shows Next position;
    - offers Hint, which reveals the text, and Start again;
    - takes the move back on 503 or 429.
  - Register the "endgames" tab in the hub registry with a loader. It shows the categories and rows with Done, the count, and either the "Needs Stockfish: reason" note with Play disabled, or "No endgame positions are installed".
- [x] **Step 10 — Front end: tests.**
  - `tests/js/endgame.test.mjs` (8):
    - the status for each goal;
    - the move counter;
    - each verdict message;
    - the session-storage round trip and a storage error;
    - the 503 and 429 texts.
  - `tests/js/endgame-tab.test.mjs` (3):
    - rows and the count;
    - "Needs Stockfish" disables Play;
    - the not-installed state.
  - A browser test, `tests/test_u6_endgame_browser.py` (1): open the Endgames tab, play a queen-mate position against the fake engine until it passes, and see Done in the tab. It is skipped when Chromium is missing.
  - Then run the full suite.
- [x] **Step 11 — Configuration.** Add the `endgames` section to `gameplay.yaml` (step 7) and update the README "Tuning gameplay" section. Add a short "Endgame trainer" README section covering the goals, the content files and the fact that it needs Stockfish.
- [x] **Step 12 — Documentation and traceability.** Write `code-summary.md`, `source-manifest.json` and `traceability.json`.

## Requirement-to-step map

| ID | Steps |
|---|---|
| FR8.1 | 7, 9, 10 |
| FR8.2 | 3, 4, 5, 6, 7, 8, 9, 10 |
| FR6.7 | 7, 8, 9, 10 |
| NFR1 | 7, 8 |

## Constraints
- Position ids are never used to build file paths.
- Only boards replayed from the start FEN and validated moves reach the engine.
- No test touches `justchess.sqlite3`.
- The unit tests use the fake engine.
- Files are written with file tools.
