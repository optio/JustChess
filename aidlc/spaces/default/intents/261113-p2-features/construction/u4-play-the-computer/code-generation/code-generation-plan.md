# Code Generation Plan — u4-play-the-computer

## Sources
- The functional design in `construction/u4-play-the-computer/functional-design/`: `entities.md`, `rules.md` (BR1.1–BR1.6, BR2.1–BR2.2, BR3.1–BR3.6, BR4.1–BR4.3, BR5.1–BR5.6, BR6.1–BR6.2, BR7.1–BR7.2, BR8.1–BR8.4) and `functional-spec.md` (W1–W8, including the fixes from the review).
- `inception/units-generation/unit-of-work.md` (U4).
- Requirements FR1.5, FR6.1–FR6.9 and NFR1.
- ADR-001, ADR-002, ADR-005 and ADR-009.

## What changes
The work is brownfield.
- **Back end:**
  - new `justchess/engine.py` (Engine) and `justchess/computer.py` (ComputerOpponent, the level table, and the per-room reply and hint coordination);
  - changes to `rooms.py`, `games.py`, `api.py`, `live.py` and `summaries.py` (where needed).
- **Front end:**
  - new `static/js/computer.js`;
  - changes to `screens/lobby.js`, `screens/game.js`, `room-flow.js`, `api.js`, `app.js`, `view-model.js`, `live.js`, `board/` (the hint arrow) and `static/css/app.css`.

It uses the version 4 schema from U2, so there are no schema changes and no new settings.

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

The schema itself does not change (U2 built it). The data-access layer is the room and game functions in `rooms.py` and `games.py`. The business-logic layer is Engine and ComputerOpponent.

## Steps

- [x] **Step 1 — Structure.** Create skeletons with header comments for:
  - `justchess/engine.py` and `justchess/computer.py`;
  - `static/js/computer.js`;
  - a fake UCI engine script, `tests/fakes/fake_uci.py`. It is a small Python program speaking just enough UCI. Command-line flags make it answer, delay, crash, hang or return an illegal move.
- [x] **Step 2 — Runner check.** Confirm `uv run --frozen pytest -q tests/core/test_rooms.py` and `node --test tests/js/room-flow.test.mjs` run, and record the unit commands in `unit-test-instructions.md`.
- [x] **Step 3 — Rooms and games: implement** (BR3.1–BR3.4, BR3.6, BR4.1–BR4.3).
  - `rooms.py`:
    - `create_computer_room(conn, now, level, white_slot)` creates mode computer, the level, seat A with a token, and seat B with `is_computer` and no hash.
    - `join_room` refuses non-seat-A tokens in computer rooms with 409 "This room plays the computer".
    - `seat_presence` reports `computer` for seat B.
  - `games.py`:
    - `end_for(board, computer)` uses a claim-aware outcome only when `computer` is true, adding `threefold_repetition` and `fifty_moves`. `apply_move` takes a `computer` flag, and friend rooms are unchanged.
    - `takeback(conn, game, now, computer_to_move_without_reply)` removes one or two move rows, rebuilds the FEN by replay and bumps the version.
    - `resign(conn, game, slot, now)` ends the game with reason resigned.
    - `start_computer_rematch(conn, previous, now, colour)` starts the next game playing, with colours swapped or as chosen.
- [x] **Step 4 — Rooms and games: tests.**
  - `tests/core/test_computer_rooms.py` (8):
    - creation with White and with Black sets the correct seats and game state;
    - the computer seat has no hash and no token matches it;
    - join refused, while seat A rejoins;
    - the score is recorded against the computer;
    - a rematch swaps colours, and one with a colour keeps the chosen colour;
    - a rematch before the end gives 409;
    - presence is `computer`;
    - the mode route is refused.
  - `tests/core/test_takeback.py` (7):
    - two plies on the player's turn;
    - one ply on the computer's turn when no reply is in flight;
    - nothing to take back;
    - refused when the game is over;
    - a stale version;
    - the FEN, captures and version are correct after a takeback;
    - unlimited repeated takebacks.
  - `tests/core/test_computer_draws.py` (5):
    - threefold ends a computer game;
    - fifty moves ends a computer game;
    - a friend game is unchanged (it still needs a claim);
    - resign ends with the computer winning, and the score is recorded;
    - resign is refused in a friend room.
