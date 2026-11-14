# Code Generation Plan — u5-notifications

## Summary

- Builds: notifications that actually arrive, with one alert per event. You get an alert when your opponent joins, moves, or the game ends. An open page shows a banner, a background tab gets a system notification, and a closed tab gets a Web Push notification. You give permission only after turning the setting on, and turning it off stops every alert. Push signing keys come from your environment, never from the repo. Push stays off until keys are set.
- Touches:
  - New `justchess/notifications.py` and `justchess/vapid.py` (keys plus a small key generator command).
  - Push routes and `/sw.js` in `justchess/api.py`.
  - Schema version 3 in `justchess/db.py`: two new tables, with an in-place upgrade so your rooms are kept.
  - The housekeeping hook.
  - New `static/sw.js`, `static/js/notifications.js` and `static/js/notify-core.js`.
  - Wiring in `app.js`, `hooks.js` and `screens/game.js`.
  - `pywebpush` added.
  - New tests.
- Tests: about 30 pytest tests and about 15 Node tests. A real push on localhost is a manual check for you once keys exist.

## Inputs

- `construction/u5-notifications/functional-design/` (`functional-spec.md`, `rules.md`, `entities.md`).
- `inception/domain-design/decisions.md` (one-alert-per-event ADR, ADR-006).
- Existing code:
  - `justchess/db.py`, `api.py`, `live.py`, `housekeeping.py`, `rooms.py`;
  - `static/js/hooks.js`, `app.js`, `screens/game.js`, `settings-panel.js`, `settings.js`.

## Design review findings resolved in this build

The functional design review (advisory, READY with 2 Major findings) raised the points below. This build settles each one as follows.

| Finding | Build decision |
|---|---|
| A stale "visible" flag loses the alert (Major) | **Server:** push is skipped only when the target seat has a socket that is visible and fresh, meaning it sent a ping or visibility message in the last 6 s. The hub records `last_heard` per socket. **Client:** sends `visibility: false` on `visibilitychange` and on `pagehide`. **Page:** when it is hidden at the time of a snapshot event, it always asks the service worker for a local notification, whether or not a push subscription exists. Push and local notifications share the tag `<code>:<key>` with `renotify: false`, so if both arrive the second silently replaces the first and nothing is lost or doubled. W4 step 5's "do nothing" is replaced by this. |
| Push endpoint SSRF (Major) | Endpoints must be `https`, on port 443, with no user info and no IP literal, and the host must match an allowlist of push services: `fcm.googleapis.com`, `*.push.services.mozilla.com`, `*.notify.windows.com`, `web.push.apple.com` and `*.push.apple.com`. More hosts can be added through `JUSTCHESS_PUSH_HOSTS` (comma-separated). Sends go through a `requests.Session` with `max_redirects = 0`, passed to pywebpush as `requests_session`, so redirects are never followed. Endpoints are never logged; only the host is. |
| Dispatch timing | Join, move and claim handlers read presence and freshness inside the handler, then schedule `notifications.dispatch(event, presence)` as a FastAPI `BackgroundTask` that runs `asyncio.to_thread` after the response is sent. Sends to a seat's endpoints run in sequence, with a 10 s timeout each. The worker never reads hub state; the presence result is passed in. |
| Tags collide across rooms; skip path | The tag is `<code>:<key>` on both server and client. When the service worker gets a push while a visible page for that room exists (a rare race), it still shows the notification with that tag, so it never triggers Chrome's generic "updated in the background" notice. |
| Schema upgrade versus ADR-006 | `prepare_database`: version 3 is current. A version-2 database is upgraded in one transaction that creates both tables and sets `schema_version` to 3. Anything below 2, or unmarked, is still moved aside as before. A fresh database is created at version 3. The ADR-006 amendment ("version 2 upgrades in place to version 3") is recorded in the code summary and the README. A test covers the upgrade and checks the rooms are kept. |
| Seat transfer and unsubscribe | Redeeming a continue token deletes that seat's subscriptions in the same transaction, so the new device subscribes again. The page always sends its endpoint when it unsubscribes. An unsubscribe with no endpoint is refused with 400. |
| Client key fields; zero subscriptions; stuck claims | Keys are built from snapshot fields only: `joined` when `seats.B.presence` changes from `empty` while game 1 is in progress; `move:<game>:<ply>`, where ply is the number of half-moves in `moveList`; `ended:<game>` when `status` becomes `finished`. A claim with no subscriptions is marked `skipped` (`no_subscription`). A claim left `claimed` after a crash is never resent, by design, and is removed with its room. |
| Hook signature | Uses the existing `hooks.onSnapshot(snapshot, view)`, wrapped by U5, with the previous snapshot kept inside the notifications module. `hooks.notifications` is registered in `app.js` at startup, before any game screen is built. |
| VAPID format and rotation | `JUSTCHESS_VAPID_PRIVATE_KEY` accepts a PEM key or a raw base64url 32-byte P-256 key. `JUSTCHESS_VAPID_KEY_FILE` points to a PEM file, and its real path (symlinks resolved) must lie outside the project folder. A 400 or 403 from the push service that names a VAPID or key mismatch deletes that subscription, as 404 and 410 do. `uv run python -m justchess.vapid generate ~/.config/justchess/vapid.pem` writes a new key with mode 0600 and refuses any path inside the project. |

