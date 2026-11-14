# Code Summary — u2-design-system-board

## Result

- `node --test tests/js/`: **33 passed**, 0 failed.
- `uv run --frozen pytest -q`: **48 passed**. That is 46 before this unit, plus 2 bridge tests in `tests/test_frontend_js.py`.
- A browser check in headless Chromium found no console errors. It covered:
  - selecting pieces and castling;
  - the promotion picker (focus, arrows, Escape, picking a piece);
  - `reject()`;
  - keyboard focus surviving a board flip;
  - frame labels, theme and board changes;
  - the scripted game, with its slide, capture and check animations.

## Files

| Area | Files |
|---|---|
| Styles | `static/css/tokens.css`, `static/css/base.css`, `static/css/board.css` |
| Pure modules | `static/js/board/geometry.js`, `static/js/board/interaction.js`, `static/js/settings.js`, `static/js/contrast.js` |
| DOM modules | `static/js/board/board.js`, `static/js/board/promotion.js`, `static/js/settings-panel.js`, `static/js/boot.js` |
| Assets | `static/fonts/` (6 woff2 files plus OFL licences), `static/pieces/cburnett/` (12 SVGs plus `LICENSE.md`), `static/logo.svg`, `static/ASSETS.md` (sources, versions, sha256) |
| Demo | `static/demo/board.html`, `demo.js`, `demo.css` |
| Tests | `tests/js/index.js`, `tests/js/*.test.mjs` (geometry, interaction, settings, contrast, assets), `tests/test_frontend_js.py` |
| Docs | README section "Design system and demo page" |

## Decisions made during the build

- **Pinned assets.** `@fontsource` 5.3.0 for all three families, with every weight available. Pieces come from lila commit `d52ae7f9177bb1c5eb3536968284d83efdb133aa`.
- **Contrast.** Token values were changed as little as possible, and no threshold was lowered. All 84 checked pairs pass:
  - Walnut dark square #A3713F → #9C6C3C.
  - Tournament dark square #5A8160 → #597F5F.
  - Labels are solid #FFFFFF on dark squares and #1E1611 on light squares.
  - Black pieces get a light edge, which brings them to 4.65:1 on Rosewood (2.34:1 without it).
  - New tokens: `--accent-text` #785C1E for quiet buttons in light mode, `--focus-ring` #8A6A22 in light mode, and `--on-baize` #14110D in dark mode.
- **Test entry point.** `tests/js/index.js` loads every test file, so the approved command `node --test tests/js/` works on Node 24.
- **Tests read the real stylesheet.** The contrast tests parse `tokens.css`, so a regression fails the test.
- **Frame coordinates** are engraved on the bottom and left edges, as BR1.3 requires.
- **API additions.** `openPromotion()` returns a promise with `.cancel()`. If `onMove` throws, the error is logged and the move is treated as refused.

## Open points

- **Piece licence.** Lichess's `COPYING.md` lists the cburnett folder as GPLv2+. The original Wikimedia set is CC BY-SA 3.0, which is the credit that was approved. Both facts are recorded in `static/pieces/cburnett/LICENSE.md`, `ASSETS.md` and the README. Which credit to show is the owner's decision.
- **Highlight contrast.** The checklist asks for 3:1 on highlights, but this unit doesn't test it. Brass highlights on light squares may fall short, so Build and Test should measure them.
- **For U3.** Use `createBoard` and the settings store, and answer every move with `set()` or `reject()`.
