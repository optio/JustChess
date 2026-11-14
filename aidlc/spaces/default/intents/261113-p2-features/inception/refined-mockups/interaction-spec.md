# Interaction Specification — JustChess P2

Component-level specs follow `.claude/knowledge/aidlc-design-agent/component-spec-template.md`. Durations and sizes are the values the build must use.

## Component: YourGamesList (FR1)
- **Purpose:** show this browser's games and reopen one.
- **Data:** the seats stored on this device; one batch summary request (tokens in the body).
- **States:**
  - Loading: "Loading your games…"
  - Loaded
  - Empty: "No games yet. Start one above or play the computer."
  - Partial error: the stored rows stay listed with "Couldn't refresh. Retry".
  - A row whose server answer is "not found" is removed silently.
- **Row:** one `<a>`, at least 72 px tall, with a thumbnail, name, meta line and pill. The accessible name reads, for example, "Game with Sam, you play White, your move, last move 4 minutes ago".
- **Order:** unfinished games by last move (newest first), then finished games from the last 7 days.
- **Refresh:** on load, on return to the tab (`visibilitychange`), and every 60 s while visible.
- **Join request:** a row whose summary carries a pending join request shows the "Join request" pill and sorts first (FR3.4 fallback without push).

## Component: ComputerSetupPanel (FR6.1, FR6.7)
- **Trigger:** "Play the computer" toggles the panel; the button has `aria-expanded` and `aria-controls`.
- **Controls:**
  - Colour: White, Black or Random. Level: Beginner, Casual, Club, Strong or Maximum.
  - Both are segmented button groups with `aria-pressed`. Arrow keys move within a group.
- **Defaults:** White and Casual, or the last choice remembered per device.
- **Actions:** Start creates the game and opens the game screen. Cancel and Escape close the panel and return focus to the trigger.
- **Disabled state:** when the engine is unavailable, the trigger is `disabled` and the reason shows as text beside it.

## Component: CaptureAnimation (FR2, NFR2)
- **Trigger:**
  - A capture is any move whose result removes a piece: a local move, a move received live, or a takeback redo.
  - En passant uses the square of the taken pawn.
- **Sequence:**
  1. The mover slides 200 ms (existing).
  2. At the same time, a copy of the taken piece is placed absolutely on its square and runs `scale(1 → .35)` and `opacity(1 → 0)` over 260 ms with `cubic-bezier(.2,.7,.2,1)`.
  3. After that, the piece appears in the captured row with a 200 ms fade-in.
- **Input:** the board stays interactive throughout. The copy has `pointer-events:none`, and the next move can start at once.
- **Reduced motion:** the copy is never created, and the captured row updates without the fade.
- **Accessibility:** the move announcement already says "takes" (for example "Bishop takes f7"). The captured row's label updates.

## Component: BoardFit (FR4)
- **Rule:** board side = min(container width, viewport height (`100svh`) − top bar − status line − gaps).
  - Phone portrait: the reserved height is the top bar plus the status line (about 150 px).
  - Desktop: the board sits beside the side panel, capped at 640 px.
  - Landscape with height ≤ 500 px: the board sits beside the panel, and the side = viewport height − 24 px.
- **Edge to edge:** portrait under 400 px wide drops the side gutter around the board and squares the frame corners.
- **Floor:** squares never go below 36 px. Below 44 px is allowed only in landscape.
- **Re-measure:** on `resize` and `orientationchange`.

## Component: ShareDialog (FR5)
- **Element:** a native `<dialog>` opened with `showModal()`, labelled by its title. The mockup's overlay is illustrative only (review R-04).
- **Focus:** opens on "Copy link". Tab cycles inside the dialog. Escape, Close or a click on the backdrop closes it, and focus returns to the Share button.
- **Copy:** calls `navigator.clipboard.writeText`. On success the label is "Copied" for 1.6 s. If the clipboard is refused, the input is selected and the label is still "Copied" (the text is ready to copy by hand).
- **Links (all URL-encoded):**
  - Email: `mailto:?subject=Play chess with me&body=<text> <link>`
  - WhatsApp: `https://wa.me/?text=`
  - Telegram: `https://t.me/share/url?url=&text=`
  - SMS: `sms:?&body=`
- **More…:** shown only if `navigator.share` exists. It opens the share sheet and stays silent if the person cancels.
- **QR code:** drawn on a canvas from the link by a small QR encoder shipped with the app. No network call.

## Component: PassAlong (FR3.1, FR3.2, FR3.8, FR3.9)
- **Enter:** "Play here while waiting" asks the server to switch the room to pass-along. The board then lets the creator move either colour.
  - The status shows "Pass-along: <colour> to move" in baize, because it is always your move.
- **Leave:** "Wait for a friend instead" switches back to waiting, keeping the position. If it is the opponent's side to move, the board locks.
- **Score:** the practice-game note shows until someone joins. A game that ends in pass-along shows "Practice game over" and does not change the score.

## Component: JoinRequest (FR3.3–FR3.7, NFR4)
- **Joiner:**
  - Opening the link during pass-along sends a request and shows the waiting text. The page listens on the live connection for the answer.
  - A 10-minute countdown runs on the server. When it ends, the joiner sees the lapse message.
- **Creator:**
  - The banner has `role="alert"` and Accept and Decline buttons. A countdown in the text refreshes once a minute; a per-second refresh would be noisy for screen readers.
  - A notification goes out through the existing notification paths ("join request" event).
- **Accept:** the joiner gets the opponent seat and the board updates on both sides. The creator's board locks the opponent's pieces.
- **Busy and rate limit:** both refusals show as text on the joiner's page.

## Component: TrainerHub (FR8.1, FR8.5)
- **Tabs:** ARIA tablist. Left and Right arrows move between tabs, and Home and End jump to the first and last. The selected tab is remembered per device.
- **Rows:** title, an optional subtitle (count or goal), a "Done" mark, and one action button (Learn, Solve or Play).

## Component: PuzzleBoard (FR8.3)
- **Moves:** the player moves. A correct move auto-plays the scripted reply after 300 ms.
- **Wrong move:** shown for 600 ms, then taken back, with a banner explaining it. Retries are unlimited.
- **Hint:** first highlights the piece to move, then shows an arrow.
- **Solution:** plays the whole line at 800 ms per move.

## Component: ComputerGameEnd (FR6.8, FR6.9)
- **Resign:**
  - Opens a native `<dialog>` with [Keep playing], which is the default focus, and [Resign].
  - Escape counts as Keep playing.
- **End of game:**
  - Detected by the server: mate, stalemate, threefold repetition, the 50-move rule and insufficient material all end the game automatically.
  - A result card covers the board. Its title and line come from the table in `mockups.md`.
  - Focus moves to [Rematch], and the card is announced through the status line.
- **Rematch:** creates a new single-player game with colours swapped at the same level, then opens it.
- **Score:** "Score against the computer" updates when the game ends. It is kept per level, and the line shows the current level's score.

## Component: EngineStatus (NFR1, FR6.7)
- **States:**
  - Queued: "Waiting for the computer…"
  - Thinking: "Computer is thinking…"
  - Done
  - Unavailable: a reason line with the related buttons disabled.
- The status line uses `aria-live="polite"`.

## Sources
- `inception/requirements-analysis/requirements.md`; `mockups.md`; answers [Q1]–[Q5] in `refined-mockups-questions.md`.
