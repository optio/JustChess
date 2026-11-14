# Requirements — P2 features

Intent: 261113-p2-features. Scope: refactor (custom plan). Depth: Standard.

## Intent analysis

JustChess is a small self-hosted chess site for friends: room links, live play, an opening trainer and notifications ([business-overview](../../../../codekb/JustChess/business-overview.md)). This round has two goals.

1. Players can always find their way back to their games and play on, even when no friend is online. That means an ongoing-games list, pass-along play while waiting, and single player against Stockfish.
2. The site becomes a place to get better at chess. The opening trainer grows, and new trainers cover endgames, tactics and defence.

Smaller items polish the game screen: a capture animation, a board that fits the screen, and a share dialog. The `.env` item is already done.

Request type: enhancement across several components (rooms, live hub, game screen, trainer, new engine service). Complexity: standard to complex. Single player and pass-along add new game modes to the room model.

## Functional requirements

### FR1 Ongoing games on the main screen
- **FR1.1** The main screen lists every game this browser holds a seat in that is unfinished or that ended in the last 7 days, newest activity first. [Q1]
  Pass: with 3 unfinished games, 1 ended 2 days ago and 1 ended 8 days ago, the list shows 4 entries in last-move order.
- **FR1.2** Each entry shows the opponent's name (or the computer's level), your colour, whose turn it is (or the result), when the last move was played, and a small board thumbnail of the current position. [Q2]
- **FR1.3** Tapping an entry opens that game. With no entries, the list area offers to start a game.
- **FR1.4** The server returns the summaries for several rooms in one request. Seat tokens travel only in the request body. A room whose token is wrong or that no longer exists comes back marked "not found", and only then does the browser drop it from its stored seats. A network error or server error never removes stored seats; the list shows what it has and offers to retry.
- **FR1.5** Single-player games (FR6) appear in the same list. [Q11]

### FR2 Capture animation
- **FR2.1** When a piece is taken, by either player, the taken piece shrinks and fades on its square, then appears in the captured-pieces row. This includes en passant, where the taken pawn is not on the arrival square. [Q3]
  Pass: a browser test sees the animation start on the captured piece's square for a normal capture and for en passant.
- **FR2.2** With "reduce motion" set in the operating system, the piece disappears at once without the shrink.
- **FR2.3** The animation never blocks input. The next move can be made while it runs.

### FR3 Pass-along play while waiting
- **FR3.1** While a game waits for an opponent, the creator's waiting screen offers "Play here while waiting". [Q4]
- **FR3.2** In pass-along mode the creator's device moves both sides. Moves are stored on the server as normal moves of that game.
- **FR3.3** The invite link stays valid. Opening it during pass-along play sends a join request, and the joiner sees a "waiting for the creator to accept" screen. [Q5]
- **FR3.4** The creator gets a banner (and a notification when the page is in the background or closed) saying someone wants to join, with Accept and Decline. [Q5] Without push alerts set up, the pending request appears as soon as the creator next opens the game or the main screen, while it has not lapsed.
- **FR3.5** On Accept, the joiner takes the side the creator was playing for the opponent, from the current position. The creator's device can no longer move that side, and the game is a normal online game from then on.
- **FR3.6** On Decline the joiner is told so. A request with no answer lapses after 10 minutes, and the joiner is told to try again later. [Q17]
- **FR3.7** Only one join request is pending at a time. A second visitor during a pending request is told someone is already asking.
- **FR3.8** A game that ends in pass-along mode before anyone joins is kept as a practice game and does not change the room score.
- **FR3.9** Pass-along mode is stored with the game, so it survives the creator reloading or reopening the page. The creator can leave pass-along mode at any time ("Wait for a friend instead"); the position is kept and the game waits for an opponent again.

### FR4 The board fits the screen
- **FR4.1** On the game screen the whole board and the status line are visible without scrolling. This holds on phone portrait (from 360 × 640), on desktop and tablet windows (from 768 × 600) and on phone landscape (from 640 × 360). In landscape the side panel sits beside the board. [Q6]
  Pass: a browser test at 360×640, 390×844, 768×600, 768×1024, 1280×720, 640×360 and 844×390 finds the board's bottom edge inside the viewport at scroll position 0.
- **FR4.2** The board size is the smaller of the available width and the available height. Board squares are at least 44 px in portrait and on desktop/tablet, and never below 36 px. Squares below 44 px are allowed only in phone landscape. [Q18] On portrait phones narrower than 400 px the board runs edge to edge (no side gutter), so 44 px squares fit from 352 px wide.
- **FR4.3** Content below the board (the scoresheet and the controls) may scroll. The board itself never needs scrolling to be seen.

