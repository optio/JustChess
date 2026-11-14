# Code Generation Plan — u3-pass-along

This plan follows these sources:
- the functional design in `construction/u3-pass-along/functional-design/`: `entities.md`, `rules.md` (BR1.1–BR1.5, BR2.1–BR2.5, BR3.1–BR3.2, BR4.1) and `functional-spec.md` (W1–W5, including the fixes from the review);
- `inception/units-generation/unit-of-work.md` (U3);
- requirements FR3.1–FR3.9, FR9.1, FR9.2 and NFR4;
- ADR-003 (as amended) and ADR-006.

The work is brownfield. It changes `justchess/` (`rooms.py`, `games.py`, `api.py`, `notifications.py`, `housekeeping.py`, a new `ratelimit.py`) and `static/js/` (`room-flow.js`, `screens/game.js`, `seat-store.js`, a new `pass-along.js`). It uses the version 4 schema from U2, so there are no schema changes.

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

The schema itself does not change (U2 built it). The data-access layer is the room and request functions in `rooms.py`.

## Steps

- [x] **Step 1 — Structure.** Create `justchess/ratelimit.py` and `static/js/pass-along.js` as skeletons with header comments.
- [x] **Step 2 — Runner check.** Confirm `uv run --frozen pytest -q tests/core/test_rooms.py` and `node --test tests/js/room-flow.test.mjs` run, and record the unit commands in `unit-test-instructions.md`.
- [x] **Step 3 — Rooms and requests: implement** (BR1.1, BR1.3–BR1.5, BR2.1, BR2.2, BR2.4).
  - In `rooms.py`:
    - `set_mode(conn, code, seat, mode, now)`: seat A only, no seat B, not a computer room. Leaving pass-along declines any pending request. Entering it starts a game that is still in status waiting, with `counted = false`.
    - `create_join_request` and `find_request(token)`, with lapse on read.
    - `answer_request(...)`, which also checks the mode and seat B, and remembers the address of a declined requester for 10 minutes.
    - `request_status`.
    - `lapse_expired`.
    - Seat B created from the request token's hash.
  - In `games.py`:
    - The seat check allows both colours for seat A in pass-along mode.
    - `mark_counted` acts only when the game is not finished.
    - `record_result` honours `counted`.
    - A one-seat "play again" in pass-along.
- [x] **Step 4 — Rooms and requests: tests.**
  - `tests/core/test_pass_along.py` (8 tests):
    - only seat A can switch mode;
    - 409 once seat B exists;
    - both colours allowed in pass-along, refused otherwise;
    - `counted` false, then true on accept or direct join, but a finished game stays uncounted;
    - no score recorded while uncounted;
    - leaving pass-along declines the pending request;
    - one-seat play again;
    - mode present in the snapshot.
  - `tests/core/test_join_requests.py` (9 tests):
    - a request is created;
    - busy;
    - the pending request is returned again to the same visitor;
    - accept makes the request token a working seat token for B;
    - decline, then `declined_recently` for the same address;
    - lapse on read and through housekeeping;
    - only seat A can answer;
    - a stale accept after a switch back gives 409;
    - status for unknown, pending, accepted and lapsed.
- [x] **Step 5 — Rate limit: implement** (BR3.1).
  - `ratelimit.py`: a sliding 60-second window with 5 attempts. Empty windows are dropped, and at most 10,000 addresses are kept, oldest evicted first.
  - `client_address(request, trusted)`: uses `request.client.host`. Only when `JUSTCHESS_TRUSTED_PROXIES` lists that address does it take the rightmost untrusted entry from `X-Forwarded-For`.
  - CIDR parsing with `ipaddress`. Invalid entries are logged and ignored.