## Carried over from earlier unit reviews

- U1 Major (the order of checks written in BR2.1) still goes to Build and Test.

## Steps

- [x] Step 1: Project structure.
  - Create `justchess/notifications.py`, `justchess/vapid.py`, `static/sw.js`, `static/js/notifications.js` and `static/js/notify-core.js`.
  - Run `uv add pywebpush`.
- [x] Step 2: Verify the test runners. They are unchanged: `uv run --frozen pytest -q` and `node --test tests/js/`. Record the unit commands in `unit-test-instructions.md`.
- [x] Step 3: Data model in `justchess/db.py`.
  - Schema version 3 with `push_subscriptions` (unique on room, slot and endpoint) and `alert_records` (primary key on room, slot and event_key).
  - The in-place upgrade from version 2 in one transaction.
  - Fresh databases created at version 3.
- [x] Step 4: Data model tests in `tests/core/test_db.py`:
  - a fresh database is at version 3;
  - a version-2 file is upgraded in place and its rooms and moves are kept;
  - a database below version 2 is still moved aside;
  - the upgrade rolls back on failure;
  - the uniqueness constraints hold.
- [x] Step 5: Repository and business logic in `justchess/notifications.py` and `justchess/vapid.py`.
  - Subscription storage: validation (allowlisted hosts), upsert, trimming to 5 per seat, deletion by endpoint, seat or room.
  - The event builder (BR1.1).
  - The claim (insert or ignore).
  - The presence rule, using fresh visibility.
  - Sending: pywebpush with no redirects, TTL 3600, a 10 s timeout, and the result handling for 2xx, 404/410, VAPID mismatch, other failures and zero subscriptions.
  - The VAPID loader and generator.
  - The housekeeping cleanup hook.
  - Deleting subscriptions when the seat moves to another device.
- [x] Step 6: Logic tests in `tests/test_notifications.py`, with the push transport faked:
  - the event builder, including that a final move gives only an `ended` alert;
  - a second dispatch of the same key never sends;
  - connected and visible and fresh means skipped;
  - visible but stale means a send;
  - hidden means a send;
  - 2xx marks sent;
  - 404/410 and a VAPID mismatch delete the subscription;
  - a 500 marks failed;
  - zero subscriptions marks skipped;
  - subscribe validation: http, port, IP literal, localhost, a host not on the allowlist, an allowlisted host, bad key lengths;
  - the trim to 5;
  - a continue redeem deletes the seat's subscriptions;
  - the housekeeping hook;
  - VAPID: env PEM, env raw, an outside file, an inside file refused (including through a symlink), missing keys disable push;
  - the generator refuses a path inside the project;
  - no endpoint appears in the logs.