### FR5 Share dialog
- **FR5.1** The share button opens a modal dialog. The game screen behind it does not change. [desc]
- **FR5.2** The dialog shows the invite link and a "Copy link" button that confirms the copy ("Copied").
- **FR5.3** The dialog has links that open Email (with subject and message filled in), WhatsApp, Telegram and SMS with the invite text. It also has a "More…" button for the device's share sheet where the browser supports one. [Q7]
- **FR5.4** The dialog shows a QR code of the invite link, drawn in the browser. No outside service is called. [Q8]
- **FR5.5** The dialog closes with its Close button, the Escape key, or a click outside it. Focus stays inside the dialog while it is open and returns to the share button when it closes.

### FR6 Single player against Stockfish
- **FR6.1** The main screen offers "Play the computer". The player picks a colour (White, Black or Random) and one of five named levels: Beginner, Casual, Club, Strong, Maximum. [Q9]
- **FR6.2** Each level is a fixed engine setting. The computer replies on its own after each of the player's moves.

  | Level | Skill level | Thinking time |
  |---|---|---|
  | Beginner | 0 | 0.1 s |
  | Casual | 5 | 0.3 s |
  | Club | 10 | 0.6 s |
  | Strong | 15 | 1 s |
  | Maximum | 20 | 2 s |

- **FR6.3** The player can take back moves: one takeback removes the player's last move and the computer's reply. Takebacks are unlimited. [Q10] Takeback is unavailable until the player has made a move, and while the computer is thinking.
- **FR6.4** The player can ask for a hint, which shows the engine's suggested move as an arrow on the board. [Q10]
- **FR6.5** Single-player games are saved on the server, appear in the ongoing-games list (FR1) and can be resumed later. If it is the computer's turn on resume, it moves. [Q11]
- **FR6.6** The blunder-warning setting applies in single player as in online games.
- **FR6.7** When Stockfish is not available, "Play the computer", hints, and the endgame trainer are shown as unavailable with the reason. A saved single-player game can still be opened and viewed, with a note that the computer cannot move until the engine is back. The rest of the site works as before.
- **FR6.8** The player can resign and start a rematch (colours swapped). Draws by the rules (stalemate, repetition, 50-move rule, insufficient material) end the game; the computer is not offered draws.
- **FR6.9** Single-player games keep their own score against the computer and never change any online room score.

### FR7 More opening lessons
- **FR7.1** New opening lessons in the existing lesson format: Ruy Lopez, Sicilian Defence, French Defence, Caro-Kann, Queen's Gambit, London System, King's Indian Defence, Scandinavian Defence. [Q12]
- **FR7.2** New trap lessons: Legal's mate, Fried Liver Attack, Fishing Pole trap, Englund Gambit trap. [Q12]
- **FR7.3** Every lesson has a note for each move, and its walkthrough and practice work like the existing lessons.
  Pass: a test loads every lesson file and replays every line legally.

### FR8 Situation trainers
- **FR8.1** A trainer hub on the learn page groups the trainers: Openings, Traps, Endgames, Tactics, Defence. [Q13]
- **FR8.2** **Endgames:** at least 3 positions each for mate with queen, mate with rook, king-and-pawn endings and opposition, from hand-written files in the repo. Stockfish defends at full strength. The player passes by reaching the stated goal: mate, promotion, or, where the position says "hold the draw", reaching 30 moves without losing, a threefold repetition, or the 50-move rule. [Q13, Q14, Q15]
- **FR8.3** **Tactics:** puzzles on forks, pins, skewers, discovered attacks, mate in 1 and mate in 2. The repo ships a curated subset of the free Lichess puzzle collection (CC0), about 300 puzzles per theme. The player solves a puzzle by playing its solution moves; the opponent's replies come from the puzzle. A wrong move is shown and can be retried, and a hint is available. [Q13, Q14, Q16]
- **FR8.4** **Defence:** at least 4 hand-written lessons on meeting early attacks, such as the Scholar's mate attack, the Fried Liver and early queen raids, with walkthrough and practice like the opening lessons. [Q13, Q14]
- **FR8.5** Each device remembers which positions and puzzles were solved, and the hub shows progress per group.
- **FR8.6** The site credits the Lichess puzzle data and its CC0 licence.

### FR9 Settings from a .env file (done)
- **FR9.1** The app loads settings from `.env` at the project root at start-up. A variable already set in the shell wins over the file. A missing file is fine, and a malformed line is skipped and logged without its value. [desc]
- **FR9.2** `.env` is ignored by git, and `.env.example` documents every setting. The Web Push key stays in its own file outside the repository, and `.env` only names that file.
  Status: implemented and tested (`justchess/envfile.py`, `tests/test_envfile.py`). It stays here for traceability.

