# Code Generation Plan — u3-game-screen

## Summary

- Builds: the real new app. It covers:
  - the lobby;
  - joining by link or code;
  - the game screen with a slim top bar, Share, status, claims, scoresheet and room score;
  - live updates with reconnect;
  - continuing on another device;
  - the game-over overlay with the win sequence;
  - rematch;
  - every designed state.

  The old client is removed.
- Touches:
  - New `static/js/` modules: `app.js`, `api.js`, `live.js`, `seat-store.js`, `view-model.js`, `screen-state.js`, `share.js`, `hooks.js`, and `screens/*`.
  - New `static/css/app.css`.
  - `templates/index.html` is rewritten, and `static/app.js` and `static/style.css` are deleted.
  - Small additive changes to `justchess/games.py`: a `claimableDrawReason` field, and the legacy snapshot fields removed.
  - One CSS fix in `static/css/tokens.css` carried over from the board review.
  - New tests in `tests/js/` and `tests/test_game_screen.py`.
- Tests: about 45 Node tests on the pure modules (view model, screen state reducer, API client, live backoff, seat store, share choice), about 8 pytest tests, and a headless browser two-player run when Chromium is available.

## Inputs

- `construction/u3-game-screen/functional-design/` (`functional-spec.md`, `frontend-components.md`, `rules.md`).
- `inception/refined-mockups/` (`mockups.md`, `interaction-spec.md`, `design-system-mapping.md`) and the published mockup.
- The U1 code (`justchess/api.py`, `games.py`, `live.py`, `rooms.py`) and the U2 code (`static/js/board/*`, `settings*.js`, `static/css/*`).

## Design review findings resolved in this build

The functional design review (advisory, NOT-READY) raised the points below. Each row says how this build settles it.

| Finding | Build decision |
|---|---|
| Join returns no snapshot (Major) | After a 200 from create or join, the client calls `state(code, token)` with the `X-Seat-Token` header and draws that snapshot. The socket's first `state` replaces it when newer. On a 409 room-full, the attached `snapshot` is drawn as the watcher view. |
| Stale-token handling (Major) | The server treats an unknown token as no token. When a stored token was sent and the join answers with a different token or slot, the stored seat was stale: the new seat replaces it in storage, and the screen says "Your old seat had expired, so you joined as <colour>." When a stored token was sent and the answer is 409 room full, the stored seat is removed and the viewer watches. The dead "403 then retry" branch is dropped. On action routes, a 403 "This isn't your seat" also removes the stored seat and switches to watching, with the notice "This device is no longer seated in this game." |
| Incomplete screen state machine (Major) | The screen state is a pure reducer in `static/js/screen-state.js`: `reduce(state, event) → state`. The base view is `lobby`, `joining`, `notFound`, `waiting`, `playing`, `gameOver` or `watching`. The connection is a separate flag (`open` or `reconnecting`) on the base view, so reconnecting works in every room view and the status line puts "Game over" first, as BR3.4 says. A snapshot always re-derives the base view from its status and game number, so a gap that ends or restarts a game lands correctly. `seatsTaken` becomes a notice on `watching`. seat-moved and a seat 403 move any room view, `joining` included, to `watching`. Tests cover every transition. |
| claimableDrawReason values | Short names: `"threefold"`, `"fifty_moves"` or `null`, mapped from the `claimable_draw` results `threefold_claimed` and `fifty_moves_claimed`. pytest checks both reasons and null. |
| Result glyphs | `resultText` maps `1-0` → "1–0", `0-1` → "0–1" and `1/2-1/2` → "½–½". Tested. |
| lastMove | The UCI string goes straight to U2's board, which accepts UCI. There is no hand split. |
| Legacy snapshot fields | Removed in this unit (`moves`, `legal`, `white_score`, `black_score`, `outcome`), with U1's tests updated, because the old client is deleted here. |
| Move hook | `hooks.beforeMove(uci, snapshot) → Promise<boolean>`. The default resolves true. `false` calls `board.reject()`. A throw is logged, and the move is rejected with "Couldn't check that move. Try again." U4 replaces the hook. |
| Overlay accessibility | On phones the overlay sits under the board, between the board and the status, so it never covers the board. On desktop it sits over the lower third of the board with a translucent paper backing. It opens with `role="region"`, `aria-labelledby` set to its title, and focus on Play again. When a rematch starts it closes and focus returns to the board. The status line also carries "Game over — <reason>". |
| Screen logic tests | Covered by the reducer tests above. That includes seat-moved, a new game arriving during the win sequence, and a snapshot arriving while reconnecting. |

