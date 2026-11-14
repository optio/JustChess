# Code Summary — u1-core-game

## Result

- Whole suite `uv run --frozen pytest -q`: **46 passed** (it was 8 before this unit).
- Unit command `uv run --frozen pytest tests/core -q`: **38 passed**, and it passed 5 more runs in a row, which covers the race and timeout tests.
- `tests/test_stockfish_install.py` still passes, now run against the new app.

## Files

| File | Purpose |
|---|---|
| `justchess/__init__.py` | Package docstring; shared `DomainError(status, message, **extra)` |
| `justchess/db.py` | Schema v2, `connect()`, `transaction()` (`BEGIN IMMEDIATE`), startup check (BR4.1); a newer schema fails startup instead of being moved aside |
| `justchess/rooms.py` | Codes, seats, hashed tokens with constant-time compare, continue tokens (10-minute expiry), presence and abandonment, score, rematch, delete-by-room, idle listing (BR1.x, BR3.x) |
| `justchess/games.py` | Board replayed from stored moves; move checks (playing → version → side → legality); automatic ends; claimable draws; claim win; per-viewer snapshot (BR2.x) |
| `justchess/live.py` | Per-room socket hub; hello handshake; 10 s receive timeout; presence broadcasts; per-socket snapshots; `seat-moved`; 1 KB message limit |
| `justchess/housekeeping.py` | Hourly and startup 30-day cleanup, one transaction per room; hook list for U5 (BR4.2) |
| `justchess/security.py` | Origin middleware and streamed 4 KB body limit (BR4.3) |
| `justchess/api.py` | `create_app()`, all routes in the plan, per-room `asyncio.Lock` plus transaction, error table, lifespan (database, housekeeping, Stockfish) |
| `app.py` | Thin entry point |
| `templates/index.html` | HTMX script tag removed |
| `README.md` | `JUSTCHESS_DB` and `JUSTCHESS_ORIGIN`, single-process rule, fresh database on upgrade, limits, note that the old client won't work until U3 |
| `tests/core/` | `conftest.py`, plus tests for the database (7), Rooms (9), Games (8), API (8) and live updates (6) |

## Decisions made during the build

- The snapshot keeps the legacy flat `moves` list. The numbered list is `moveList`. The new fields are `game`, `endReason`, `result`, `lastMove`, `version`, `claimableDraw`, `seats`, `score`, `rematch`, `slot`, `colour` and `legalMoves`.
- The version is checked before the turn, so whoever loses a race always gets 409 with the latest snapshot. Every 409 from a room action carries a `snapshot`.
- `POST /api/rooms` returns 201 with `Location`. Running out of codes returns 503. A move on a game still waiting for an opponent returns 409 "Waiting for an opponent".
- Rematch has three outcomes: recorded, unchanged (a repeat request) and start. "Lapsed" is computed when read, never stored.
- Presence is one of `empty`, `connected`, `away` or `abandoned`. `lastSeenAt` is written at most once a minute.
- Socket close codes: 4408 timeout, 1009 message too large, 1003 bad JSON, 1008 refused, 1011 database error.

## Open points for later units

- **U3 client:** send the seat token only in the `X-Seat-Token` header. A token put in a query string would show up in uvicorn's access log.
- The 50-move claim is implemented but has no test of its own. Insufficient material is tested on a position set up directly.
- A validation failure returns FastAPI's default 422, which the spec's error table doesn't list.
- When `app.py` changed, the running dev server reloaded and moved the old database to `justchess.sqlite3.old`, as planned (BR4.1).