- [x] **Step 5 — Engine and ComputerOpponent: implement** (BR1.1–BR1.6, BR2.1–BR2.2).
  - `engine.py`, class `Engine`:
    - one python-chess async UCI process (`chess.engine.popen_uci`) with `Threads = 2` and `Hash = 64`;
    - `submit(board, skill, think, on_progress) -> Ticket` is synchronous. It returns a request id and the initial state, or raises Busy or Unavailable;
    - `await ticket.result()`, and `cancel(ticket)`;
    - a FIFO worker task, with queue positions reported through `on_progress`;
    - a cap of 32;
    - `queued_count()` for the hint threshold;
    - a timeout of think + 5 s, counted as a crash;
    - one restart, then unavailable with a reason;
    - the "starting" status until the process is open;
    - `start(path)` and `stop()` (quit, then kill after 2 s);
    - an injected process opener, so tests use the fake script.
  - The returned move is checked to be legal.
  - `computer.py`:
    - the `LEVELS` table and `reply_settings(level)` and `hint_settings()`;
    - `ComputerCoordinator`, which holds ReplyInFlight `{game_id, version, request_id}`, HintInFlight and RetryBackoff per room;
    - a strong-reference task set, and clearing in `finally` only when the request id matches.
- [x] **Step 6 — Engine and ComputerOpponent: tests.**
  - `tests/test_engine.py` (8), against the fake script:
    - FIFO order and positions;
    - one search at a time;
    - the cap gives Busy;
    - a crash fails the running request, restarts, and the queue continues;
    - a second crash makes the engine unavailable and fails every queued request;
    - a hang past think + 5 s is handled as a crash;
    - an illegal move is a failure;
    - `stop()` fails queued requests and ends the process.
  - `tests/test_computer.py` (6):
    - the level table, and hint settings at full strength for 0.5 s;
    - the coordinator clears only its own request id;
    - the flag is cleared after an exception and after cancellation;
    - RetryBackoff blocks for 5 s;
    - a flag from an earlier game does not block the current game.
  - `tests/test_engine_real.py` (2):
    - a real Stockfish reply at Maximum within 3 s;
    - a hint returns a legal move.

    Both are skipped with a reason when no Stockfish binary is found. The first also serves as the NFR1 timing check when run on the Pi.
- [x] **Step 7 — API, live updates and lifecycle: implement** (BR3.1–BR3.6, BR4.1–BR4.3, BR5.1–BR5.6, BR6.1–BR6.2, BR7.1–BR7.2, BR1.5).
  - **Lifecycle:** Engine is started in the app lifespan after `_prepare_stockfish` and stopped on shutdown. An engine factory is injectable in `create_app` for tests.
  - **`GET /api/engine`** keeps `available`, `path_source` and `version`, and adds `reason`.
  - **`POST /api/rooms`:**
    - `kind: computer` with `level` and `colour` is validated (400). Random uses `secrets.choice`.
    - It is rate-limited at 10 per minute per address (429) and refused with 503 when the engine is unavailable.
    - When the computer is White, the reply is asked for.
  - **Move route:** in computer rooms it gives 503 while the engine is unavailable. After the commit it asks for the reply (W2) and returns the snapshot with `computer`. No alerts are sent for computer rooms.
  - **New routes:**
    - `POST …/computer-move` (30 per minute);
    - `POST …/takeback`;
    - `POST …/hint` (20 per minute; refused at 16 or more queued; cancelled on client disconnect);
    - `POST …/resign`.
  - **Changed routes:**
    - rematch handles computer rooms, with an optional colour, replaces the reply flag, and asks for the reply when the computer is White;
    - claim-draw and claim-win give 409 in computer rooms.
  - **Reply completion:** under the room lock it checks game id, version, status, turn and legality, then applies the move or discards it. It broadcasts, and on failure sets the backoff.
  - **Snapshot `computer`:** `{state, queuePosition, reason, level, available}`, or `null` for friend rooms.
  - **`live.py`:** `send_event(code, message)` sends `{type: computer, …}` and `{type: takeback}` to the room's sockets.
  - **Rate limits** reuse `ratelimit.RateLimiter` and `client_address`.
  - Tokens are never logged.