## Non-functional requirements

- **NFR1 Engine load on the Raspberry Pi.** At most one Stockfish search runs at a time, with ≤ 2 threads and ≤ 64 MB hash. Engine work never runs on the web server's event loop, so other games keep their response times. Requests for the engine (computer moves, hints, endgame defence) wait their turn in order; the page shows "thinking…" while waiting. With no other engine request waiting, the computer's reply is shown within 3 s at the 95th percentile on the Pi at every level (thinking times in FR6.2).
- **NFR2 Animation timing.** The capture animation lasts ≤ 300 ms and respects reduced motion (FR2.2).
- **NFR3 Layout.** FR4.1 holds at every viewport size listed in FR4.1 with the default font size, checked by a browser test.
- **NFR4 Security.**
  - Seat tokens are never put in URLs or logs, including in the batch summary request (FR1.4) and in join requests.
  - Only the creator's seat token can accept or decline a join request.
  - Join requests are limited to one pending request per room (FR3.7), and one client may send at most 5 join requests per minute (more are refused with "try again shortly").
  - Share links are built with URL encoding. The QR code is drawn locally.
  - Lesson and puzzle files are validated when loaded, and a bad file is skipped with a log line.
- **NFR5 Accessibility.**
  - The share dialog is a labelled modal with a focus trap and Escape to close.
  - Animations are never the only signal: the captured-pieces row and the move list still update.
  - Tap targets stay ≥ 44 px except board squares in phone landscape (FR4.2).
- **NFR6 Size.** Shipped puzzle data is ≤ 5 MB in the repo, and nothing is downloaded for trainers at start-up.
- **NFR7 Compatibility.** No backward compatibility is needed (decided by the user after requirements approval). A database file with an older schema version is moved aside to `justchess.sqlite3.old` and a fresh version-4 database is created; existing rooms, games, scores and seat links are not kept. The real database file is never opened by tests.
- **NFR8 Quality.** The existing test suite stays green under `uv run --frozen pytest -q`. Each FR has at least one automated test (Python, JS unit, or browser).

## Constraints

- **Runs as one process.** The app stays a single Uvicorn process on a Raspberry Pi. Stockfish is the pinned version already installed by `stockfish_install.py` ([architecture](../../../../codekb/JustChess/architecture.md)).
- **Same stack.** FastAPI, SQLite, python-chess and native ES modules with no build step, keeping the package layout in [code-structure](../../../../codekb/JustChess/code-structure.md).
- **Security rules from earlier rounds still hold:** no secrets in the repo, tokens never in URLs, and the real `justchess.sqlite3` is never touched by tests.

## Assumptions

- **Named levels.** The five levels map to Stockfish "Skill Level" 0 / 5 / 10 / 15 / 20 with growing move time. Reason: the engine supports skill levels, and named levels are what was chosen in Q9.
- **Signal.** Signal has no public link for sharing text, so it is reached through the device's share sheet ("More…") rather than its own button. Reason: there is no web share URL for Signal. This differs from the Q7 answer and was accepted by the user at the requirements review (finding R-03).
- **Pass-along join.** In pass-along mode the opponent's side is the side the creator did not pick when creating the room. Reason: rooms already fix colours at creation.
- **Progress storage.** Trainer progress (FR8.5) is kept per device in browser storage, like other settings. Reason: there are no accounts.
- **Defence lessons.** The defence lessons are original texts written for this project. The trap and opening lines are standard chess theory written up in our own words.

## Out of scope

- Accounts or syncing games across devices beyond the existing "continue on another device".
- Online play against other people's engines, engine analysis of finished games, and adjustable thinking time per move.
- Downloading or updating the full Lichess puzzle database.
- Signal as a dedicated button (see Assumptions).

## Open questions

- None that block design. The piece-set licence credit from the previous round is still the user's decision and is not part of this work.

## Sources

- Initial description: the user's 8 requirements and the `.env` line [desc]
- Answers Q1–Q18 in `requirements-analysis-questions.md` [Q1]–[Q18]
- FR3.9, FR6.8, FR6.9 and the added detail in FR1.4, FR3.4, FR4.1–FR4.2, FR6.2–FR6.3, FR6.7, FR8.2, FR8.4, NFR1 and NFR4: decided by the user at the requirements review (findings R-01 to R-06, `reviews/review-01.md`)
- Left for design (finding R-09): how a client is identified for the join-request limit, where the score against the computer is shown, and whether repetition and 50-move draws end the game automatically
- Code map: [business-overview](../../../../codekb/JustChess/business-overview.md), [architecture](../../../../codekb/JustChess/architecture.md), [code-structure](../../../../codekb/JustChess/code-structure.md)
