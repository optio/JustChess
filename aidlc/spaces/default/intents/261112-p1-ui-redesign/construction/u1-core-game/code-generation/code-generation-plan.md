# Code Generation Plan — u1-core-game

## Summary

- Builds: the `justchess/` backend package with rooms and hashed seats, games with full chess rules, draw claims, rematch and score, live updates with presence, cleanup and a fresh database
- Touches: new `justchess/` package (db, rooms, games, live, housekeeping, api); `app.py` becomes a thin entry point; `templates/index.html` (HTMX tag removed); new `tests/core/`; `stockfish_install.py` and `/api/engine` kept
- Tests: about 40 pytest tests (unit tests per component, plus API and WebSocket integration tests through FastAPI's TestClient)

## Inputs

- Functional design for this unit: `construction/u1-core-game/functional-design/functional-spec.md`, `rules.md` (BR1.1–BR4.4) and `entities.md`.
- `inception/units-generation/unit-of-work.md` (U1) and `inception/requirements-analysis/requirements.md`.
- Current code: `app.py` and `stockfish_install.py`.

## Design review findings resolved in this build

The functional design review (advisory, NOT-READY) raised these points. The build settles each one as follows:

| Finding | Build decision |
|---|---|
| Repetition history (Major) | The board is always rebuilt from the standard starting position by replaying the stored `Move.uci` list in ply order. `Game.fen` is a cache, used only for display and fast reads, never to rebuild the board for rules. Fivefold repetition, threefold repetition and the 50-move rule are evaluated on the replayed board. A test reaches repetition through stored moves. |
| Concurrency (Major) | Every state-changing use case (create, join, move, claim draw, claim win, rematch, continue-link redeem) runs under a per-room `asyncio.Lock`, inside one SQLite transaction opened with `BEGIN IMMEDIATE`. A loser gets a 409 with the latest snapshot, never a 500. The app runs as one process (stated in the README). Race tests cover concurrent moves, joins and rematch requests. |
| State read (Major) | `GET /api/rooms/{code}` reads the seat token from the `X-Seat-Token` header only. A token in the query string is ignored and never logged. With no token, or an invalid one, the viewer gets a watcher snapshot (no slot or colour, no legal moves). An unknown room returns 404. |
| Per-viewer snapshot | Broadcast builds the snapshot per socket from that socket's identity (seat A, seat B or watcher). Legal moves go only to the seat whose turn it is. A test checks a seat and a watcher in the same room. |
| Disconnect detection | Each socket has a 10 s receive timeout (the client pings every 5 s), so a disconnect is detected within 10 s. `lastSeenAt` is written at most once a minute per seat; 24 h abandonment needs no finer precision. |
| Continue token | Expires 10 minutes after it is issued (`continueExpiresAt` stored with the hash). Sockets bound to the old seat token are told `seat-moved` and become watchers. Tests cover expiry and rebinding. |
| Limits and origin | The body limit (4 KB) is enforced by a middleware that counts streamed bytes, including chunked requests. WebSocket messages over 1 KB close the socket (code 1009). The expected origin is `JUSTCHESS_ORIGIN` when set; otherwise the request's `Host` with the `X-Forwarded-Proto` scheme when present, else the request scheme. |
| Version increments | Any accepted change increments `version` exactly once, including a move that ends the game. A repeated rematch request by the same seat is idempotent. "Lapsed" is computed, never stored: a returning seat sees the request as pending again. |
| Push subscriptions in cleanup | Housekeeping takes optional per-room cleanup hooks. U5 registers its delete-by-room hook there; U1 ships the hook list empty. |

## Steps

- [x] Step 1: Project structure. Create the `justchess/` package with `__init__.py`, `db.py`, `rooms.py`, `games.py`, `live.py`, `housekeeping.py`, `api.py` and `security.py` (origin and size middleware). `app.py` becomes `from justchess.api import create_app; app = create_app()`. Keep `stockfish_install.py` unchanged and call it from the new lifespan (FR9.1). Remove the HTMX `<script>` from `templates/index.html`.
- [x] Step 2: Verify the test runner. `uv run --frozen pytest --version` reports pytest 9.x; `pyproject.toml` already has `testpaths=["tests"]` and `pythonpath=["."]`. Record the unit-scoped command `uv run --frozen pytest tests/core -q` in `unit-test-instructions.md`.
- [x] Step 3: Data model. Implement `db.py`:
  - schema version 2, with tables `rooms`, `seats`, `games`, `moves`, `schema_version` and the indexes and unique constraints from `entities.md`;
  - `connect()` and a `transaction()` context manager that uses `BEGIN IMMEDIATE`, rolls back on error and commits on success;
  - the startup check (BR4.1): an old or unmarked file is renamed to `justchess.sqlite3.old` with a logged warning, and the database path is configurable through `JUSTCHESS_DB`.
- [x] Step 4: Data model tests (`tests/core/test_db.py`): a fresh database gets schema version 2; an old-format file is moved to `.old` and a fresh one is created; the transaction rolls back on an exception; the unique `(room, number)` constraint holds; an unwritable path fails startup with a clear error.
- [x] Step 5: Repository and business logic for Rooms (`rooms.py`):
  - code generation and validation (BR1.1, BR1.2);
  - create, join and rejoin, with the third join refused (BR1.3);
  - token issue, hashing and verification (BR1.4);
  - continue token issue and redeem with a 10-minute expiry (BR1.5);
  - seat authorisation (BR1.6);
  - presence, lastSeenAt throttling and the abandoned check (BR1.7);
  - score update (BR3.1);
  - rematch request, idempotence and lapse computation (BR3.2, BR3.3);
  - delete-by-room and idle-room listing.
- [x] Step 6: Rooms tests (`tests/core/test_rooms.py`):
  - the code format;
  - collision retry;
  - a third join is refused;
  - rejoin by token;
  - only the token hash is stored;
  - a wrong token is refused;
  - continue redeem rotates the token, and the old token stops working;
  - an expired continue token is refused;
  - the score follows the slot across a colour swap;
  - a rematch needs both seats, and a repeat request is idempotent;
  - lapsed when the other seat is abandoned (injected clock).
- [x] Step 7: Business logic for Games (`games.py`):
  - start a game (game 1 or a rematch with colours flipped);
  - rebuild the board by replaying the moves;
  - apply a move with the turn, legality and version checks (BR2.1);
  - automatic ends with reasons (BR2.2);
  - claimable-draw detection and claim (BR2.3);
  - claim win after abandonment, given the fact by the caller (BR2.4);
  - the snapshot builder per viewer (BR2.5), keeping the legacy fields;
  - delete-by-room.
- [x] Step 8: Games tests (`tests/core/test_games.py`):
  - a legal move is accepted and an illegal one rejected;
  - the wrong side is rejected;
  - a stale version is rejected;
  - Fool's mate ends with reason checkmate and result 0-1;
  - stalemate;
  - insufficient material;
  - a threefold repetition reached through stored moves is claimable but not ended, and the claim ends it with threefold_claimed;
  - fivefold repetition ends automatically;
  - a claim is refused when not claimable;
  - the snapshot moves are numbered;
  - a watcher snapshot has no legal moves and no slot.
- [x] Step 9: Live updates (`live.py`):
  - a connection registry per room;
  - the hello handshake (token in the first message), with an invalid token treated as a watcher;
  - the 10 s receive timeout and the ping/visibility messages;
  - presence change broadcasts;
  - per-socket snapshot composition;
  - `seat-moved` on transfer;
  - the 1 KB message size limit.
- [x] Step 10: Housekeeping (`housekeeping.py`): an hourly task plus a run at startup that deletes rooms idle for 30 days (BR4.2) through Games and Rooms delete-by-room in one transaction per room, with an empty hook list for U5. Errors are logged and retried on the next run.
- [x] Step 11: API and orchestration (`api.py`, `security.py`).
  - Routes:
    - `POST /api/rooms`
    - `POST /api/rooms/{code}/join`
    - `GET /api/rooms/{code}` (with the `X-Seat-Token` header)
    - `POST /api/rooms/{code}/moves`
    - `POST /api/rooms/{code}/claim-draw`
    - `POST /api/rooms/{code}/claim-win`
    - `POST /api/rooms/{code}/rematch`
    - `POST /api/rooms/{code}/continue-link`
    - `POST /api/rooms/{code}/continue`
    - `WS /ws/{code}`
    - `GET /r/{code}` serves the page
    - `GET /`, the existing lessons routes and `GET /api/engine` are kept
  - Each state change runs under the per-room lock and a `BEGIN IMMEDIATE` transaction, then broadcasts.
  - Origin middleware and streaming body limit (BR4.3).
  - The error table from `functional-spec.md`, with Pydantic request models.
  - Database errors are logged with the room code only, never with tokens.
  - Lifespan: database check, housekeeping task, Stockfish preparation.
- [x] Step 12: API and WebSocket integration tests (`tests/core/test_api.py`, `tests/core/test_live.py`), using TestClient and the WebSocket test client with a temporary database:
  - create, join, move, end and score;
  - a state read with the header returns the seat, and a token in the query string is ignored;
  - a foreign origin is refused on POST and on the socket;
  - a body over 4 KB returns 413;
  - concurrent moves (two threads) give one 200 and one 409, with no 500;
  - concurrent rematch requests create exactly one new game;
  - claim win is refused before 24 h and accepted after (injected clock);
  - hello gives a snapshot; the seat and the watcher get different snapshots;
  - presence becomes away after the receive timeout (shortened in tests);
  - a continue redeem tells the old socket `seat-moved`;
  - the existing Stockfish tests still pass.
- [x] Step 13: Environment configuration. Document `JUSTCHESS_DB` and `JUSTCHESS_ORIGIN` in the README; state the single-process assumption; note that the old frontend does not work with the new API until U3.
- [x] Step 14: Documentation and traceability. Docstrings for each module's public functions. Fill this unit's `code-summary.md` and `traceability.json`.

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

Inapplicable layer: frontend behaviour belongs to U2 and U3. U1 only removes the HTMX tag, so it has no frontend tests.
