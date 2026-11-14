# Code Summary — u1-game-screen-polish

All 8 steps of the approved plan are done. This unit changed the front end only: no server, API or database code.

## Files

**Created**
- `static/js/vendor/qrcode.js`: QR encoder written for JustChess, under an MIT header (byte mode, level M, versions 1–10, Reed–Solomon, format and version info, masking).
- `static/js/captures.js`: `capturedPieces`, a SAN resolver and `captureLabel`.
- `static/js/layout.js`: `boardMode` and `boardSide`, mirroring the CSS.
- `static/js/share-dialog.js`: the native `<dialog>` controller.
- `static/js/qr-canvas.js`: `qrMatrix` and `drawQr`.
- `tests/js/captures.test.mjs`, `tests/js/layout.test.mjs`, `tests/js/qr.test.mjs`, `tests/test_u1_polish_browser.py`.

**Modified**
- `static/js/board/board.js`: shrink-and-fade capture, and optimistic captures animate once.
- `static/js/screens/game.js`: the captured row.
- `static/js/share.js`: `appLinks` and `dialogText`.
- `static/js/app.js`: wires the dialog; the inline share fallback is removed.
- `static/css/tokens.css`: `--t-capture` is now 260 ms, a new `--t-settle` token is 200 ms, and the unused `--capture-drop` is removed.
- `static/css/app.css`, `static/css/board.css`: board fit, the landscape layout, edge to edge under 400 px.
- `templates/index.html`: the dialog markup; `#share-fallback` and `#share-field` are removed.
- `static/ASSETS.md`: credit for the QR encoder.
- `README.md`: notes on the share dialog and the board fit.
- `tests/js/share.test.mjs`: 5 new tests.

## Key decisions and deviations from the plan

1. **The move list has no UCI.** The snapshot's move list is SAN only, and this unit changes no server code. So `captures.js` resolves SAN itself, including disambiguation and pins. A move it can't resolve throws `SanError`, and the row is hidden and the error logged, rather than showing a wrong row.
2. **A confirmation no longer cuts the animation short.** A confirming position equal to the one already shown no longer finishes running animations, so the player's own capture plays in full. Any new position still finishes them as before.
3. **Own move: only the capture animates.** The player's own optimistic move animates the capture, not a slide, so tap-to-move feels as before.
4. **Portrait from 400 to 767 px.** This range keeps the existing 8 px gutters (side = width − 16). The 640 px cap applies only on desktop. The 768 × 1024 case gets a 736 px board, as the design table says.
5. **The captured row is hidden until a capture happens**, which saves vertical space.
6. **Phone-landscape top bar.** To fit the 24 px reserve, the bar sits to the right of the board during a game. The browser test checks that it does not overlap the board.
7. **Share result.** The overlay's "share result" fallback used to rely on the removed inline field. When there is no clipboard, it now shows the result line in the overlay message instead.
8. **Service worker.** `static/sw.js` caches no assets, so it needed no change (step 7).
9. **More tests than planned.** QR: 7 instead of 4. They check Reed–Solomon against the published HELLO WORLD 1-M example, the format and version bits, and an independent decoder round trip at versions 2, 3, 7 and 10, including UTF-8. Captures: 8 instead of 6.

## Tests

| Command | Result |
|---|---|
| Baseline `uv run --frozen pytest -q`, before any edit | 182 passed, 1 skipped |
| `node --test tests/js/captures.test.mjs tests/js/layout.test.mjs tests/js/share.test.mjs tests/js/qr.test.mjs` | 29 passed (26 new) |
| `node --test tests/js/` | 156 passed (130 before) |
| `uv run --frozen pytest -q tests/test_u1_polish_browser.py` | 7 passed, real headless Chromium |
| `uv run --frozen pytest -q`, full suite | 189 passed, 1 skipped, 0 failed |

- The one skip is unchanged: `tests/test_push_e2e.py`, because this Chromium build cannot subscribe to a push service.
- P1's 44 px accessibility test still passes.
- Every test written in this unit was run, and no linter is configured in the repo.

## Known gaps
- **Frame labels at 360 px.** With coordinates in the frame, a 360 px wide portrait screen gets 42.5 px squares. The 44 px floor holds with the default labels on the squares at every FR4.1 size, and with frame labels at 390 px.
- **Below 360 px wide.** At 320 px, for example, the board keeps 352 px and the page scrolls sideways. This was accepted in the functional spec, since FR4.1 starts at 360 px.
