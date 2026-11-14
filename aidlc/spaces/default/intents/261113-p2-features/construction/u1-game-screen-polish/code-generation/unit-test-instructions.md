# Unit Test Instructions — u1-game-screen-polish

## Framework
- **JS unit tests:** Node's built-in test runner (`node:test`, `node:assert/strict`). Test files are `tests/js/*.test.mjs`, and `tests/js/index.js` loads them all. Nothing needs installing.
- **Browser tests:** pytest with the headless Chromium CDP helpers already in `tests/test_game_screen.py` (`live_server`, `browser`, `Page`). They need Chromium (`JUSTCHESS_CHROMIUM`, or `chromium` on the PATH). Without it they skip with a reason.

## Commands for this unit only
```bash
node --test tests/js/captures.test.mjs tests/js/layout.test.mjs tests/js/share.test.mjs tests/js/qr.test.mjs
uv run --frozen pytest -q tests/test_u1_polish_browser.py
```

The project-wide check stays `uv run --frozen pytest -q`, the approved verification command. It also runs the JS suite through the existing wrapper test.

## Scope (Standard strategy)

| Component | File | Tests |
|---|---|---|
| captures.js | tests/js/captures.test.mjs | 6 |
| layout.js | tests/js/layout.test.mjs | 6 |
| share.js additions | tests/js/share.test.mjs | 5 new |
| qr-canvas.js | tests/js/qr.test.mjs | 4 |
| Board, game screen, dialog (browser) | tests/test_u1_polish_browser.py | 7 |

Each component covers the happy path and at least two edge cases: en passant, promotion with capture, the 1024 × 500 precedence, the 320 px floor, encoding of special characters, too-long QR input, reduced motion, and a refused clipboard.

## Mocking and test data
- `navigator` is a plain object in the JS tests (`{ clipboard: { writeText } }`, with or without `share`), as `share.test.mjs` already does.
- Move lists are short hand-written SAN/UCI sequences, including an en passant line (`e4 a6 e5 d5 exd6`).
- The browser tests create rooms through the API on a temporary database. They never touch `justchess.sqlite3`.
- Reduced motion is emulated with CDP `Emulation.setEmulatedMedia` (`prefers-reduced-motion: reduce`). Viewports use `Emulation.setDeviceMetricsOverride`.

## Coverage
The refactor scope sets no coverage floor. Every new exported helper has tests, and the existing suite must stay green.
