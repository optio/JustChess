# Code Summary — u6-training

## Result

- `node --test tests/js/`: **100 passed**. There were 71 before this unit.
- `uv run --frozen pytest -q`: **90 passed**. There were 56 before this unit. The total includes a headless Chromium run through the Italian Game lesson. That run covers the walkthrough, a legal move that leaves the line, going back to the line, the trainer's replies, and finishing the line.
- Unit command `uv run --frozen pytest tests/test_lessons.py tests/test_lessons_api.py -q`: **33 passed**.

## Files

| Area | Files |
|---|---|
| Lessons | `lessons/italian.yaml`, `lessons/monte-carlo.yaml` |
| Loader | `justchess/lessons.py` |
| Routes | `justchess/api.py`: `/api/lessons`, `/api/lessons/{id}`, `/api/position/move`, and the `/learn` shell; the inline lesson list is removed |
| Trainer | `static/js/training/trainer-state.js`, `arrow.js`, `lessons-api.js`, `trainer.js`; `static/css/training.css` |
| Carried from U3 | `static/js/room-flow.js`, the failure-path helper used by `app.js` |
| U2 and U3 touch points | `board/board.js` and `interaction.js` (`onRejectedTap`, `hintSquare`); `board.css` and `tokens.css` (hint ring, arrow tokens); `app.js`, `hooks.js`, `screens/game.js` and `screens/lobby.js` (drawer mounting, `/learn`, "Learn an opening") |
| Dependency | `pyyaml` added as a direct dependency |
| Tests | `tests/test_lessons.py` (11), `tests/test_lessons_api.py` (22), `tests/js/trainer-state.test.mjs` (12), `arrow.test.mjs` (3), `board-rejected-tap.test.mjs` (6), `room-flow.test.mjs` (7); extended `contrast.test.mjs` and `test_game_screen.py` |
| Docs | README section "Opening lessons", which covers how to add a lesson and `JUSTCHESS_LESSONS_DIR` |

## Decisions made during the build

- **Arrow colour.** New `--arrow` token: #785C1E in light mode and #D3AE5C in dark mode. Its outline uses `--arrow-edge` (paper). The plan's #8A6A22 reached only 2.80:1 on Rosewood light squares. The new colour clears 3:1 against all six squares in both themes.
- **Loader safety.**
  - Folders are only listed, and files are opened with `O_NOFOLLOW`. Files over 64 KB, symlinks and anything that is not a regular file are skipped.
  - YAML is read with `safe_load` only.
  - Unknown fields are refused, so typos are reported.
  - Each alternative must be legal and different from the taught move.
  - SAN is normalised.
  - When ids clash, the first file by name wins.
- **Reload.** The loader reloads when file names, sizes or times change, and swaps the new catalog in under a lock.
- **Free-play route.** It checks the move format and the position before playing. Its outcome has no game history, so repetition draws are never reported.
- **Trainer timers.** Timers and requests are cancelled whenever the trainer leaves the state that started them, and late timers are ignored.
- **`onRejectedTap`.** It fires only when you tap an empty square, or an opponent piece that is not a target. It never fires when you deselect, press Escape, cancel a drag, reselect another of your own pieces, or the board is locked or waiting.
- **Drawer.** The trainer is mounted when the drawer first opens and removed when the game screen is torn down.

## Open points

- The demo page's self-check total doesn't count the arrow pairs, though failures in them still show.
- The drawer board's 300 px minimum means a sideways scroll on phones narrower than about 332 px.
- The U1 BR2.1 written check order is still left for Build and Test.
