# Frontend Components — u1-game-screen-polish

All of these are native ES modules with no build step. They extend the existing modules from intent 261112.

## Component hierarchy

```
Page shell (templates/index.html)
├── Top bar
│   └── Share button ──opens──> ShareDialog (new, native <dialog>)
│                                  ├── link input + Copy link
│                                  ├── app links (Email, WhatsApp, Telegram, SMS, More…)
│                                  └── QrCode canvas (vendored encoder)
└── Game screen (screens/game.js)
    ├── Board (board/board.js)  ── capture animation (changed)
    ├── Status line
    ├── CapturedRow (new)
    ├── Actions
    └── Scoresheet
```

## Board (`static/js/board/board.js`, `board.css`) — changed

- **State:** unchanged (shown position, interaction state, running animations).
- **Change, capture:** `fadeCaptured` becomes a shrink-and-fade: scale 1 → 0.35 and opacity 1 → 0, over `--t-capture`, with easing `--ease-out`. The token changes from 150 ms to 260 ms. The ghost copy keeps `pointer-events: none` (BR1.3, BR1.5).
- **Change, optimistic capture:** the optimistic render path runs `animate(diff)` with the capture. The confirming render compares against the shown position, so it does not animate again (BR1.2).
- **Props:** unchanged.
- **Events:** a new optional `onCaptureShown(capture)` callback fires after the ghost ends, so the game screen can settle the captured row.

## CapturedRow (new, inside `screens/game.js`; pure helper in `static/js/captures.js`)

- **Props:** `moves` (the snapshot move list, SAN plus UCI), `you` (your colour), `reducedMotion`.
- **Derived:** `capturedPieces(moves)` returns `{ byWhite: [...], byBlack: [...] }`, ordered Q, R, B, N, P, using the move list and replaying from the start position with the existing chess helpers (BR1.6).
- **Render:**
  - The two rows are labelled "Captured".
  - The latest added glyph gets the `is-new` class for the 200 ms settle. Under reduced motion it gets no class.
  - `aria-label` reads, for example, "Pieces you captured: black pawn, black knight".
- **No state** beyond the last rendered list, which is used to find the newly added piece.
- **Optimistic own capture:** the game screen passes the pending move with the move list, so the row updates when the ghost ends (`onCaptureShown`). On confirmation the list is unchanged. On rejection the row is recomputed from the server list without a fade. First render, reconnect and replay never fade (BR1.6).

## BoardFit (CSS in `app.css` and `board.css`; small helper `static/js/layout.js`)

- **CSS:** the board column width is `min(100%, calc(100svh - var(--reserve)), var(--cap))`, with `--reserve` set per mode. `--cap` is 640 px on desktop and `none`/100% otherwise. The landscape-phone media query comes after desktop in the stylesheet, so it wins when both match. The floor is `max(352px, …)` in portrait and desktop, and `max(288px, …)` in landscape-phone.
- **Modes:** from media queries, `(orientation: landscape) and (max-height: 500px)` for landscape-phone and `(min-width: 1024px)` for desktop. Under 400 px in portrait the gutter is removed and the frame radius set to 0 (BR2.1–BR2.4).
- **Helper:** `layout.js` exports `boardMode(width, height)` and `boardSide(width, height)`. They mirror the CSS so the rules can be unit-tested and the browser test can compare. Nothing calls them at runtime.

## ShareDialog (new, `static/js/share-dialog.js`; pure helpers stay in `share.js`)

- **Props:** `{ url, waiting, colourForJoiner, navigator }`.
- **Pure helpers added to `share.js`:**
  - `appLinks(url, text)` returns `[{ id, label, href }]` for email, whatsapp, telegram and sms, all URL-encoded.
  - `dialogText({ waiting, colour })` returns `{ title, line }`.
- **DOM:**
  - A `<dialog aria-labelledby>` containing the title, the line, a read-only `<input>` labelled "Invite link", the Copy link button, the app link grid, "More…" (rendered only when `chooseShareMethod(nav) === "share"`), the QR canvas with `role="img"` and an `aria-label`, and Close.
- **Behaviour:**
  - `open()` calls `showModal()` and focuses Copy link.
  - A click on the backdrop (the dialog element itself) closes it.
  - Escape uses the dialog's native close.
  - On `close`, focus returns to the trigger.
  - Copy uses `copyText()`. On "field" it selects the input. Either way the label reads "Copied" for `COPIED_MS` (BR3.2).
  - "More…" calls `shareLink()`.
- **Replaces:** app.js's inline share fallback (`#share-fallback`, `#share-field`). Those elements are removed from `index.html` (BR3.1).

## QrCode (new, `static/js/vendor/qrcode.js` plus `static/js/qr-canvas.js`)

- **Vendored encoder:** a small MIT-licensed QR code generator as an ES module, unmodified, with its licence header. It is credited in `static/ASSETS.md` (ADR-008).
- **`drawQr(canvas, text)`:** encodes at level M and draws modules black on white with a 4-module quiet zone. The canvas is scaled for device pixel ratio.
- **Loading:** the encoder loads with a dynamic `import()` on first open. On failure the area shows "QR code unavailable", and the error is logged (functional-spec error cases).

## API integration points

None. U1 reads only the existing game snapshot (position, move list, room state) and the invite URL that `share.js` already builds.

## Validation

There are no forms. The one input is the read-only link field.

## Sources
- `rules.md`, `functional-spec.md`
- `inception/refined-mockups/interaction-spec.md` (CaptureAnimation, BoardFit, ShareDialog)
