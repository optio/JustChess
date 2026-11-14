# Mockups — JustChess P2 features

Clickable mockup: `mockup.html` in this folder, published privately at https://claude.ai/artifact/Ay7onaC7pAo12zJxaDaqyH. Visual language: the "Club Set" design system from intent 261112 (walnut board, scoresheet paper, brass accent, Libre Caslon and Atkinson Hyperlegible). Nothing new is added to the palette; see `design-system-mapping.md`.

No user stories or rough mockups exist for this intent (the plan skips them), so screens are designed from `inception/requirements-analysis/requirements.md` and the answers in `refined-mockups-questions.md`.

## Screen 1: Main screen (FR1.1–FR1.5, FR6.1) [Q1, Q3]

Wide screens (≥ 900 px): two columns. Phones: the list stacks under the actions.

```
+----------------------------------------------------------------+
| [logo] JustChess                                               |
+--------------------------------------+-------------------------+
| Play a friend. Play the computer.    | Your games              |
| Get better.                          | [thumb] Sam             |
| No accounts. Start a game and send   |   You play White · 4 min ago   (Your move) |
| the link, play the computer, or ...  | [thumb] Computer, Club  |
|                                      |   You play Black · yesterday   (Your move) |
| [Start a game] [Play the computer]   | [thumb] Alex            |
| [Train]                              |   You play Black · 2 h ago     (Alex to move) |
|                                      | [thumb] Robin  (greyed) |
| Have a room code? [______] [Join]    |   Ended 2 days ago · checkmate (You won) |
+--------------------------------------+-------------------------+
```

