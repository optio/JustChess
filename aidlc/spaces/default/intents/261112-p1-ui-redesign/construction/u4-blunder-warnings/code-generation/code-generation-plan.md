# Code Generation Plan — u4-blunder-warnings

## Summary

- Builds: warnings before a blunder. The server checks your move before it is sent. If the move allows mate in one, or leaves a knight, bishop, rook or queen that can be taken for free, a dialog says why and asks you to confirm. It only warns about problems this move creates. It stays quiet when every move has the same problem. The "Warn me before blunders" setting turns it off.
- Touches:
  - new `justchess/analysis.py`;
  - a `POST /api/rooms/{code}/check-move` route in `justchess/api.py`;
  - new `static/js/blunder.js` (hook and dialog logic) and `static/js/screens/blunder-dialog.js`;
  - a widened move-hook result in U3's `hooks.js`, `room-flow.js` and `app.js`;
  - styles in `static/css/app.css`;
  - new tests.
- Tests: about 20 pytest tests (analysis positions, route, timing) and about 12 Node tests (dialog text, hook decisions, room-flow handling of the widened result).

## Inputs

- `construction/u4-blunder-warnings/functional-design/` (`functional-spec.md`, `rules.md`, `entities.md`).
- `inception/refined-mockups/mockups.md` (Screen 3) and `interaction-spec.md` (Blunder dialog).
- Existing code:
  - `justchess/api.py` and `games.py`;
  - `static/js/hooks.js`, `room-flow.js`, `app.js`, `screens/game.js`;
  - `settings.js`.

## Design review findings resolved in this build

The functional design review (advisory, NOT-READY) raised the points below. Each row says how this build settles it.

| Finding | Build decision |
|---|---|
| Hook result too narrow for messages and snapshots (Major) | The move hook's contract widens to `beforeMove(uci, snapshot) → Promise<true \| false \| {allow: false, message?: string, snapshot?: object}>`. `room-flow.js` (`runBeforeMove`) and `app.js` handle the object form: they show `message` through the existing flash line and apply `snapshot` through the same path as a 409 move answer. A plain `false` keeps today's silent refusal, and a throw still fails closed. The hook is installed in `app.js` at startup with `setHook("beforeMove", createBlunderHook({api, settings, dialog}))`. The `hooks.js` header documents the widened type. The existing room-flow tests are kept and extended. |
| No mechanism behind the 300 ms budget (Major) | (1) The mate-in-one scan only plays opponent replies that give check (`board.gives_check(move)` is tested first), so only checking moves are pushed. (2) The no-alternative sweep stops at the first legal move free of the problem, and tries quiet moves before captures and checks. (3) Analysis runs in `asyncio.to_thread`. The route reads the game under the room lock only long enough to copy the move list and version, then analyses outside the lock with no write transaction, so it never blocks moves or sockets. (4) There is a hard time budget of 250 ms on a monotonic clock. When the sweep runs out of time, the warning stands, because warning is safer, and the result is logged at debug level. A pytest timing test runs a busy middlegame and a position where every move allows mate, and asserts 300 ms or less on the host. |
| Legality in the before position and in exchanges (Major) | Exchanges use legal captures only, worked out by pushing real moves on a copy of the board, so pins, king recaptures and check evasions are respected. The before position comes from `board.copy()` with `push(chess.Move.null())`. When the mover is in check before the move, a null move is not meaningful, so the "before" sets are empty and every problem after the move counts as new. A mate threat's identity is "the opponent has at least one mating reply": a warning appears only when the after position has a mate and the before position had none. |
| Promotion offset | For a promoted piece, the offset is the captured value plus (promoted value − 1). A defended queen promotion that a rook takes back is therefore not called "free". A test covers it. |
| Sweep per kind | The sweep runs per warning kind. When the mate warning is dropped because every move allows mate, the hanging check runs again on its own, with its own sweep. An alternative "free of mate" only needs to allow no mate. A test covers it. |
| Client failure mapping | The check request has a 2.5 s timeout through `AbortController`. Timeout, network failure, 404, 413, 422, 429, any 5xx and a 200 with a malformed body all resolve `true` (the move goes ahead) and log `console.warn`. A 409 resolves `{allow:false, snapshot}`. A 400 or 403 resolves `{allow:false, message}`. The whole hook body sits in try/catch, so errors from reading settings or building the dialog also go ahead, and the hook never throws. |
| Meaning of "defended", and the body text | `defended` means at least one legal recapture exists after the opponent's first capture. The body names the piece: "After <move>, <colour>'s <capturer> on <capSquare> takes your <piece> on <square> and nothing takes back." When defended: "…takes your <piece> on <square> and you lose material." |
| Dialog accessibility | `role="alertdialog"`, `aria-modal="true"`, with `aria-labelledby` set to the title and `aria-describedby` set to the body. Buttons are at least 44 px. The dialog catches Escape in the capture phase and stops it there, so the board never sees it. Focus returns to the move's from-square on the board. If a snapshot with a newer version arrives while the dialog is open, the dialog closes, the hook resolves `{allow:false}`, and the new position shows. |
| Traceability | NFR6 is added to the upstream list. The route name `/api/rooms/{code}/check-move` is used in every new file and in the README. BR2.2 is recorded as a budget derived from NFR5 in the code summary. |

