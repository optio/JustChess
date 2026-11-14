# Code Generation Plan — u2-data-and-your-games

This plan follows `construction/u2-data-and-your-games/functional-design/` (`entities.md`, `rules.md` BR1.1–BR3.6, `functional-spec.md` W1–W6), `inception/units-generation/unit-of-work.md` (U2), requirements FR1.1–FR1.4, FR2.1, NFR4 and NFR7, and ADR-010.

This is brownfield work in `justchess/` (`db.py`, `rooms.py`, `games.py`, `api.py`, `security.py`) and `static/js/` (`seat-store.js`, `screens/lobby.js`, `api.js`). The tests run on the existing runner, pytest plus `node --test`. They use temporary databases only, never `justchess.sqlite3`.

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

## Steps

- [x] **Step 1 — Structure.** Add the empty module `justchess/summaries.py` (the summary read model) and the empty client module `static/js/your-games.js` (pure list logic), each with a docstring or header.
- [x] **Step 2 — Runner check.** Confirm that `uv run --frozen pytest -q tests/core/test_db.py` and `node --test tests/js/seat-store.test.mjs` run, and record the unit commands in `unit-test-instructions.md`.
- [x] **Step 3 — Database: implement** (BR1.1, entities).
  - In `db.py`, set `SCHEMA_VERSION = 4` and remove `UPGRADABLE_VERSION` and `_upgrade_in_place`.
  - Write the full version 4 schema in one script:
    - rooms gain `mode` and `computer_level`, with a CHECK that the level is set if and only if mode is computer;
    - seats gain `is_computer`; `token_hash` becomes nullable, with a CHECK that it is null if and only if `is_computer`;
    - games gain `counted` and the extra `end_reason` values;
    - moves gain `captured_piece` and `captured_square`;
    - add `join_requests`, with a partial unique index for one pending request per room and `ON DELETE CASCADE`;
    - push and alert tables are unchanged.
  - Startup behaviour:
    - version 4 is kept;
    - a newer version refuses to start;
    - anything else is moved to `.old` and created fresh;
    - a failed rename stops start-up.
- [x] **Step 4 — Database: tests.** Update `tests/core/test_db.py`:
  - a fresh version 4 file is created;
  - version 2 and version 3 files are moved aside, replacing an existing `.old`;
  - a garbage file is moved aside;
  - a version 4 file is kept as is;
  - version 5 refuses to start;
  - the CHECK constraints reject a computer seat with a token and a computer level without computer mode;
  - the one-pending-request index holds.

  That is 8 tests. Replace the version 2 upgrade tests in `tests/test_notifications.py` with a version 2 move-aside test.
- [x] **Step 5 — Rooms and games: implement** (BR1.2, BR1.3).
  - `rooms.py`: create inserts `mode='waiting'`; a successful join sets `mode='online'` in the same transaction; the room view carries `mode` and `computer_level`.
  - `games.py`: capture info is computed before the move is pushed (en passant uses the passed pawn's square) and stored on the move row; the snapshot gains `mode`, `computerLevel` and `lastCapture`.
- [x] **Step 6 — Rooms and games: tests.**
  - `tests/core/test_rooms.py`: waiting, then online on join (2 tests).
  - `tests/core/test_games.py`: capture info for a normal capture, en passant, promotion with capture, and a quiet move, plus `lastCapture` in the snapshot (5 tests).
- [x] **Step 7 — Summaries API: implement** (BR2.1–BR2.3).
  - `security.py`: a per-path body-limit override, 8 KB for `/api/rooms/summaries` only.
  - `summaries.py`:
    - validate the body; on failure return the fixed 400 message "Invalid summary request";
    - deduplicate by (code, token);
    - in one read transaction, compare token hashes in constant time;
    - build each RoomSummary per BR2.2, returning `found:false` for an unknown room or a wrong token.
  - `api.py`: the route `POST /api/rooms/summaries`, origin-checked, writing nothing; tokens are never logged.
- [x] **Step 8 — Summaries API: tests.** `tests/core/test_summaries.py`, 10 tests:
  - ok;
  - `found:false` for an unknown room and for a wrong token, with the same shape;
  - your turn and their turn;
  - won, lost and drawn;
  - waiting;
  - a pending join request (row inserted directly);
  - one browser holding both seats of a room gets both views;
  - 400 with the fixed message, the submitted token absent from both the body and the logs;
  - 413 above 8 KB, 403 for a bad origin;
  - read-only: `last_activity_at` and `last_seen_at` unchanged.
- [x] **Step 9 — Front end: implement** (BR3.1–BR3.6).
  - `seat-store.js`: `kind` and `computerLevel` fields, defaulting to friend; `validSeats()`, which skips and removes malformed entries; `remove(code, token)`.
  - `your-games.js`, pure functions:
    - `filterAndSort(summaries, now)`;
    - `rowModel(summary, now)`, giving the label, meta, pill and thumbnail squares;
    - `relativeTime`;
    - `reconcile(store, summaries)`, which drops seats only on `found:false`.
  - `api.js`: `fetchSummaries(seats)`.
  - `screens/lobby.js`:
    - the new headline and the "Train" button, which opens `/learn`;
    - the Your games panel with its Loading, Listed, Stale and Empty states;
    - refresh on load, on `visibilitychange` and every 60 s while visible, with at most one request in flight and at most one per 30 s except Retry;
    - two columns at 900 px and wider.
  - CSS in `app.css`, using the tokens from the design system mapping.
- [x] **Step 10 — Front end: tests.**
  - `tests/js/your-games.test.mjs`, 8 tests: the 7-day cut-off; the sort order with join requests first; labels for friend joined, friend waiting and computer; pills for every case, including "Waiting" and "Ended"; seat dropping only on `found:false`; the failure path keeping seats; malformed stored seats skipped; relative times.
  - `tests/js/seat-store.test.mjs`, 2 new tests for `kind` and level.
  - Browser test `tests/test_u2_your_games_browser.py`: the main screen lists two rooms, and the "Your move" row opens its game (1 test).
  - Then run the full suite.
- [x] **Step 11 — Configuration.** No new environment variables. The README notes that the first start after this version moves the old database to `justchess.sqlite3.old` and starts fresh (ADR-010).
- [x] **Step 12 — Documentation and traceability.** Docstrings, `code-summary.md` and `traceability.json`.

## Requirement-to-step map

| ID | Steps |
|---|---|
| FR1.1 | 9, 10 |
| FR1.2 | 5, 7, 8, 9, 10 |
| FR1.3 | 9, 10 |
| FR1.4 | 7, 8, 9, 10 |
| FR2.1 | 5, 6 |
| NFR4 | 7, 8 |
| NFR7 | 3, 4, 11 |

## Constraints
- Never open, migrate or delete the real `justchess.sqlite3`. Every test uses `tmp_path`.
- Tokens never appear in URLs, logs or error bodies.
- Write files only with file tools.
