# Units of Work — JustChess P2

These units group the components in `inception/domain-design/components.md`, following `inception/domain-design/decisions.md` (ADR-001 to ADR-009). Together they cover every requirement in `inception/requirements-analysis/requirements.md`. You chose the six-unit feature split [Q1], built one at a time [Q2], and approved the plan.

**Deployment model:** every unit ships into the one FastAPI app on the Raspberry Pi: a single process serving the API, the WebSocket, the ES modules and the service worker. No unit deploys on its own.

| Unit ID | Directory | Kind | Size | Components |
|---|---|---|---|---|
| U1 | u1-game-screen-polish | ui | M | WebClient: capture animation, board fit, share dialog with QR encoder |
| U2 | u2-data-and-your-games | service | M | Rooms and Games schema v4, HttpApi batch summaries, WebClient Your games list |
| U3 | u3-pass-along | service | L | Rooms modes and JoinRequest, LiveUpdates request sockets, Notifications join alert, HttpApi rate limit and trusted proxies, Housekeeping expiry, WebClient pass-along and join screens |
| U4 | u4-play-the-computer | service | L | Engine process and queue, ComputerOpponent, Games takeback and automatic draws, HttpApi computer flows (ADR-009), WebClient setup panel and computer game screen |
| U5 | u5-lessons-and-puzzles | service | L | Lessons kinds and new content, Puzzles with the curated set, HttpApi trainer routes, WebClient trainer hub, puzzle screen and progress |
| U6 | u6-endgame-trainer | service | M | Endgames with positions and judging, HttpApi endgame routes, WebClient endgame screen |

FR9 (the `.env` file) is already built and tested (`justchess/envfile.py`). The one addition, `JUSTCHESS_TRUSTED_PROXIES`, belongs to U3.

## U1 — u1-game-screen-polish

- **Description:** front-end improvements to the game screen. No server changes.
- **Responsibilities:**
  - **Capture animation (FR2):**
    - Detects a capture from the position before and after a move, including en passant, so it works for local, live and replayed moves.
    - The taken piece shrinks and fades over 260 ms, then a 200 ms settle in the new captured-pieces row.
    - Respects reduced motion and never blocks input.
  - **Board fit (FR4):**
    - Board size is the smaller of the width and the available height.
    - Portrait under 400 px runs edge to edge. Landscape (height ≤ 500 px) puts the side panel beside the board.
    - Squares never go below 36 px.
  - **Share dialog (FR5):**
    - Native `<dialog>` with Copy, Email, WhatsApp, Telegram, SMS and "More…" (the share sheet).
    - A QR code drawn from a vendored, MIT-licensed encoder in `static/js/vendor/`, credited in `static/ASSETS.md` (ADR-008).
    - Focus is trapped inside, Escape closes it, and focus returns to the Share button.
- **Tests:** JS unit tests (capture detection, board size maths, share link building, QR output for a known input). Browser tests: the board fits at all 7 viewport sizes; dialog focus and Escape; reduced motion.
- **Notes:** this extends the existing board, game and share modules. P1's 44 px accessibility test stays green in portrait and on desktop.

## U2 — u2-data-and-your-games

- **Description:** the data foundation the next units build on, plus the ongoing-games list.
- **Responsibilities:**
  - **Schema v4 (ADR-010):** created fresh. A file at any other version is moved aside to `justchess.sqlite3.old`. The in-place upgrade code is removed, since no backward compatibility is needed.
  - **New columns:**
    - Room: `mode` (new friend rooms start as `waiting`), `computer_level`.
    - Seat: `is_computer`, and `token_hash` is nullable.
    - Game: `counted` (default 1).
    - Move: `captured_piece`, `captured_square`.
  - **New table:** `join_requests`, created here and used by U3.
  - **Games:** writes capture info for new moves and exposes it in the snapshot.
  - **Batch summaries (FR1.4):** a POST route takes a list of room code and seat token pairs in the body and returns, for each room, the opponent label, your colour, whose turn it is or the result, the last move time, the current position for the thumbnail, and any pending join request. Wrong tokens and missing rooms come back as "not found". The request is size-limited and origin-checked.
  - **Your games list (FR1.1–FR1.3, FR1.5):** shown beside the actions on wide screens and below them on phones. Unfinished games come first, then games that ended in the last 7 days, greyed. The list has loading, empty and network-error states. A stored seat is dropped only on "not found". The list refreshes on load, when the tab regains focus, and every 60 s.
  - **New headline:** "Play a friend. Play the computer. Get better.", and the "Train" button. Until U5 lands, the button opens the existing lessons page (review R-05).