- [x] **Step 6 — Rate limit: tests.** `tests/test_rate_limit.py` (6 tests):
  - five requests allowed, the sixth refused;
  - the window slides;
  - a spoofed `X-Forwarded-For` is ignored when no proxies are trusted;
  - it is honoured from a trusted proxy (rightmost untrusted entry);
  - a CIDR entry works and an invalid entry is ignored;
  - eviction.
- [x] **Step 7 — API, live updates and notifications: implement** (BR1.1, BR2.1–BR2.5).
  - In `api.py`:
    - `POST /api/rooms/{code}/mode`.
    - `/join` runs the seat-token rejoin check first, then the pass-along branch (the rate limit, then 202/409/429).
    - `POST …/join-request/answer` and `POST …/join-request/status`.
    - The rematch route takes the one-seat path in pass-along.
    - Every route is origin-checked, and tokens are never logged.
  - The snapshot carries `joinRequest {expiresAt}` for seat A only, and broadcasts follow every change.
  - In `notifications.py`: a `join_request_event(code, request_id)` for seat A.
  - In `housekeeping.py`: an hourly `lapse_expired` with no broadcast.
- [x] **Step 8 — API: tests.**
  - `tests/core/test_join_requests_api.py` (7 tests):
    - the HTTP flow end to end (mode, join gives 202, status, answer, then the seat token works);
    - 403 and 409 errors;
    - 429;
    - the creator rejoining with a seat token does not create a request;
    - `joinRequest` appears only in seat A's snapshot;
    - no token appears in logs (`caplog`);
    - an origin check.
  - `tests/test_notifications.py` gets 1 new test for the join-request event.
- [x] **Step 9 — Front end: implement** (BR4.1).
  - `pass-along.js`, pure logic: the joiner's poll state machine (every 3 s, paused while the page is hidden), the countdown text, and the rules for which buttons show.
  - In `screens/game.js`:
    - "Play here while waiting" and "Wait for a friend instead".
    - The pass-along status and practice note.
    - The request banner (`role="alert"`, countdown refreshed each minute, hidden at zero) with Accept and Decline.
    - "Play again" in pass-along.
  - In `room-flow.js`:
    - a 202 answer shows the joiner's waiting screen;
    - the request token is kept in session storage;
    - on accepted, the token is saved as seat B and the game opens;
    - messages for declined, lapsed, busy, `declined_recently` and too many requests.
  - The board allows both colours to move in pass-along mode.
- [x] **Step 10 — Front end: tests.**
  - `tests/js/pass-along.test.mjs` (7 tests).
  - `tests/js/room-flow.test.mjs` (2 new tests).
  - A browser test, `tests/test_u3_pass_along_browser.py` (1 test): the creator enters pass-along and makes a White move and a Black move; a second page asks to join; the creator accepts; the joiner's board opens as Black and both boards agree.
  - Then run the full suite.
- [x] **Step 11 — Configuration.** Add `JUSTCHESS_TRUSTED_PROXIES` to `.env.example`, to the env-file test's allowed list, and to the README. The README also explains Uvicorn's own `--forwarded-allow-ips` and when to use each.
- [x] **Step 12 — Documentation and traceability.** README sections on pass-along and join requests. Write `code-summary.md` and `traceability.json`.

## Requirement-to-step map

| ID | Steps |
|---|---|
| FR3.1 | 3, 4, 7, 9, 10 |
| FR3.2 | 3, 4, 9, 10 |
| FR3.3 | 3, 4, 7, 8, 9, 10 |
| FR3.4 | 7, 8, 9 |
| FR3.5 | 3, 4, 7, 8, 10 |
| FR3.6 | 3, 4, 7, 8, 9 |
| FR3.7 | 3, 4, 8, 9 |
| FR3.8 | 3, 4 |
| FR3.9 | 3, 4, 9 |
| FR9.1, FR9.2 | 11 |
| NFR4 | 5, 6, 7, 8 |

## Constraints
- Tokens never appear in URLs, logs or error bodies.
- No test touches `justchess.sqlite3`.
- Files are written with file tools.
