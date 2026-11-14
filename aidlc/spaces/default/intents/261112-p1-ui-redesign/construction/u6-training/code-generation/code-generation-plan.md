# Code Generation Plan — u6-training

## Summary

- Builds: an opening trainer that teaches from lesson files. It has an animated walkthrough. In practice the trainer replies to your moves, and you can switch sides. It gives a hint, then shows an arrow after 3 misses, and tells illegal moves apart from moves that are legal but off the line, with free play. It works inside the game's "Learn openings" drawer and on its own page at `/learn`.
- Touches:
  - new `justchess/lessons.py`, plus a `lessons/` folder with the Italian Game and the French Exchange Monte Carlo;
  - `justchess/api.py`: lesson routes and a stateless free-play move route replace the inline lesson list;
  - new `static/js/training/*` and `static/css/training.css`;
  - small additive changes to U2's board (`onRejectedTap`, `hintSquare`) and to U3's `app.js`, `hooks.js`, `game.js` and `lobby.js` (mounting and the `/learn` route);
  - `pyyaml` added as a direct dependency;
  - new tests.
- Tests: about 16 pytest tests (loader, routes, both lessons) and about 22 Node tests (trainer reducer, arrow geometry, board addition). It also adds the U3 failure-path tests carried over from that unit's review.

## Inputs

- `construction/u6-training/functional-design/` (`functional-spec.md`, `entities.md`, `rules.md`, `frontend-components.md`).
- `inception/refined-mockups/mockups.md` (Training section).
- The existing code: `justchess/api.py`, U2's `static/js/board/*`, and U3's `static/js/app.js`, `hooks.js` and `screens/*`.

## Design review findings resolved in this build

The functional design review (advisory, NOT-READY) raised the points below. Each row says how this build settles it.

