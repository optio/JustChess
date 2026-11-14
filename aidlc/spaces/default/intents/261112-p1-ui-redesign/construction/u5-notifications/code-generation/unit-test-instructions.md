# Unit Test Instructions — u5-notifications

## Test framework setup and configuration

- **Python:** pytest with FastAPI's TestClient and the core conftest fixtures (temporary database, Stockfish patched out). The push transport is faked by injecting a sender, so no network call is made. VAPID tests use keys generated inside `tmp_path` and environment variables set with `monkeypatch`.
- **JavaScript:** Node's built-in test runner, run through `tests/js/index.js`. The browser APIs are injected fakes.
- **Browser run (optional):** the existing headless Chromium harness, with notification permission granted through CDP. It is skipped with a reason when Chromium is missing.

## How to run this unit's tests

From the project root:

```bash
uv run --frozen pytest tests/test_notifications.py tests/test_push_api.py tests/core/test_db.py -q
node --test tests/js/
```

The whole suite, which is the unit checkpoint command:

```bash
uv run --frozen pytest -q
```

## Tests (Standard strategy: 5–8 per component, plus key boundaries)

| File | Component | Count | Covers |
|---|---|---|---|
| `tests/core/test_db.py` (extended) | data model | +5 | fresh database at v3; v2 upgraded in place with rooms kept; below v2 moved aside; upgrade rollback; uniqueness |
| `tests/test_notifications.py` | logic and storage | 8–16 | event builder and final move; claim once; fresh, stale and hidden presence; send results (2xx, 404/410, VAPID mismatch, 500, none); subscribe validation and allowlist; trim to 5; seat transfer cleanup; housekeeping hook; VAPID loading and refusal (including symlink); generator refusal; no endpoint in logs |
| `tests/test_push_api.py` | routes | 8 | key route enabled and disabled; subscribe (seat, foreign, invalid); unsubscribe (with endpoint, without endpoint gives 400); `/sw.js` headers; move and join dispatch one claim; foreign origin; response not delayed by a slow send |
| `tests/js/notify-core.test.mjs` | client logic | 6–8 | keys match the server; banner, local or none; already shown; turned off; room in the tag; service worker decision |
| `tests/js/notifications.test.mjs` | toggle flow | 5 | granted with push; granted without push; denied; turned off; re-subscribe in another room |
| `tests/test_game_screen.py` (extended) | integration | +1–2 | `/sw.js` and imports resolve; optional browser local-notification run |

All existing tests must stay green.

## Expected coverage targets

The refactor scope sets no coverage floor. The Standard strategy's test count per component is met.

## Mocking and stubbing guidance

- **Push sender:** injected as a callable that returns a fake response (status code and text), so each tested outcome comes straight from it.
- **Presence:** passed to `dispatch` directly. For the API tests, the hub's `last_heard` is set through its test helpers.
- **Background tasks:** the API tests run them synchronously after the response, as TestClient does by default. The slow-send test uses a sender that sleeps and checks the response arrived first.

## Test data management

- Subscription fixtures use allowlisted example endpoints such as `https://fcm.googleapis.com/fcm/send/test-…`, with keys of valid length.
- Nothing is sent to a real push service in automated tests.