- The list is a scoresheet-style paper panel. Each row is one link with a thumbnail, the opponent (or "Computer, <level>"), your colour and the time of the last move, and a pill showing whose turn it is or the result.
- "Your move" pills use baize (the redesign's "your move" colour). Finished games come after the unfinished ones, with a desaturated thumbnail and muted text. [Q3 A]
- Order: unfinished games, newest activity first, then finished games, newest first.
- **Empty state:** "No games yet. Start one above or play the computer."
- **Loading:** the panel shows "Loading your games…".
- **Error (network):** the games already known stay listed as stored, with "Couldn't refresh. Retry" (FR1.4).
- **Headline copy change:** the headline becomes "Play a friend. Play the computer. Get better." The "Learn an opening" button is renamed "Train" and opens the trainer hub.
- **Pending join request (FR3.4, review R-06):** when one of your pass-along games has a pending join request, its row shows a brass-outlined "Join request" pill and moves to the top of the list. Opening the row shows the Accept/Decline banner. Without push alerts set up, this is how the creator finds the request.
- **Notification permission (R-06):** asked only when you switch on Notifications in Game settings, as today. The join-request alert uses the same permission; nothing new is asked.
- **Clickable states in the mockup:** Normal, Loading, Empty, Network error, No Stockfish, Join request.

## Screen 2: Play the computer panel (FR6.1) [Q2 A]

The panel opens in place under the buttons, and "Play the computer" gets `aria-expanded="true"`.

```
[Start a game] [Play the computer ▾] [Train]
+-------------------------------------------+
| Your colour   [White] [Black] [Random]    |
| Computer level [Beginner][Casual][Club]   |
|                [Strong][Maximum]          |
| [Start]  Cancel                           |
+-------------------------------------------+
```

- Defaults: White, Casual. The device remembers the last choice.
- **Stockfish unavailable (FR6.7):** the button is disabled, with the line "Playing the computer needs Stockfish, which isn't installed on this server."

## Screen 3: Game screen and board fit (FR4.1–FR4.3, FR2.1–FR2.3, FR6.2–FR6.9)

```
Phone portrait               Desktop (≥1024)                    Phone landscape
+------------------+         +--------------------+-----------+  +-----------+-----------+
| bar      [Share] |         |                    | players   |  |           | status    |
|+----------------+|         |      board         | status    |  |  board    | captured  |
||    board       ||         |  (min(640, vh-110))| captured  |  | (vh-24)   | actions   |
|| edge to edge   ||         |                    | actions   |  |           | sheet ↓   |
||  under 400 px  ||         |                    | sheet     |  |           |           |
|+----------------+|         +--------------------+-----------+  +-----------+-----------+
| status           |
| captured, actions|
| sheet (scrolls) ↓|
```

- Board size = min(available width, viewport height − top bar − status line). The board never needs scrolling; the sheet below it may scroll (FR4.3).
- **Capture (FR2.1):** the moving piece slides (200 ms, the existing move slide). The taken piece shrinks to 35 % and fades out on its square over 260 ms, then appears in the "Captured" row with a 200 ms settle. For en passant the shrink plays on the taken pawn's square. Try it with the "Show a capture" button in the mockup.
- **Single player extras:**
  - **Status line:** "Computer is thinking…" while the engine works, or "Waiting for the computer…" while queued (NFR1).
  - **Actions:**
    - Take back: disabled until you have moved, and while the computer thinks.
    - Hint: shows a baize arrow on the board plus a line of text, such as "Hint: castle short".
    - Resign: a quiet button.
  - **Score:** the line under the scoresheet reads "Score against the computer (this level): you 1, computer 3, draws 0" (scores are kept per level) (resolves review finding R-09, where the computer score is shown).
  - **Saved game, Stockfish missing:** the board shows read-only. The status reads "The computer can't move right now. Stockfish isn't available. Your game is saved." Hint is disabled.
- **Single-player end of game (FR6.8, review R-01):**
  - **Resign** asks for confirmation in a dialog: "Resign this game? The computer gets the win. You can start a rematch afterwards." The buttons are [Keep playing] and [Resign].
  - **When the game ends**, a result card sits over the board, as in the redesign's game-over card. It has [Rematch] and [Back to your games], with the line "Rematch swaps colours. Level stays the same." The card's text by result:

    | Result | Title | Line |
    |---|---|---|
    | Win | Checkmate | You win with <move> |
    | Loss | Checkmate | The computer wins |
    | Resign | You resigned | The computer wins |
    | Stalemate | Draw | Stalemate |
    | Repetition | Draw | Threefold repetition |
    | 50-move rule | Draw | Fifty moves without a capture or pawn move |
    | Insufficient material | Draw | Neither side can mate |

  - **Draws by rule end the game automatically** in single player, which settles that part of review finding R-09. There are no draw offers.
  - The score line updates.
- **Clickable states in the mockup (Computer game tab):** Thinking, Queued, Resign?, each result, No Stockfish.

## Screen 4: Share dialog (FR5.1–FR5.5) [Q7 B, Q8 A]

```
+--------------------------------------+
| Invite a friend                      |
| Send this link. Whoever opens it     |
| first plays Black.                   |
| [https://…/r/K7Q2PX      ] [Copy link]|
| [Email] [WhatsApp] [Telegram] [SMS]  |
| [More…]                              |
| ---------------------------------    |
| [QR]  Sitting together? Your friend  |
|       can scan this with their phone.|
|                              [Close] |
+--------------------------------------+
```

- A modal on a scrim; the game screen behind it does not change.
- "Copy link" becomes "Copied" for 1.6 s. If the clipboard is refused, the link text is selected instead.
- "More…" appears only where the browser supports a share sheet, and Signal is reached through it.
- The QR code is drawn in the browser.
- **After the opponent joins:** the title becomes "Share this game" and the line reads "Anyone with the link can watch; seats are taken."

## Screen 5: Waiting and pass-along (FR3.1–FR3.3, FR3.8, FR3.9)

```
Waiting                                Pass-along
status: Waiting for your friend        status (baize): Pass-along: White to move
        Send the link. You can play            Hand the device over after each move.
        here while you wait.                   The invite link still works.
[Play here while waiting] [Share]      [Wait for a friend instead]
                                       scoresheet
                                       "Practice game: the room score changes only once a friend joins."
```

## Screen 6: Join request (FR3.3–FR3.7)

- **Creator's side:** a brass-bordered banner above the status reads "Someone wants to join as Black. They will take over Black from this position. Expires in 9:41." It has [Accept] and [Decline]. In a background tab, or with the tab closed, a notification carries the same text.
- **Joiner's side:** "Waiting for the creator to accept. You'll play Black from the current position."
  - On decline: "The creator declined. You can ask again later."
  - When the request lapses: "Nobody answered. Try again later."
  - When another request is already pending: "Someone else is already asking to join. Try again in a few minutes."
  - When a client sends too many requests: "Too many requests. Try again shortly."
- **Clickable states in the mockup:** Creator, Joiner: waiting, declined, lapsed, busy, too many.

## Screen 7: Trainer hub (FR8.1, FR8.5, FR8.6, FR7.1–FR7.2) [Q4 A]

```
Train
[Openings 2/10] [Traps 1/4] [Endgames 1/4] [Tactics 0/6] [Defence 0/4]
2 of 10 done on this device
+------------------------------------------+
| Italian Game                 Done [Learn] |
| Ruy Lopez                         [Learn] |
| ...                                       |
+------------------------------------------+
```

- The tabs follow the ARIA tablist pattern. The counts show progress kept on this device.
- The Tactics tab ends with the credit "Puzzles from the Lichess puzzle database, released under CC0."
- The Endgames tab notes that it needs Stockfish. Without it, the rows show "Needs Stockfish" and their buttons are disabled.

## Screen 8: Tactics puzzle (FR8.3)

- The status reads "White to move: find the fork", with "Forks · puzzle 12 of 300".
- A wrong move is taken back after a short pause. A banner explains it, for example "Not this one. Nxc6 takes a knight, but Black takes back. Try again."
- Actions: Hint (highlights the piece to move), Show solution (plays the line slowly), Next puzzle.
- When solved: "Solved" in baize, then Next puzzle.
- **Clickable states in the mockup:** Your move, Wrong move, Solved.

## Screen 9: Endgame trainer (FR8.2)

- The status shows the goal, for example "Mate with the rook. Goal: checkmate. Position 1 of 3." A draw position instead says "Goal: hold the draw (30 moves, repetition or 50-move rule)".
- The computer defends at full strength, with the same queue states as single player.
- **On success:** "Done! Mate in 14 moves." The tab count updates.
- **On failure:** "The computer escaped / won. Start again."
- **Clickable states in the mockup:** Mate goal, Done, Escaped, Hold the draw (with a move counter, "Move 12 of 30"), Draw held. The Trainer hub tab also has a "No Stockfish" state, where the Endgames rows show the reason and disabled buttons.

## States not shown visually

Every state listed above can be clicked in the mockup, using the States row under the tabs. Two things are illustrative only:
- The share dialog in the mockup is a plain overlay. The app uses the native `<dialog>` element with `showModal()`, as `interaction-spec.md` says.
- The QR code is a placeholder pattern. The app draws a real, scannable code.

## Sources

- Requirements: `inception/requirements-analysis/requirements.md` (FR1–FR9, NFR1–NFR8)
- Answers: `refined-mockups-questions.md` [Q1]–[Q5]
- Design system: intent 261112 `inception/refined-mockups/design-system-mapping.md`
