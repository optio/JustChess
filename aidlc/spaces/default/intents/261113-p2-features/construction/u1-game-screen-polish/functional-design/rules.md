# Business Rules — u1-game-screen-polish

These are the rules for the three front-end features of U1: capture animation, board fit and the share dialog. Sources are `inception/requirements-analysis/requirements.md` (FR2, FR4, FR5, NFR2, NFR3, NFR5) and `inception/refined-mockups/interaction-spec.md`.

```yaml
rules:
  - id: BR1.1
    statement: Every capture is animated on the captured piece's own square, by either side.
    category: policy
    applies_to: board capture animation
    trigger: a position change that removes a piece (local move, live update, replay, rematch reset excluded)
    logic: IF the new position lacks a piece that the previous position had on a square other than the mover's origin THEN a shrink-and-fade copy of that piece plays on that square; for en passant the square is the taken pawn's square, not the arrival square
    violation: the piece disappears without animation (test fails)
    source: FR2.1
  - id: BR1.2
    statement: The player's own move is animated the same way as a received move, including when it is shown before the server confirms it.
    category: policy
    applies_to: board optimistic move
    trigger: the player completes a capture by tap, drag or keyboard
    logic: IF the move is shown optimistically THEN its capture animation starts at once; IF the server then confirms the same move THEN no second animation plays; IF the server rejects it THEN the piece is restored without a capture animation
    violation: double animation, or no animation for own captures
    source: FR2.1
  - id: BR1.3
    statement: The capture animation shrinks the piece to 35 % and fades it to transparent over 260 ms, then the piece appears in the captured row with a 200 ms fade-in.
    category: constraint
    applies_to: board capture animation, captured row
    trigger: BR1.1
    logic: duration 260 ms (token --t-capture), easing --ease-out; captured-row settle 200 ms starting when the shrink ends; total visible motion stays under 300 ms per element (NFR2)
    violation: timing outside the token values
    source: FR2.1, NFR2
  - id: BR1.4
    statement: With reduced motion set, captures do not animate.
    category: policy
    applies_to: board capture animation, captured row
    trigger: prefers-reduced-motion is reduce
    logic: IF reduced motion THEN no animated copy is created and the captured row updates without a fade
    violation: animation plays under reduced motion
    source: FR2.2
  - id: BR1.5
    statement: The capture animation never blocks input.
    category: constraint
    applies_to: board
    trigger: any input during an animation
    logic: the animated copy ignores pointer events and sits above the square; a new move may be started while it runs; a new position finishes any running animation first
    violation: a tap or key press is lost during an animation
    source: FR2.3
  - id: BR1.6
    statement: The captured row lists the pieces each side has taken and is announced through its label.
    category: policy
    applies_to: game screen captured row
    trigger: every position update
    logic: pieces taken are derived from the move list (not counted from the board), ordered queen, rook, bishop, knight, pawn; the row's accessible label names them, for example "Pieces you captured: black pawn, black knight". For the player's own optimistic capture the row is updated optimistically from the move list plus the pending move, when the ghost ends; on confirmation nothing changes, and on rejection the row is recomputed from the server move list without a fade. Only a piece newly added by a live move or an own move gets the 200 ms fade; first render, reconnect and replay render the row without a fade
    violation: the row disagrees with the move list
    source: FR2.1, NFR5
  - id: BR2.1
    statement: The board side is the smaller of the available width and the available height.
    category: calculation
    applies_to: game screen board
    trigger: load, resize, orientation change
    logic: side = min(container width, viewport height (small viewport units) minus the top bar, the status line and the gaps); on desktop (width >= 1024) the side is also capped at 640 px
    violation: the board's bottom edge is below the viewport at scroll position 0
    source: FR4.1, FR4.2, NFR3
  - id: BR2.2
    statement: Phone landscape places the side panel beside the board.
    category: policy
    applies_to: game screen layout
    trigger: viewport in landscape with height <= 500 px
    logic: IF landscape and height <= 500 THEN two columns (board, panel) and the side = viewport height minus 24 px; the top bar is compact. This mode takes precedence over desktop (a 1024 x 500 window is landscape-phone)
    violation: the board overflows vertically in landscape
    source: FR4.1
  - id: BR2.3
    statement: Portrait phones narrower than 400 px show the board edge to edge.
    category: policy
    applies_to: game screen layout
    trigger: portrait and width < 400 px
    logic: IF portrait and width < 400 THEN the board frame drops the side gutter and its corner radius, so 44 px squares fit from 352 px
    violation: squares below 44 px in portrait
    source: FR4.2
  - id: BR2.4
    statement: Board squares are at least 44 px in portrait and on desktop/tablet, and never below 36 px anywhere.
    category: constraint
    applies_to: game screen board
    trigger: BR2.1
    logic: IF the computed square is below 44 px and the layout is not phone landscape THEN the side is raised to 352 px and the content below scrolls; in phone landscape the floor is 36 px
    violation: a square below the floor
    source: FR4.2, NFR5
  - id: BR2.5
    statement: Only the content below the board scrolls.
    category: policy
    applies_to: game screen layout
    trigger: content taller than the viewport
    logic: the scoresheet, actions and lessons drawer may scroll; the board and status line stay within the first screen
    violation: the board needs scrolling
    source: FR4.3
  - id: BR3.1
    statement: The Share button opens a modal dialog and the game screen behind it does not change.
    category: policy
    applies_to: share dialog
    trigger: Share button
    logic: the dialog opens as a modal over a scrim; nothing in the game screen is re-rendered or moved; the old inline link field is no longer used
    violation: the game screen layout changes
    source: FR5.1
  - id: BR3.2
    statement: Copy link copies the invite link and confirms with "Copied".
    category: policy
    applies_to: share dialog
    trigger: Copy link
    logic: IF the clipboard accepts THEN the label reads "Copied" for 1.6 s; IF the clipboard refuses THEN the link input is selected and the label still reads "Copied" so the link is ready to copy by hand
    violation: no feedback, or an error with no fallback
    source: FR5.2
  - id: BR3.3
    statement: App links carry the invite text and link, URL-encoded.
    category: validation
    applies_to: share dialog links
    trigger: dialog render
    logic: Email = mailto with subject "Play chess with me" and body text plus link; WhatsApp = wa.me with text; Telegram = t.me share with url and text; SMS = sms with body; every value passes through URL encoding; "More…" is shown only when the browser offers a share sheet, and a cancelled share does nothing
    violation: an unencoded value or a broken link
    source: FR5.3, NFR4
  - id: BR3.4
    statement: The dialog shows a QR code of the invite link, drawn in the browser.
    category: policy
    applies_to: share dialog
    trigger: dialog open
    logic: the QR code is encoded by the vendored encoder (error correction level M) and drawn black on white on a canvas; no network request is made; the canvas has a text alternative and the link is shown as text beside it
    violation: a request to an outside service, or an unscannable code
    source: FR5.4, NFR4, NFR5
  - id: BR3.5
    statement: The dialog closes with Close, Escape or a click on the backdrop, keeps focus inside while open and returns focus to Share.
    category: policy
    applies_to: share dialog
    trigger: open and close
    logic: native modal dialog; focus starts on Copy link; Tab cycles inside; Escape, Close or a backdrop click closes; focus returns to the Share button
    violation: focus escapes or is lost
    source: FR5.5, NFR5
  - id: BR3.6
    statement: The dialog text depends on whether the opponent has joined.
    category: policy
    applies_to: share dialog
    trigger: dialog open
    logic: IF the room waits for an opponent THEN title "Invite a friend" and the line "Send this link. Whoever opens it first plays <colour>." ELSE title "Share this game" and the line "Anyone with the link can watch; seats are taken."
    violation: wrong text for the room state
    source: FR5.1
```