- **Tests:**
  - Schema tests on temporary files only (never the real database): a fresh version-4 database is created, and a version-2 or version-3 file is moved to `.old` with a new database created beside it.
  - Summary route tests: mixed valid and invalid tokens, size limit, and no token in URLs or logs.
  - JS tests for list ordering and seat dropping.
  - A browser test of the list.
- **Notes:** the mode and computer columns are written here but used by U3 and U4. Until then every room behaves as today.

## U3 — u3-pass-along

- **Description:** pass-along play while waiting, and the join-request handshake.
- **Responsibilities:**
  - **Room modes (FR3.1, FR3.2, FR3.9):**
    - Rooms changes between `waiting` and `pass_along`, in both directions.
    - In `pass_along` the creator's seat may move both colours.
    - Pass-along survives a reload.
  - **JoinRequest (FR3.3–FR3.7):**
    - Created when a visitor opens the link of a pass-along room. Only one can be pending.
    - The visitor gets a request token, sent only in request bodies and stored hashed.
    - The request lapses after 10 minutes. The creator accepts or declines, and on accept seat B is created.
  - **Counting (FR3.8):** Games marks the current game counted on accept, under the same room lock. A game that ends in pass-along is not counted.
  - **LiveUpdates:** new events for mode changes and for join requests (created, answered, lapsed), and request-scoped sockets authenticated by the request token.
  - **Notifications:** a "join request" alert to the creator.
  - **Housekeeping:** marks lapsed requests.
  - **Rate limit (NFR4, ADR-006):** 5 join requests per minute per client address. A new `JUSTCHESS_TRUSTED_PROXIES` setting goes into `.env.example`, the README and the env-file test's allowed list.
  - **WebClient:**
    - "Play here while waiting" and "Wait for a friend instead".
    - The pass-along status and the practice note.
    - The Accept/Decline banner with a countdown that updates once a minute.
    - The joiner's waiting, declined, lapsed, busy and too-many screens.
    - The "Join request" pill in Your games.
- **Tests:**
  - Mode transitions and authorization: the creator may move both colours only in pass-along.
  - Join request lifecycle, including lapse and busy.
  - Only the creator can answer a request.
  - The rate limit, including spoofed `X-Forwarded-For` with no trusted proxy set.
  - The counted flag.
  - A browser test of the full accept flow between two pages.

## U4 — u4-play-the-computer

- **Description:** single player against Stockfish.
- **Responsibilities:**
  - **Engine (NFR1, ADR-001):**
    - One long-running Stockfish process through python-chess's asynchronous UCI interface, with Threads ≤ 2 and Hash ≤ 64 MB.
    - A FIFO queue that reports the queue position.
    - One restart after a crash, then reports unavailable.
    - Started and stopped with the app.
  - **ComputerOpponent (FR6.2, FR6.4):**
    - The level table: skill 0/5/10/15/20 with think times of 0.1, 0.3, 0.6, 1 and 2 s.
    - Computer replies, and hints at full strength for 0.5 s.
  - **Computer rooms (FR6.1, FR6.5, FR6.9, ADR-002, ADR-005):**
    - Created with a level, and with seat B as the computer's seat (no token).
    - The room score is the score against the computer.
    - The client reopens its saved room for a level.
  - **Games:**
    - Takeback of the last two plies (FR6.3), allowed only in computer rooms.
    - Threefold repetition and the 50-move rule end the game automatically in computer rooms (FR6.8).
  - **HttpApi:**
    - After a move, a reply that applies only if the game version is unchanged. No lock is held during the search, and an in-flight flag refuses takebacks meanwhile (ADR-009).
    - Resume asks for the reply when it is the computer's turn.
    - The hint route.
    - Resign.
    - Rematch with colours swapped, at the same level.
    - Unavailable answers (FR6.7).
  - **LiveUpdates (review R-01):** "computer queued" (with the queue position from Engine), "computer thinking" and "takeback" events, sent to the room's socket. The HTTP move response also returns the initial queued or thinking state, so the page shows it even before the socket event arrives.
  - **WebClient:**
    - The "Play the computer" panel, with colour and level remembered.
    - Thinking and queued states.
    - Takeback, the hint arrow and the resign dialog.
    - The result card with Rematch.
    - The score line ("this level").
    - The unavailable states.
    - The blunder warning applies to computer games too (FR6.6).
