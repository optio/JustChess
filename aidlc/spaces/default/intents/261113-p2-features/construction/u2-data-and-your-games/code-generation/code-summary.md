# Code Summary — u2-data-and-your-games

All 12 plan steps are done. Steps 1–11 were done by the build; step 12's docstrings were too, and this summary and the traceability files finish it.

## Files

**Created**
- `justchess/summaries.py`: the read model behind `POST /api/rooms/summaries`.
  - Body validation, with the fixed 400 `{"error":"bad_request","detail":"Invalid summary request"}`.
  - Deduplication by (code, token).
  - One rolled-back read transaction, with a constant-time comparison of token hashes.
- `static/js/your-games.js`: `seatsToSend`, `reconcile`, `filterAndSort`, `rowModel`, `staleRowModel`, `relativeTime`, `thumbnailSquares`.
- `tests/core/test_summaries.py` (10 tests), `tests/js/your-games.test.mjs` (8), `tests/test_u2_your_games_browser.py` (1).

**Modified**
- `justchess/db.py`:
  - `SCHEMA_VERSION = 4`, with a single schema script; the version-2 upgrade path is removed.
  - At start-up: version 4 is kept; a newer version refuses to start; anything else goes to `.old` and is created fresh; a failed rename stops start-up.
- `justchess/rooms.py`: modes (waiting, then online on join), `computer_level`, `is_computer`.
- `justchess/games.py`: capture info is stored on each move; the snapshot gains `mode`, `computerLevel` and `lastCapture`.
- `justchess/security.py`: a per-path body limit, 8 KB for the summaries route only.
- `justchess/api.py`: the summaries route, plus `mode`/`computer_level` passed into the snapshot.
- `justchess/__init__.py`: docstring only.
- `static/js/seat-store.js`: `kind`, `computerLevel`, `savedAt`, `validSeats()`, `remove()`.
- `static/js/api.js`: `fetchSummaries`.
- `static/js/screens/lobby.js`: the new headline, the "Train" button, and the Your games panel (Loading, Listed, Stale, Empty), refreshed on load, on focus and every 60 s.
- `static/js/app.js`: wiring for the panel.
- `static/css/app.css`: an appended section for the panel; U1's rules are untouched.
- Tests: `tests/core/test_db.py` rewritten for version 4; `test_rooms.py` +2, `test_games.py` +5, `tests/js/seat-store.test.mjs` +2.
- `README.md`: the database note now describes version 4 and the move to `.old` (ADR-010).

## Deviations from the plan
1. **Upgrade tests.** The version-2 upgrade tests were in `tests/core/test_db.py`, not in `test_notifications.py`, so they were replaced there by move-aside tests. `test_notifications.py` is unchanged.
2. **More database tests:** 10 instead of 8. The failed rename and the version 2 and version 3 cases are tested separately.
3. **`RoomSummary` gains `endReason`.** The meta line in BR3.2, "Ended … · reason", needs it.
4. **`reconcile` takes the sent seats as well.** The summaries carry no tokens, so answers are paired with seats by position. If they don't line up, nothing is dropped.
5. **The 30 s cap lets more requests through.** Besides Retry, it also allows a request for a newly saved seat or an empty panel. The last rows are kept across lobby rebuilds, so going back to the main screen is never blank.
6. **The hero board is gone from the main screen.** The decorative starting-position board was removed, and the list takes its column, as in mockup Screen 1.
7. **The pill reads "Their move".** There are no player names to put in it.

## Tests
| Command | Result |
|---|---|
| Baseline `uv run --frozen pytest -q` | 189 passed, 1 skipped |
| `uv run --frozen pytest -q tests/core/test_db.py tests/core/test_rooms.py tests/core/test_games.py tests/core/test_summaries.py tests/test_notifications.py tests/test_u2_your_games_browser.py` | 87 passed |
| `node --test tests/js/your-games.test.mjs tests/js/seat-store.test.mjs` | 15 passed |
| `node --test tests/js/` | 166 passed |
| `uv run --frozen pytest -q` (full) | 211 passed, 1 skipped (push end-to-end test, unchanged: this Chromium cannot subscribe to a push service) |

Every test written was run, and no test touched the real `justchess.sqlite3`.