| Finding | Build decision |
|---|---|
| Safe file handling (Major) | YAML is read only with `yaml.safe_load`, and JSON with `json.loads`. Files over 64 KB are skipped, with the reason "file too large". Symlinks and anything that is not a regular file are skipped. The folder is `lessons/` at the project root (next to `app.py`), resolved once in `create_app`. `JUSTCHESS_LESSONS_DIR` overrides it, and tests inject a path. A missing folder means an empty catalog plus a warning, not a crash. The id is checked with the regex before any lookup and is never joined into a path; files are only listed, never opened by a name from a request. |
| When `onRejectedTap` fires (Major) | It fires only when a piece is selected and the person then picks an empty square or an opponent's piece that is not one of the selected piece's targets. These never fire it: tapping the selected piece again (deselect), Escape, a drag cancel, picking another own piece (which reselects), and taps while the board is not interactive or a move is pending. Node tests pin each case. |
| Mounting contract (Major) | U3's hook contract becomes `lessonsMount(element, {getSnapshot}) → {destroy()} \| void`. U3 calls it when the drawer first opens (the first `toggle` to open), not when the screen is built, stores what it returns, and calls `destroy()` when the game screen is torn down (leaving the room, seat-moved re-render, or route change). `hooks.js` and its comments are updated. The trainer's `destroy()` clears its timers, including the 500 ms reply timer, cancels any request in flight with an `AbortController`, and removes its DOM. The reply timer is also cleared whenever the state leaves practice. |
| What an off-line move shows (Major) | The move is shown. The board's pending move is resolved by `board.set({fen: offLineFen, lastMove: uci, interactive: false})`, with `offLineFen` from `POST /api/position/move`. While the choice is open the board is locked, and the panel shows "Legal, but not this line" with "Keep playing freely" and "Back to the line". "Back to the line" calls `board.set({fen: step.fenBefore, lastMove: previous step's uci or null, interactive: true, legalMoves: step.legalBefore})`. BR4.2's "position unchanged" is read as "the lesson position is unchanged". The state machine gains an "Other lessons" exit from every phase. |
| Hint availability and highlight | The Hint button is always shown on learner plies. It highlights the from-square through a new optional board option, `hintSquare` (a dashed accent ring, styled in U2's `board.css`), and the message also says it in words: "Move the piece on g1." |
| Free-play outcome | `outcome` is one of `checkmate`, `stalemate`, `insufficient_material`, `fifty_moves`, `seventyfive_moves` or `null`. The route checks the uci against `^[a-h][1-8][a-h][1-8][qrbn]?$` and the fen with `chess.Board(fen).is_valid()` before using them. It cannot know about repetition because it keeps no state, and this is documented. |
| Alternatives | Shown under the move's note as "Also good: Nf6 (note)". The data is already served. |
| Drawer layout and arrow | In the drawer the trainer stacks vertically. Its board is the drawer width up to 480 px and never under 300 px, so the 44 px targets are kept from 352 px. The arrow layer is `pointer-events: none` and `aria-hidden`. The arrow uses `--hl-last-tint` (#8A6A22 in light mode) or the dark-mode brass, with a 2 px paper-coloured outline, so it stays at least 3:1 against both square colours. A contrast test checks this. |
| Route shape | A pytest test pins the new detail shape (`steps[].fenBefore` and `fenAfter`, among others), checks that the old `before` and `final` keys and the inline `LESSONS` dict are gone, and checks the 404 for a malformed id. |

## Carried over from earlier unit reviews

- **U3 Major (failure paths untested):** add Node tests driving `app.js`'s room flow through a small extracted pure helper, `static/js/room-flow.js`, with injected api, storage and live clients. Cover:
  - the stale-seat notice;
  - 409 room full removing the stored seat;
  - redeeming the continue fragment, and its 403;
  - a 403 "This isn't your seat" on an action, leading to watching;
  - a move refused with 400 and with 409 plus a snapshot;
  - `beforeMove` throwing, which fails closed.

  `app.js` keeps its behaviour and calls the helper.
- **U1 Major (BR2.1 written order):** still left for Build and Test.

## Steps

- [x] Step 1: Project structure.
  - Create `lessons/`, `justchess/lessons.py`, `static/js/training/` and `static/css/training.css`.
  - Run `uv add pyyaml`, which records the direct dependency; it is already in `uv.lock`.
  - Serve the shell at `/learn` and `/learn/{id}` from `api.py`.
- [x] Step 2: Verify the test runners. They are unchanged: `node --test tests/js/` and `uv run --frozen pytest -q`. Record the unit commands in `unit-test-instructions.md`.
- [x] Step 3: Lesson data. Write `lessons/italian.yaml` and `lessons/monte-carlo.yaml`, following BR1.4. Each has a name, aliases, eco, side `white`, start `startpos`, moves with notes (and alternatives where useful), and 2–3 objectives.
- [x] Step 4: Loader in `justchess/lessons.py`.
  - Scan with the safety rules above and validate per BR1.2. Expand into steps per BR1.3, using `python-chess`.
  - Build `LessonCatalog` with `problems` and `dirStamp`. Reload when the stamp changes and swap the catalog in atomically, with a lock around the swap.
  - Log each problem at warning level with the file name and reason.
- [x] Step 5: Loader tests in `tests/test_lessons.py`:
  - both shipped lessons load and replay;
  - a missing required field is skipped with its reason;
  - an illegal SAN is skipped;
  - SAN and UCI disagreeing is skipped;
  - a duplicate id is skipped;
  - an oversized file is skipped;
  - a symlink is skipped;
  - JSON and YAML are both accepted;
  - steps have the right FENs and legal moves;
  - adding a file is picked up on the next list call.
- [x] Step 6: Routes in `justchess/api.py`.
  - `GET /api/lessons`, `GET /api/lessons/{id}` and `POST /api/position/move`, per BR2.1–BR2.3 and the decisions above.
  - Remove the inline `LESSONS` dict.
- [x] Step 7: Route tests in `tests/test_lessons_api.py`:
  - the list shape and sort order;
  - the detail shape, with the old keys gone;
  - a malformed id and an unknown id both give 404;
  - position move: legal, illegal, invalid FEN, a bad uci pattern, promotion, an outcome at checkmate, and a foreign origin giving 403.
- [x] Step 8: Pure frontend modules.
  - `static/js/training/trainer-state.js`: the reducer per frontend-components.md, plus the decisions above (Other-lessons exits, offLine shown and locked, hint, arrow at 3 misses, side switch with the trainer's first ply, completion).
  - `static/js/training/arrow.js`: arrow geometry for both orientations.
  - `static/js/training/lessons-api.js`.
  - `static/js/room-flow.js`: the carried U3 helper.
- [x] Step 9: Frontend tests.
  - `tests/js/trainer-state.test.mjs` (about 12 cases): walkthrough limits, practice judging, the miss count and arrow, trainer replies, the side switch, free play in and out, completion, the exits, and timers cancelled on leaving practice.
  - `tests/js/arrow.test.mjs`: 3 cases.
  - `tests/js/board-rejected-tap.test.mjs`: about 6 cases on U2's `interaction.js`, covering every fire and no-fire case above.
  - `tests/js/room-flow.test.mjs`: the carried U3 cases.
  - `contrast.test.mjs`: the arrow pairs.
- [x] Step 10: DOM modules and wiring.
  - `static/js/training/trainer.js` (`mountTrainer`) and `static/css/training.css`.
  - U2: the `onRejectedTap` and `hintSquare` options.
  - U3: the hook contract change; the lobby's "Learn an opening" button; the `/learn` routes in `app.js`; and `app.js` using `room-flow.js`.
- [x] Step 11: Integration checks.
  - Extend `tests/test_game_screen.py`: `/learn` serves the shell, and every new module import resolves.
  - If Chromium is available, add a browser run that opens `/learn/italian`, plays the walkthrough to the end, then in practice:
    - plays a wrong legal move and sees "Legal, but not this line";
    - goes back to the line;
    - plays the correct moves and sees the trainer reply;
    - reaches "Line complete".
  - Run `uv run --frozen pytest -q`.
- [x] Step 12: Documentation and traceability.
  - README section "Opening lessons": how to add a lesson file, the schema, and that `JUSTCHESS_LESSONS_DIR` overrides the folder.
  - Module headers.
  - `source-manifest.json`, with every file listed individually and no record or plan files. Leave `code-summary.md` and `traceability.json` to the orchestrator.

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

The data model layer has nothing to build: lessons are files, not database rows. The loader is this unit's "repository / data access" layer, and it is tested in Step 5.