## Carried over from earlier unit reviews

- **U2 Major (label contrast under the last-move highlight):** add contrast pairs to `tests/js/contrast.test.mjs` for coordinate labels on light and dark squares under the last-move overlay, on all three boards. Then adjust the tokens (`--hl-last` opacity, or the label colour on highlighted squares through `.sq.is-last .label`) until every pair is at least 4.5:1. Record the values in the `tokens.css` header.
- **U1 Major (move check order):** U3 handles a 409 with a snapshot and a 400/403 the same way, whatever order the server checks them in. Amending BR2.1's written order is left to Build and Test.

## Steps

- [x] Step 1: Project structure.
  - Create `static/js/screens/` and `static/css/app.css`.
  - Rewrite `templates/index.html` as the new shell: `lang="en"`, `boot.js` in `<head>`, token/base/board/app CSS, a font preload, a top bar slot, `<main id="app">`, a polite live region and `<script type="module" src="/static/js/app.js">`.
  - The Jinja context passes nothing secret.
- [x] Step 2: Verify the test runner. The runner is the same as U2's: `node --test tests/js/`, with the U2 `index.js` loader picking up the new `*.test.mjs` files, and `uv run --frozen pytest -q`. Record both commands in `unit-test-instructions.md`.
- [x] Step 3: Server additions in `justchess/games.py`:
  - add `claimableDrawReason`;
  - remove the legacy snapshot fields;
  - update U1's tests that referenced the legacy fields;
  - add the reason assertions to `tests/core/test_games.py`.

  Run `uv run --frozen pytest tests/core -q`.
- [x] Step 4: Pure modules.
  - `view-model.js`: status (BR3.4 order), board options, claims (BR3.7), scoresheet and result (BR3.5), score per player (BR3.6), overlay title, subtitle and rematch button state (BR4.2, BR4.3), notices, the announcement sentence, `endTitle` and `resultText`.
  - `screen-state.js`: the reducer above.
  - `api.js`: request building and response mapping, injectable `fetch`, `X-Seat-Token` on state reads, never a token in a URL.
  - `live.js`: `backoffDelay` and the message handling, with injectable `WebSocket` and timers.
  - `seat-store.js`: storage with an in-memory fallback, plus `parseContinueFragment`.
  - `share.js`: `chooseShareMethod(navigatorLike)`, plus the action.
- [x] Step 5: Tests for the pure modules.
  - **View model** (`tests/js/view-model.test.mjs`), covering every status-line state and its order:
    - claim visibility, including the draw only on your move and the win only when the opponent is abandoned;
    - scoresheet rows and the newest move;
    - result glyphs;
    - score per player across a colour swap;
    - every end-reason title, plus the fallback for an unknown reason;
    - all four rematch states;
    - the announcement text.
  - **Screen state reducer** (`tests/js/screen-state.test.mjs`), covering every transition in the finding row above.
  - **API client** (`tests/js/api.test.mjs`):
    - 200;
    - 409 with a snapshot;
    - 400 and 403 messages;
    - network failure;
    - the header on state reads;
    - no token in any URL.
  - **Live client** (`tests/js/live.test.mjs`):
    - the backoff schedule;
    - hello with and without a token;
    - pings;
    - the visibility message;
    - seat-moved;
    - older snapshots ignored.
  - **Seat store** (`tests/js/seat-store.test.mjs`):
    - storage that throws;
    - set, get and remove;
    - fragment parsing.
  - **Share** (`tests/js/share.test.mjs`): the share sheet, the clipboard, and the field fallback.