- [x] **Step 8 — API: tests.**
  - `tests/core/test_computer_api.py` (8):
    - create a computer room over HTTP, play a move, and the reply arrives (fake engine);
    - 400 for a bad level or colour;
    - 503 when the engine is unavailable (create and move);
    - the hint flow and its errors (409 on the computer's turn, 409 when a hint is pending, 503 at the queue threshold);
    - takeback and resign over HTTP;
    - 409 for claims in computer rooms;
    - `computer` in the snapshot and in the socket events;
    - no token appears in logs (`caplog`).
  - `tests/core/test_reply_race.py` (6):
    - a stale reply is discarded after a takeback (the takeback waits for the flag to clear);
    - a reply is discarded after a resign;
    - resign then rematch with the computer White while the old reply is in flight: the new game gets its own reply, and the old one is discarded without clearing the new flag;
    - resume asks once, and a second call returns the state;
    - a failed reply leaves the game unchanged and sets the backoff;
    - the reply after a server-restart-like reset is asked again.
  - `tests/test_engine_rate_limit.py` (3):
    - 429 on computer room creation;
    - 429 on hints;
    - 429 on computer-move.
  - Every engine in these tests is the fake one, injected through `create_app`. No test touches `justchess.sqlite3`.
- [x] **Step 9 — Front end: implement** (BR3.5, BR8.1–BR8.4).
  - `computer.js` (pure logic):
    - level names;
    - status text for each state;
    - which buttons show and are enabled (takeback, hint, resign);
    - the retry policy (3 tries, 5 s apart);
    - the hint arrow geometry from two squares and the board orientation.
  - `screens/lobby.js`: the "Play the computer" panel.
    - Colour and level radio groups, defaulting to Random and Casual, remembered in local storage inside try/catch.
    - The unavailable state, read from `/api/engine`.
    - Play applies BR3.5 through `room-flow.js`: reopen the saved seat for the level, rematch if finished, otherwise create.
  - `screens/game.js`:
    - the "Computer · level" label;
    - the thinking, queued and unavailable statuses;
    - Take back, Hint, and Resign with an in-page confirm dialog;
    - the hint arrow, drawn as an SVG overlay in `board/`;
    - the result card with Play again;
    - the score line "This level: You n · Computer n · Draws n";
    - Share and invite hidden in computer rooms;
    - `computer-move` called on open when the computer is to move and the state is idle, within the retry cap, then "The computer didn't answer." with Try again.
  - `live.js` handles the `computer` and `takeback` events.
  - `seat-store` saves kind computer with the level.
  - The blunder check runs unchanged.
- [x] **Step 10 — Front end: tests.**
  - `tests/js/computer.test.mjs` (8):
    - level names;
    - status text for queued, thinking and unavailable;
    - takeback enablement (player's turn, at least one player move, idle, playing);
    - hint enablement;
    - resign enablement;
    - the retry cap;
    - the arrow geometry for White and Black orientation;
    - the score line.
  - `tests/js/computer-panel.test.mjs` (4):
    - choices are remembered and restored;
    - the defaults are Random and Casual;
    - an unavailable engine disables Play and shows the reason;
    - Play picks reopen, rematch or create from the saved seats.
  - A browser test, `tests/test_u4_computer_browser.py` (1): it creates a Beginner game as White with the fake engine, makes a move, sees the computer's reply and the thinking status, takes back, gets a hint arrow, resigns, and sees the result card. It is skipped when Chromium is missing.
  - Then run the full suite.
- [x] **Step 11 — Configuration.** There are no new environment settings. The README gains a "Play the computer" section covering:
  - the levels;
  - the engine queue and its limits;
  - what "unavailable" means and how to recover (restart the app);
  - the per-address limits;
  - the fact that `JUSTCHESS_TRUSTED_PROXIES` also applies to these limits.
- [x] **Step 12 — Documentation and traceability.** Write `code-summary.md`, `source-manifest.json` and `traceability.json`.

## Requirement-to-step map

| ID | Steps |
|---|---|
| FR1.5 | 9, 10 |
| FR6.1 | 3, 4, 7, 8, 9, 10 |
| FR6.2 | 5, 6, 7, 8 |
| FR6.3 | 3, 4, 7, 8, 9, 10 |
| FR6.4 | 5, 6, 7, 8, 9, 10 |
| FR6.5 | 3, 4, 7, 8, 9, 10 |
| FR6.6 | 9 (the existing check-move flow, covered by the browser test) |
| FR6.7 | 5, 6, 7, 8, 9, 10 |
| FR6.8 | 3, 4, 7, 8, 9 |
| FR6.9 | 3, 4 |
| NFR1 | 5, 6, 7, 8, 11 |

## Constraints
- Tokens never appear in URLs, logs or error bodies.
- Only boards replayed from stored moves reach the engine.
- No test touches `justchess.sqlite3`.
- The unit tests use the fake engine. Only `test_engine_real.py` uses Stockfish.
- Files are written with file tools.
