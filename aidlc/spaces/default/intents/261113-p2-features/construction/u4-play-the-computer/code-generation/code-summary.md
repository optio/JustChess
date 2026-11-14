# Code Summary — u4-play-the-computer

All 12 plan steps are done. The build wrote the code and tests for steps 1–11 and the README part of step 12. This summary, `source-manifest.json` and `traceability.json` complete step 12.

## Files

**Created**
- `justchess/engine.py`: one async UCI Stockfish process with Threads = 2 and Hash = 64.
  - A FIFO queue capped at 32, which reports queue positions.
  - Requests are submitted synchronously and return a ticket.
  - A search that runs 5 s past its think time counts as a crash. The engine restarts once, then reports unavailable.
  - It reports "starting" until the process is up, and is stopped with a quit followed by a kill.
  - The engine's move is checked to be legal before use.
- `justchess/computer.py`: the level table and the hint settings, and the `ComputerCoordinator`.
  - The coordinator tracks the reply in flight by game id, version and request id, plus the hint in flight and a 5 s retry backoff.
  - Its tasks are held by strong references, and the in-flight flag is cleared in a `finally`, only by the request that set it.
- `static/js/computer.js`: level names, status text, which buttons are enabled, the retry cap, the arrow geometry and the score line.
- `static/js/board/hint-arrow.js`: the SVG hint arrow.
- Test helpers in `tests/fakes/`: a fake UCI engine script, engine factories and computer room and API helpers.
- 12 test files (listed under Tests).

**Modified**
- Back end:
  - `justchess/api.py`: engine lifecycle in the app lifespan, and `/api/engine` gains `reason`.
    - Computer room creation; the move route asks for the computer's reply.
    - New routes: computer-move, takeback, hint and resign. The rematch route handles computer rooms.
    - Claims are refused in computer rooms, and per-address limits apply.
    - The snapshot gains a `computer` field, and the live events are sent.
  - `justchess/rooms.py`: computer room creation, join refused, presence `computer`.
  - `justchess/games.py`: automatic threefold and 50-move draws in computer rooms only, takeback, resign, computer rematch with an optional colour, and the snapshot's `computer` field.
  - `justchess/live.py`: `send_event`.
- Front end:
  - `static/js/screens/lobby.js`: the "Play the computer" panel.
  - `static/js/screens/game.js`: the computer controls and states.
  - `static/js/screens/overlay.js`: hides "Share result" in computer rooms.
  - `room-flow.js`, `api.js`, `app.js`, `live.js`, `view-model.js`, `app.css`.
- Docs: `README.md` gains a "Play the computer" section and an updated Stockfish section.
- Existing tests changed because the approved design changes their behaviour:
  - `tests/test_stockfish_install.py`: `available` now means the process is running, and the body gains `reason`.
  - `tests/js/view-model.test.mjs`: `resigned` is now a known end reason, so the unknown-reason example uses `timeout`.

There are no schema changes and no new settings. `summaries.py` needed no change.

## Deviations from the plan
1. **Repetition and 50-move draws** count the position on the board (`is_repetition(3)`, `is_fifty_moves()`). They do not use `outcome(claim_draw=True)`, which would also end the game when the next move merely could repeat. This matches the intent of BR4.2.
2. **Snapshot `computer.message`** is an extra field. It carries the busy text in the HTTP answer right after a busy refusal (W2 step 6).
3. **Function signatures:**
   - `games.takeback` and `games.resign` take an optional `version`, and `takeback` also takes `player_slot`.
   - New helpers: `create_computer_game`, `white_slot_for` and `require_playing`.
4. **Where some planned tests sit:**
   - The mode-route refusal is tested at `rooms.set_mode`.
   - Fifty moves is tested through `games.end_for` on a FEN.
   - Resign refused in a friend room is tested over HTTP in step 8.
5. **Accessibility fix:** the radio inputs in the new panel were under the 44×44 px minimum. Each input now covers its whole label, and the browser test checks the touch targets at phone width.
6. **Extra files:** `board/hint-arrow.js` and the change to `overlay.js`. `seat-store.js` needed no change.

## Changes the person asked for after the review (message b695c7bc)
The request: "Beginner level is still too hard for some. make all levels easier. Also move this and all other gameplay settings to a yaml file for easy tuning."

- **Weaker levels.** Each level now has a skill, a think time, an optional depth limit and a random-move chance. The random move is chosen on the server with `SystemRandom`, and the chooser can be injected for tests.

  | Level | Skill | Depth | Think | Random |
  |---|---|---|---|---|
  | beginner | 0 | 1 | 0.05 s | 0.35 |
  | casual | 2 | 3 | 0.1 s | 0.15 |
  | club | 6 | 6 | 0.3 s | 0.05 |
  | strong | 11 | 10 | 0.6 s | 0 |
  | maximum | 16 | — | 1.0 s | 0 |

  Hints are unchanged (skill 20, 0.5 s).
- **`gameplay.yaml` at the repo root**, loaded by `justchess/gameplay.py`.
  - Every key has a comment.
  - Values are validated. A bad key stops start-up with an error that names it.
  - `JUSTCHESS_GAMEPLAY_FILE` can point to another file. If the shipped file is missing, built-in defaults are used.
  - The file holds the levels, hint, queue cap, hint threshold, overrun grace, restarts, retry backoff, the per-address computer limits, the join-request limit, lifetime, decline block and address cap, the claim-win away time, the idle-room deletion age, and the blunder-check budget.
  - Client-side timings reach the page as a JSON block in the app shell, read by `static/js/gameplay.js`.
- **Review finding fixed.** The retry backoff is now set only when the failed reply's game is still the current game.
- **Files created:** `gameplay.yaml`, `justchess/gameplay.py`, `static/js/gameplay.js`, `tests/test_gameplay.py`, `tests/js/gameplay.test.mjs`.
- **Files modified:** `engine.py`, `computer.py`, `rooms.py`, `housekeeping.py`, `ratelimit.py`, `analysis.py`, `templates/index.html`, `board/board.js`, `.env.example`, the README, and the tests that pinned the old level numbers.
- **Result:** 354 passed and 1 skipped (pytest); 210 passed (node).

## Tests
| File | Tests | Result |
|---|---|---|
| tests/core/test_computer_rooms.py | 9 | passed |
| tests/core/test_takeback.py | 7 | passed |
| tests/core/test_computer_draws.py | 5 | passed |
| tests/test_engine.py | 9 | passed |
| tests/test_computer.py | 7 | passed |
| tests/test_engine_real.py | 2 | passed, using the real Stockfish sf_19 on the Pi (NFR1: a Maximum reply in under 3 s) |
| tests/core/test_computer_api.py | 9 | passed |
| tests/core/test_reply_race.py | 6 | passed |
| tests/test_engine_rate_limit.py | 3 | passed |
| tests/js/computer.test.mjs | 10 | passed |
| tests/js/computer-panel.test.mjs | 4 | passed |
| tests/test_u4_computer_browser.py | 1 | passed in headless Chromium, using the fake engine |

| Run | Result |
|---|---|
| Baseline `uv run --frozen pytest -q` | 276 passed, 1 skipped |
| Full `uv run --frozen pytest -q` after the build | 334 passed, 1 skipped (the existing push end-to-end skip) |
| JS suite | 207 passed |

Every test that was written was also run.