- [x] Step 6: DOM modules.
  - `screens/lobby.js`.
  - `screens/game.js`:
    - the U2 board;
    - the status with its baize tone and dot;
    - the claim buttons and notices;
    - the settings sheet using U2's panel plus the continue-link row (BR1.6);
    - the scoresheet table, which collapses on a phone;
    - the score and the lessons `<details>` with its mount point and the BR3.8 banner.
  - `screens/overlay.js`.
  - `screens/win-sequence.js`: the king tips, the board dims, the result is inked and the winner's pieces glow, using Web Animations and finishing at once under reduced motion; it is cancelled when a new game starts.
  - `hooks.js`.
  - `app.js`: routing (`/` and `/r/{code}`, using pushState and popstate), redeeming the continue fragment and then `replaceState`, join, then state, then socket wiring, and the reducer driving the screens.
- [x] Step 7: Styles in `static/css/app.css`:
  - the top bar, at most 56 px;
  - the lobby;
  - the game grid: on a phone the board is full width minus 8 px gutters with its top at 72 px or less; from 1024 px it is 560–640 px in the left column with the panel on the right;
  - the status, scoresheet, score and overlay;
  - the notices.

  Use only U2 tokens: four button roles, the focus ring, and 44 px targets.
- [x] Step 8: The carried U2 contrast fix (above). Run `node --test tests/js/`.
- [x] Step 9: Frontend behaviour checks and integration tests (`tests/test_game_screen.py`):
  - `/` and `/r/ABC123` serve the new shell;
  - every script and stylesheet the shell references returns 200, and the module imports resolve, by statically scanning `import` paths;
  - `static/app.js` and `static/style.css` are gone;
  - a full HTTP flow (create, join, state with the header) returns a snapshot with `claimableDrawReason` and without the legacy fields.

  Then, if headless Chromium is available, run a two-context browser game: create, open the invite link in the second context, play Fool's mate, see "Checkmate" and the overlay in both, and press Play again in both to get swapped colours. The run uses a server started by the test on a free port with a temporary database, and is skipped with a reason when Chromium is missing.
- [x] Step 10: Delete the old client: `static/app.js` and `static/style.css`. Run `uv run --frozen pytest -q`.
- [x] Step 11: Documentation and traceability.
  - Update the README: remove the "old client won't work until U3" note and describe how to play.
  - Add module headers.
  - Write `source-manifest.json`, listing every file one by one, including the deletions and the U1 and U2 files touched. Leave `code-summary.md` and `traceability.json` to the orchestrator.

## Loop-back 1 repair (from Build and Test, 2026-11-13)

Build and Test ran the game screen in headless Chromium at 390 × 844 and found touch targets under 44 × 44 px (NFR6):
- all 64 board squares are 42.5 × 42.5 px, because the 374 px board frame keeps its desktop padding;
- the top-bar logo link is 28 px tall.

The full diagnosis is in `construction/build-and-test/test-results.md` under "Loop-back 1". Only this unit is reopened. Its earlier steps and files stay as they are.

- [x] Step 12: Phone-width touch targets in `static/css/app.css`.
  - Below 768 px, the game's board frame padding becomes 3 px in inside-label mode, so the squares are at least 46 px on a 390 px screen.
  - In frame-label mode, the frame padding is reduced so the squares are at least 44 px and the whole frame stays at least 374 px wide.
  - `home-link` gets a minimum hit area of 44 × 44 px, using padding and an inline-flex box, with the visible mark unchanged.
  - Nothing changes from 768 px up, and U2's `board.css` defaults are not edited.
- [x] Step 13: Tests.
  - `tests/test_accessibility_browser.py` (added by Build and Test) must pass. It covers targets of at least 44 px, square labels, and keyboard play at 390 px.
  - Extend the U3 layout assertions in `tests/test_game_screen.py`: at 390 px, squares are at least 46 px with inside labels, and at least 44 px with frame labels.
  - Run `uv run --frozen pytest -q` and `node --test tests/js/`.
  - Add `static/css/app.css`, `tests/test_game_screen.py` and `tests/test_accessibility_browser.py` to `source-manifest.json`, keeping every path already listed.

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

Inapplicable layers:
- **Data model and repository:** U3 adds no stored data. The seat lives in browser storage and is tested as business logic.
- **API / endpoint:** only the additive snapshot field, which Step 3 implements and tests.
