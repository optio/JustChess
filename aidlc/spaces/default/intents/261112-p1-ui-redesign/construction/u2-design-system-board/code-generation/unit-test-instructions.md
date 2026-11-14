# Unit Test Instructions — u2-design-system-board

## Test framework setup and configuration

- **Runner:** Node's built-in test runner (`node --test`, Node 24.x, already installed). There is no npm install, no `package.json` and no test dependency. Tests are `.mjs` files that import the browser modules from `static/js/` directly. Only the pure modules are imported; the DOM modules are not.
- **Bridge into the approved check:** `tests/test_frontend_js.py` runs the Node suite through `subprocess`, so the recorded verification command `uv run --frozen pytest -q` includes it. When `node` is not installed it skips, saying so. The same file also checks, with the FastAPI TestClient, that the demo page and its assets are served without a 404.

## How to run this unit's tests

Run this exactly, from the project root:

```bash
node --test tests/js/
```

The whole suite, as used at the unit checkpoint:

```bash
uv run --frozen pytest -q
```

## Tests (Standard strategy: 5–8 per component, plus key boundaries)

| File | Component | Count | Covers |
|---|---|---|---|
| `tests/js/geometry.test.mjs` | geometry | 8 | square colour; orientation; labels in both modes; FEN, including a bad one; targets and promotion; diffMove (normal, capture, castling, en passant, promotion, null); edge focus moves; accessible names |
| `tests/js/interaction.test.mjs` | interaction reducer | 8 | a piece with no moves; retap; emit and pending; promotion pick and cancel; locked from selected, promoting or pending; reject; optimistic equal position |
| `tests/js/settings.test.mjs` | settings store | 7 | defaults; one corrupt key; storage that throws; subscribers; unknown value refused; storage event sync; notifications hook granted, denied and throw (the hook's pure decision helper) |
| `tests/js/contrast.test.mjs` | tokens | 5 | pieces against 6 squares at 3:1 or more; labels at 4.5:1 or more; primary button pairs; body and muted text in both themes; the luminance helper itself |
| `tests/js/assets.test.mjs` | assets | 3 | fonts and pieces exist and match their sha256; CSS references resolve; the licence files are present |
| `tests/test_frontend_js.py` | integration | 2 | the Node suite passes; the demo page and the assets it references are served |

The existing 46 Python tests must stay green.

## Expected coverage targets

The refactor scope sets no coverage floor. The Standard strategy asks for 5–8 tests per component, which the table above meets. Visual behaviour (motion, themes, picker) is checked on the demo page; Build and Test runs the axe and contrast checks.

## Mocking and stubbing guidance

- Storage is injected: tests pass an in-memory object, or one whose methods throw.
- The notifications hook is a fake async function that resolves `true` or `false`, or rejects.
- No DOM is needed: board.js stays thin and the logic sits in the pure modules.

## Test data management

Positions are FEN strings and short UCI move lists written in each test. The asset hashes are read from `static/ASSETS.md`.