- **Tests:**
  - The engine queue against a fake UCI engine (ordering, restart, unavailable).
  - One real-engine test, skipped when Stockfish is missing.
  - Level mapping.
  - Takeback rules.
  - Automatic draws.
  - The reply race: a stale reply is discarded.
  - NFR1 timing on the Pi, with the real engine, at the Maximum level.
  - A browser test of a short game against the computer.

## U5 — u5-lessons-and-puzzles

- **Description:** more opening content, defence lessons, tactics puzzles and the trainer hub.
- **Responsibilities:**
  - **Lessons (FR7, FR8.4):**
    - A `kind` field on lessons (opening, trap or defence); old files default to opening.
    - New lesson files:
      - 8 openings: Ruy Lopez, Sicilian, French, Caro-Kann, Queen's Gambit, London, King's Indian and Scandinavian.
      - 4 traps: Legal's mate, Fried Liver, Fishing Pole and the Englund Gambit trap.
      - At least 4 defence lessons.
    - Every lesson has a note on each move, written in our own words.
  - **Puzzles (FR8.3, FR8.6, NFR6):**
    - A curated subset of the Lichess puzzle database (CC0): about 300 puzzles for each theme (forks, pins, skewers, discovered attacks, mate in 1, mate in 2), at most 5 MB in total, kept in `puzzles/`.
    - Loaded and validated at startup.
    - Routes for themes, getting a puzzle and checking a move.
    - The credit is shown on the Tactics tab and in `static/ASSETS.md`.
  - **Trainer hub (FR8.1, FR8.5):**
    - Tabs for Openings, Traps, Tactics and Defence. The Endgames tab is hidden until U6 registers it (review R-05).
    - Per-device progress counts.
    - The puzzle screen: wrong-move feedback, a hint, show solution, and next puzzle.
- **Tests:**
  - Every lesson and puzzle replays legally.
  - Theme counts and the size limit.
  - Move checking: correct, wrong and solved.
  - The lesson kind filter.
  - A browser test of the hub tabs and of solving one puzzle.
- **Notes:**
  - Curating the puzzles means downloading the public Lichess puzzle file once, during development, on the developer's machine. A small script in the repo filters and samples it. The script and its output are committed, but the big download is not.
  - The app downloads nothing at runtime.

## U6 — u6-endgame-trainer

- **Description:** endgame positions played against a full-strength computer.
- **Responsibilities:**
  - **Endgames (FR8.2):**
    - Hand-written position files: at least 3 for each of queen mate, rook mate, king and pawn, and opposition.
    - Goal judging: mate; promotion; or holding the draw for 30 moves, by threefold repetition or by the 50-move rule.
    - Defender moves come from Engine at skill 20 with 1 s to think.
    - No server session: the client sends the move list.
  - **HttpApi:** routes to list positions, get one, and play a move. The play route returns the defender's reply and a verdict.
  - **WebClient:**
    - The Endgames tab in the hub, with "Needs Stockfish" when the engine is unavailable.
    - The endgame screen: goal, move counter, hint, start again, and done or failed results.
- **Tests:**
  - Judging rules for each goal, using a fake engine.
  - Every position file loads and is legal.
  - Unavailable behaviour.
  - A browser test of one position.

## Sources
- `inception/domain-design/components.md`, `decisions.md`
- `inception/requirements-analysis/requirements.md`
- `inception/refined-mockups/` (screens and interaction spec)
- `units-generation-questions.md` [Q1], [Q2]