## Carried over from earlier unit reviews

- **U1 Major (BR2.1 written check order)** is left for Build and Test, as before. U4's route follows the order U1 actually uses (playing, then version, then turn, then legality), and the code summary says so.

## Steps

- [x] Step 1: Project structure. Create `justchess/analysis.py`, `static/js/blunder.js` and `static/js/screens/blunder-dialog.js`. No new dependencies.
- [x] Step 2: Verify the test runners. They are unchanged: `uv run --frozen pytest -q` and `node --test tests/js/`. Record the unit commands in `unit-test-instructions.md`.
- [x] Step 3: Business logic in `justchess/analysis.py`.
  - `analyse(board, move, *, budget_ms=250) → Warning | None`, implementing:
    - BR1.1–BR1.5;
    - the decisions above: checks-only mate scan, legal-capture exchange evaluation, before and after identity tracking with empty "before" sets when the mover is in check, the promotion offset, the per-kind sweep with ordering and the time budget, and `defended`.
  - A pure module with no I/O.
- [x] Step 4: Analysis tests in `tests/test_analysis.py`, using fixed FEN positions:
  - allowing Qh4# (Fool's mate setup);
  - a back-rank mate allowed;
  - a hanging knight, then a hanging queen;
  - an even trade, not warned;
  - a defended piece that loses to a lower-value attacker (defended, so the "you lose material" wording);
  - a piece already hanging, then an unrelated move, not warned;
  - every move allows mate, not warned;
  - when the mate is dropped, the hanging warning is still reported;
  - a mate threat that already existed, not warned;
  - the mover in check before the move;
  - mate takes priority over a hanging piece;
  - the most valuable piece is reported among several;
  - a pinned would-be recapturer does not count as a defender;
  - a defended queen promotion, not warned;
  - castling and en passant positions;
  - the move itself delivers mate, so no warning.
- [x] Step 5: Route in `justchess/api.py`.
  - `POST /api/rooms/{code}/check-move` takes the body `{token, uci, version}`.
  - Under the room lock, it reads the moves and version and checks seat, playing, version (409 with snapshot), turn (403) and legality (400).
  - It then runs `asyncio.to_thread(analyse, …)` outside the lock.
  - It answers `{warning, san, version}`.
  - The same origin and size middleware apply.
- [x] Step 6: Route tests in `tests/test_check_move_api.py`:
  - a clean move gives `warning: null`;
  - a mate-allowing move gives a `mate_in_one` result;
  - a hanging piece gives a `hanging_piece` result;
  - a wrong token gives 403;
  - not your turn gives 403;
  - a stale version gives 409 with a snapshot;
  - an illegal move gives 400;
  - game over gives 409;
  - a foreign origin gives 403;
  - the check does not change the version;
  - timing: a busy middlegame and the "every move allows mate" position both answer in 300 ms or less.
- [x] Step 7: Frontend pure logic in `static/js/blunder.js`.
  - `dialogText(warning, colourNames) → {title, body, confirmLabel, cancelLabel}`.
  - `createBlunderHook({api, settings, openDialog, timeoutMs=2500})`, with the decision logic and failure mapping above.
- [x] Step 8: Frontend tests.
  - `tests/js/blunder.test.mjs`:
    - text for mate, hanging and defended-hanging warnings;
    - setting off gives true;
    - no warning gives true;
    - a warning with confirm gives true, and with cancel gives false;
    - timeout and network failure give true;
    - 409 gives a snapshot result;
    - 403 gives a message result;
    - a malformed 200 gives true;
    - a thrown settings read gives true.
  - Extend `tests/js/room-flow.test.mjs` for the object result: the message is shown, the snapshot applied, and the board told to refuse.
- [x] Step 9: DOM and wiring.
  - `static/js/screens/blunder-dialog.js`: the alertdialog, focus trap, Escape caught in the capture phase, focus return, and closing on a newer snapshot.
  - Styles in `static/css/app.css`.
  - The widened contract in `hooks.js`, `room-flow.js` and `app.js`, with the hook registered at startup.
- [x] Step 10: Integration checks.
  - Extend `tests/test_game_screen.py` to check that the new modules are imported and resolve.
  - If Chromium is available, add a browser run:
    - two players reach the Fool's mate position;
    - White tries g4 after 1.f3 e5, and the dialog appears with "This allows checkmate";
    - Escape cancels and the pawn is back;
    - "Play g4 anyway" sends the move;
    - with the setting off, no dialog appears.
  - Run `uv run --frozen pytest -q`.
- [x] Step 11: Documentation and traceability.
  - A README line under "Implemented", plus the setting.
  - Module headers.
  - `source-manifest.json`, with application files only, each listed individually.
  - Leave `code-summary.md` and `traceability.json` to the orchestrator.

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

Inapplicable layers: the data model and repository layers. U4 stores nothing and reads the game through U1's existing functions.