- [x] Step 7: API in `justchess/api.py` and `justchess/live.py`.
  - `GET /api/push/key`.
  - `POST /api/rooms/{code}/push/subscribe` and `/push/unsubscribe` (an endpoint is required).
  - `GET /sw.js` with the headers `Service-Worker-Allowed: /`, `Cache-Control: no-cache` and the JavaScript content type.
  - Background-task dispatch after join, move and the two claims.
  - `last_heard` per socket in the hub, plus an `is_fresh_visible(code, slot, now)` helper.
- [x] Step 8: API tests in `tests/test_push_api.py`:
  - the key route when enabled and when disabled;
  - subscribe as a seat, with a foreign token, and with an invalid endpoint;
  - unsubscribe, with and without an endpoint;
  - `/sw.js` headers;
  - a move dispatches exactly one claim for the opponent, faked and synchronous in the test;
  - join dispatches `joined` to A;
  - a foreign origin is refused;
  - the response does not wait for a slow fake send.
- [x] Step 9: Frontend pure logic and tests.
  - `static/js/notify-core.js`:
    - `eventFor(prev, next, slot)` gives the key, title, body and tag;
    - `decide({visible, permission, enabled, shownKeys, key})` returns `"banner"`, `"local"` or `"none"`;
    - `swDecision` (pure logic shared with `sw.js` through `importScripts`, or duplicated with a test that pins both copies equal).
  - `tests/js/notify-core.test.mjs`:
    - keys match the server builder for join, move, the final move and claims;
    - visible means a banner;
    - hidden means a local notification, with or without push;
    - an already shown key gives `none`;
    - turned off gives `none` for system notifications and a banner when visible;
    - the tag includes the room.
  - `tests/js/notifications.test.mjs`, with fake Notification, serviceWorker and pushManager objects, and fetch:
    - the toggle on with permission granted, push enabled, and the subscription posted;
    - granted with push disabled, giving local-only mode;
    - denied, giving false and a message;
    - the toggle off, which unsubscribes and posts the endpoint;
    - joining another room re-subscribes for that seat.
- [x] Step 10: Frontend DOM and wiring.
  - `static/js/notifications.js`: permission inside the click, service worker registration, subscribe and unsubscribe, the banner element in the game screen, local notifications through `registration.showNotification`, `visibility` on `pagehide`, and `sessionStorage` for shown keys with a try/catch fallback.
  - `static/sw.js`: push, then the visible check, then `showNotification` with the tag (also shown when a page is visible); `notificationclick` focuses the room's page or opens it.
  - Wiring in `app.js` and `hooks.js` (`onSnapshot` wrapper, registered at startup), and the banner slot in `screens/game.js`.
- [x] Step 11: Integration checks.
  - Extend `tests/test_game_screen.py` so that `/sw.js` and the new modules resolve.
  - If Chromium is available, add a browser run with notification permission granted through CDP: the second context goes to the background, the first context moves, and the second context's service worker shows a notification with tag `<code>:move:1:1`. This uses local notifications; push is not needed.
  - Run `uv run --frozen pytest -q`.
- [x] Step 12: Documentation and traceability.
  - A README section "Notifications": how to generate keys outside the repo (`uv run python -m justchess.vapid generate ~/.config/justchess/vapid.pem`, then `export JUSTCHESS_VAPID_KEY_FILE=…`); push works on `localhost` and needs HTTPS elsewhere (the open hosting decision, with options: a reverse proxy with a certificate, or a tunnel); the allowlist variable; the ADR-006 amendment.
  - Module headers.
  - `source-manifest.json`, application files only.
  - Leave `code-summary.md` and `traceability.json` to the orchestrator.

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

All five testable layers apply to this unit. Repository and business logic share `notifications.py` and are tested together in Step 6.
