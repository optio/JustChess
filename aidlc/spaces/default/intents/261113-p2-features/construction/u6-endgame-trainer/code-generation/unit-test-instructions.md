# Unit Test Instructions — u6-endgame-trainer

## Framework
- **Python:** pytest. The API tests use the fixtures in `tests/core/conftest.py` (temporary database, TestClient). Run with `uv run --frozen`.
- **Fake engine:** the U4 helpers in `tests/fakes/` (`fake_uci.py`, `engines.py`), injected through `create_app`. A test endgame folder is passed to `create_app` where a test needs its own positions.
- **JS:** `node:test`.
- **Browser:** headless Chromium through the CDP helpers in `tests/test_game_screen.py`, with the fake engine. The test skips with a reason when Chromium is missing.

## Commands for this unit only
```bash
uv run --frozen pytest -q tests/test_endgames_content.py tests/test_endgames.py tests/test_endgame_judge.py tests/core/test_endgames_api.py tests/core/test_computer_api.py tests/test_gameplay.py tests/test_u6_endgame_browser.py
node --test tests/js/endgame.test.mjs tests/js/endgame-tab.test.mjs
```

**Runner check (step 2, 2026-11-14):** `uv run --frozen pytest -q tests/test_puzzles.py` ran 9 passed in 0.94 s, and `node --test tests/js/hub-tabs.test.mjs` ran 5 passed (Node v24.6.0). Chromium is at `/usr/bin/chromium`, so the browser test runs here. The baseline full suite `uv run --frozen pytest -q` before any change was 354 passed, 1 skipped. The unit commands above are the ones to use.

`tests/core/test_computer_api.py` and `tests/test_gameplay.py` are included because the hint wait helper and the gameplay loader change. The project-wide check stays `uv run --frozen pytest -q`.

## Scope (Standard strategy)

| Component | File | Tests |
|---|---|---|
| Shipped content | tests/test_endgames_content.py | 4 |
| Catalog loader | tests/test_endgames.py | 6 |
| Judge | tests/test_endgame_judge.py | 10 |
| Endgame HTTP | tests/core/test_endgames_api.py | 9 |
| endgame-state.js | tests/js/endgame.test.mjs | 8 |
| Endgames tab | tests/js/endgame-tab.test.mjs | 3 |
| One position (browser) | tests/test_u6_endgame_browser.py | 1 |

## Mocking and test data
- **Judge tests** use hand-picked FENs and short move lists. No engine is involved.
- **Engine behaviour** comes from the fake engine. Its delay flag holds a request in the queue for the refusal and wait-limit tests, and the wait limit is set short through the gameplay settings in those tests.
- **Rate limit:** a fake clock or a low per-minute limit set in the test's gameplay settings.

## Coverage
The refactor scope sets no coverage floor. Every new function has tests, and the existing suite must stay green.
