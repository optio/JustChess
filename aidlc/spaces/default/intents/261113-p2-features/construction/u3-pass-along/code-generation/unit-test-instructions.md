# Unit Test Instructions — u3-pass-along

## Framework
- **Python:** pytest, using the fixtures in `tests/core/conftest.py` (temporary database, TestClient). Run with `uv run --frozen`.
- **JS:** `node:test`.
- **Browser:** headless Chromium through the CDP helpers in `tests/test_game_screen.py`. The browser test skips with a reason if Chromium is missing.

## Commands for this unit only
```bash
uv run --frozen pytest -q tests/core/test_pass_along.py tests/core/test_join_requests.py tests/core/test_join_requests_api.py tests/test_rate_limit.py tests/test_notifications.py tests/test_envfile.py tests/test_u3_pass_along_browser.py
node --test tests/js/pass-along.test.mjs tests/js/room-flow.test.mjs
```

The project-wide check stays `uv run --frozen pytest -q`.

Runner check (step 2): `uv run --frozen pytest -q tests/core/test_rooms.py` (11 passed) and `node --test tests/js/room-flow.test.mjs` (10 passed) both run on the unchanged tree, so the commands above use the existing configuration as is.

## Scope (Standard strategy)

| Component | File | Tests |
|---|---|---|
| Modes and play | tests/core/test_pass_along.py | 8 |
| Join requests (domain) | tests/core/test_join_requests.py | 9 |
| Join requests (HTTP) | tests/core/test_join_requests_api.py | 7 |
| Rate limit | tests/test_rate_limit.py | 6 |
| Join-request alert | tests/test_notifications.py | 1 new |
| pass-along.js | tests/js/pass-along.test.mjs | 7 |
| room-flow.js | tests/js/room-flow.test.mjs | 2 new |
| Two-page flow (browser) | tests/test_u3_pass_along_browser.py | 1 |

## Mocking and test data
- **Time:** a fake clock is injected for lapse and window tests. There are no real sleeps beyond the browser test.
- **Client address:** TestClient's client address is set, or an `X-Forwarded-For` header is added, together with the `JUSTCHESS_TRUSTED_PROXIES` environment variable via `monkeypatch`.
- **Logs:** `caplog` asserts that no token appears in any log line.

## Coverage
The refactor scope sets no coverage floor. Every new function has tests, and the existing suite must stay green.