## Summary

| ID | Rule | Source |
|---|---|---|
| BR1.1 | Every capture animates on the taken piece's square (en passant included) | FR2.1 |
| BR1.2 | Own optimistic moves animate once; rejection restores without animation | FR2.1 |
| BR1.3 | 260 ms shrink to 35 % plus fade, then a 200 ms settle in the captured row | FR2.1, NFR2 |
| BR1.4 | Reduced motion: no capture animation | FR2.2 |
| BR1.5 | Animation never blocks input | FR2.3 |
| BR1.6 | Captured row derived from the move list, with an accessible label | FR2.1, NFR5 |
| BR2.1 | Board side = min(width, available height), capped at 640 px on desktop | FR4.1, FR4.2, NFR3 |
| BR2.2 | Phone landscape: panel beside the board | FR4.1 |
| BR2.3 | Portrait under 400 px: edge to edge | FR4.2 |
| BR2.4 | Squares ≥ 44 px (portrait and desktop), ≥ 36 px in landscape | FR4.2, NFR5 |
| BR2.5 | Only content below the board scrolls | FR4.3 |
| BR3.1 | Share opens a modal; the game screen is unchanged | FR5.1 |
| BR3.2 | Copy link with "Copied", selecting the link when the clipboard refuses | FR5.2 |
| BR3.3 | Email, WhatsApp, Telegram and SMS links URL-encoded; "More…" only with a share sheet | FR5.3, NFR4 |
| BR3.4 | QR code drawn locally | FR5.4, NFR4, NFR5 |
| BR3.5 | Close by Close, Escape or backdrop; focus trap and return | FR5.5, NFR5 |
| BR3.6 | Dialog text for waiting and joined rooms | FR5.1 |
