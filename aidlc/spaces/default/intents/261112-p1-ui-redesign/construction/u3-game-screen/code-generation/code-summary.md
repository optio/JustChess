# Code Summary — u3-game-screen

## Result

- `node --test tests/js/`: **71 passed** (33 before this unit).
- `uv run --frozen pytest -q`: **56 passed** (48 before this unit). This includes a two-player game played in headless Chromium through the real interface. The players create a room, open the invite link, play Fool's mate, see the overlay on both sides, and play again with colours swapped. The same run checks the layout rules:
  - phone top bar 56 px or less;
  - phone board top 72 px or less;
  - phone board 374 px or wider;
  - no horizontal scroll on a phone;
  - desktop board 560–640 px.

## Files

| Area | Files |
|---|---|
| Shell | `templates/index.html` (new shell) |
| Modules | `static/js/app.js`, `api.js`, `live.js`, `seat-store.js`, `view-model.js`, `screen-state.js`, `share.js`, `hooks.js` |
| Screens | `static/js/screens/lobby.js`, `game.js`, `overlay.js`, `win-sequence.js` |
| Styles | `static/css/app.css`; `static/css/tokens.css`, with the carried label-contrast fix |
| Server | `justchess/games.py`: adds `claimableDrawReason` and removes the legacy snapshot fields |
| Tests | `tests/js/{view-model,screen-state,api,live,seat-store,share}.test.mjs`, an extended `contrast.test.mjs`, `tests/test_game_screen.py`, and updated `tests/core/test_games.py`, `test_api.py`, `test_live.py` |
| Removed | `static/app.js`, `static/style.css` |
| Docs | README: how to play, and the work-in-progress note removed |

## Decisions made during the build

- **Snapshot ordering:** a snapshot with the same game and version is applied. Presence and rematch-lapse broadcasts don't bump the version, so only strictly older snapshots are ignored.
- **Board position:** the board is told the position only when it actually changed. A move that is still waiting after the server answers is treated as refused, so input never stays locked.
- **Highlight contrast:** a new `--hl-last-tint` uses the darkened brass #8A6A22 at 38%. Labels under the last-move highlight are now at least 4.73:1, up from 3.32:1.
- **Move hook:** if `beforeMove` throws, the move is refused with "Couldn't check that move. Try again." It fails closed.
- **Browser test:** it drives Chromium through its debugging protocol, using the `websockets` package uvicorn already installs, so nothing new was installed. It skips with a reason when Chromium is missing; `JUSTCHESS_CHROMIUM` picks the binary.
- **Small additions beyond the spec:**
  - the reconnecting view adds a second line, "Your game is safe. Trying again…";
  - a 409 on a move applies the snapshot and shows the message;
  - the empty lessons drawer shows a placeholder until U6;
  - the lobby leaves out "Learn an opening" until U6.

## Loop-back 1 repair (from Build and Test)

At 390 × 844 in headless Chromium, the board squares and the logo link were under the 44 px touch target. The fix is a phone-only block in `static/css/app.css`, active below 768 px:

| Element | Change | Result |
|---|---|---|
| Board frame, inside labels | 2 px frame, 1 px brass inlay, no inlay padding | 46 × 46 px squares on a 374 px frame |
| Board frame, frame labels | Padding `2px 2px 16px 16px` | 44.25 × 44.25 px squares on a 374 px frame |
| Lobby board | Same slimmer frame | 46 px squares |
| `home-link` | 8 px padding inside a negative margin | 44 × 44 px tap area; the mark stays where it was |

Desktop is unchanged: the frame padding is still 6 px.

Tests added: square-size and logo-link-size checks in `tests/test_game_screen.py`. Build and Test's `tests/test_accessibility_browser.py` now passes. Its Enter key events now carry `"\r"`, as a real key press does.

Totals: 177 Python tests passed (1 skipped: the push run this Chromium build cannot perform) and 130 Node tests passed.

## Open points

- **50-move claim reason:** tested on a position built directly, not on 100 replayed moves.
- **U5:** must register its notifications hook at startup, because the game screen reads it when it is created.
- **U1's BR2.1 check order:** U3 handles either order. Updating the written contract to match the code is left to Build and Test.
- **Git index:** during the build, `git rm --cached` was run on the two deleted files by mistake and was undone at once. Nothing is staged now.
