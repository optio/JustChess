# Code Summary — u4-blunder-warnings

## Result

- `node --test tests/js/`: **115 passed** (100 before this unit).
- `uv run --frozen pytest -q`: **121 passed** (90 before this unit). This includes two headless Chromium runs:
  - the Fool's mate game with "Warn me before blunders" turned off;
  - a new dialog run: g4 shows "This allows checkmate", Escape puts the pawn back, and "Play g4 anyway" sends the move.
- Unit command: **30 passed**.
- Timing on the Pi, measured over the full HTTP round trip, 5 runs each:

  | Position | Median | Maximum | Budget |
  |---|---|---|---|
  | Busy middlegame, where the sweep runs | 4.5 ms | 4.9 ms | 300 ms |
  | Every move allows mate | 6.2 ms | 7.1 ms | 300 ms |

  BR2.2's 300 ms is a budget derived from NFR5's 1-second delivery target. It is not an NFR on its own.

## Files

| Area | Files |
|---|---|
| Analysis | `justchess/analysis.py`: `analyse()` and `BlunderWarning` |
| Route | `justchess/api.py`: `POST /api/rooms/{code}/check-move`. `justchess/games.py`: `parse_legal_move` and `require_move_turn` helpers |
| Client | `static/js/blunder.js` (dialog text and hook), `static/js/screens/blunder-dialog.js`, and `static/js/api.js` (`checkMove` with an abort signal) |
| Widened hook | `static/js/hooks.js`, `static/js/room-flow.js` (`applyRefusal`), `static/js/app.js` (hook wired at startup) |
| Styles | `static/css/app.css` |
| Tests | `tests/test_analysis.py` (18), `tests/test_check_move_api.py` (12), `tests/js/blunder.test.mjs` (12); extended `room-flow.test.mjs`, `api.test.mjs` and `test_game_screen.py` |
| Docs | A README line under "Implemented" |

## Decisions made during the build

- **Analysis:**
  - The mate-in-one search only tries replies that give check.
  - Exchanges are worked out with legal captures only, least valuable attacker first. A pawn that captures onto the last rank counts as promoting.
  - "Defended" means at least one legal recapture exists.
  - When the mover is in check before the move, the "before" sets are empty.
  - For a promoted piece, the value it is judged against is the captured piece's value plus the promotion gain.
  - The no-alternative sweep runs once per warning kind, tries quiet moves first, and stops after 250 ms.
- **Route:** it follows U1's actual check order (seat, playing, version with a 409 carrying the snapshot, then turn) under the room lock, on a read-only connection. Replay, the legality check (400) and the analysis run outside the lock in a worker thread.
- **Hook:** it accepts true, false, or `{allow:false, message?, snapshot?}`. On 409 the result carries both the snapshot and the message. Timeout (2.5 s), network errors, 404, 413, 422, 429, 5xx and malformed replies all let the move through. 400 and 403 return their message. The hook never throws.
- **Dialog:** `alertdialog`, labelled and described. It catches Escape before the board does, its buttons are 44 px, and focus returns to the from-square. It closes when a newer snapshot arrives. The body spells the move out in words; the confirm button uses SAN ("Play Ba3 anyway").
- **Existing test changed:** the Fool's mate browser run now turns the setting off for White first. This also covers the "setting off, no dialog" case.

## Open points

- The route timing case for "every move allows mate" ends in check, with only 2 legal moves. The version not in check is covered at the analysis level only.
- U1's written BR2.1 check order still needs to be brought in line with the code in Build and Test.
