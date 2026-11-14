# JustChess — Requirements

This document is the JustChess product specification. It replaces the standalone `REQUIREMENTS.md`, which is deleted once this work is done (intent statement, `ideation/intent-capture/intent-statement.md`; questions file Q1).

**Inputs**
- REQUIREMENTS.md: the previous spec, cited below as "spec §n".
- The approved intent statement (`ideation/intent-capture/intent-statement.md`).
- The code scan:
  - `aidlc/spaces/default/codekb/JustChess/business-overview.md`: the implemented-vs-specified table, cited as "scan".
  - `architecture.md` and `code-structure.md`: the component layout this spec builds on.
- Your observations from playing the app, cited as "obs".
- The answers in `requirements-analysis-questions.md`, cited as Q1–Q16.

**Legend**
- **Status:** Built = works today; Partial = partly built; New = not built.
- **Priority:** Must / Should / Could (Q9).
- **Phase:**
  - P1 = the next delivery phase: two-player polish and training together (Q2).
  - P2 = the following phase.
  - P3 = later.

## 1. Intent analysis

JustChess is a lightweight, mobile-friendly web app with two capabilities (spec §1):

- two people play chess through a shared room code or link, with no accounts;
- one person learns chess openings through guided walkthroughs and practice against scripted replies.

It requires no account, registration, subscription or payment. It has no matchmaking or computer opponent, and needs only minimal storage and simple deployment.

You are about to build the next phase and want a spec you can trust, held in the AI-DLC structure (intent statement). The review found three things:

- About a third of the old spec is already built, though none of it was marked as built (scan).
- Four places where the spec and the code disagree. They are resolved in Q7 and Q14.
- Usability problems you hit while playing: a game end that is easy to miss, a board that is cramped on phones, notifications that don't work, sharing that is hard, and squares that are hard to identify (obs).

P1 fixes the playing experience and makes practice mode real. Everything else stays, with an explicit priority.

## 2. Functional requirements

### FR1 Rooms and joining

| ID | Requirement | Pass/fail criterion | Status | Priority | Phase | Origin |
|---|---|---|---|---|---|---|
| FR1.1 | The system shall create a room with a public code of 6 characters drawn at random from A–Z and 0–9 | A new room returns a code matching `^[A-Z0-9]{6}$`, generated with a cryptographic random source; codes never repeat for open rooms | Built | Must | P1 | spec §3, scan |
| FR1.2 | The system shall let a second player join by typing the code | Entering a valid code seats the joiner as Black; an unknown code shows "Room not found" | Built | Must | P1 | spec §3, scan |
| FR1.3 | The system shall let a player join by opening an invite link that contains the room code | Opening the link on a fresh device either seats the visitor as Black or, if both seats are taken, says so. No code has to be typed | New | Must | P1 | spec §3, scan, obs, Q6 |
| FR1.4 | The system shall allow exactly two players per room: the creator plays White and the joiner Black | A third join attempt is refused with "Room already has two players" | Built | Must | P1 | spec §3, scan |
| FR1.5 | The system shall let a player return to their own seat after a refresh or reconnect without typing anything | After a page reload in the same browser tab, the player is back in their seat with the current position | Built | Must | P1 | spec §3, scan |
| FR1.6 | The system shall show each player whether the opponent is waiting, connected or disconnected | Closing the opponent's tab changes the shown status to "disconnected" within 10 seconds | Partial | Should | P1 | spec §3, scan |
| FR1.7 | The system shall let anyone with the room code watch a game read-only | A spectator sees live moves and cannot move pieces | Partial | Could | P3 | spec §3, scan |
| FR1.8 | The system shall expire and clean up stale rooms | A room with no activity for the retention period (NFR7) is deleted with its moves and subscriptions | New | Should | P2 | spec §3, §8 |

### FR2 Sharing

| ID | Requirement | Pass/fail criterion | Status | Priority | Phase | Origin |
|---|---|---|---|---|---|---|
| FR2.1 | The system shall offer a Share button that opens the device's native share sheet with the invite link (FR1.3) and a short invitation text | On a phone, tapping Share opens the system share sheet with WhatsApp, email and SMS among the targets, and the link is pre-filled | New | Must | P1 | obs, Q6 |
| FR2.2 | Where the native share sheet is unavailable, the system shall offer "Copy link" and confirm the copy | On a desktop browser without Web Share, tapping it puts the invite link on the clipboard and shows "Link copied" | Partial | Must | P1 | obs, Q6, scan |

### FR3 Playing a game

| ID | Requirement | Pass/fail criterion | Status | Priority | Phase | Origin |
|---|---|---|---|---|---|---|
| FR3.1 | The system shall highlight the legal destination squares of a tapped piece and move it when a highlighted square is tapped | Tapping a piece marks exactly its legal targets; tapping a target makes the move | Built | Must | P1 | spec §3, scan |
| FR3.2 | The system shall validate every move on the server with the full chess rules: side to move, check, castling, en passant, promotion, mate and stalemate | An illegal or out-of-turn move is rejected with an error and the position is unchanged | Built | Must | P1 | spec §3, scan |
| FR3.3 | The system shall ask for the promotion piece with an in-page picker (queen, rook, bishop, knight) instead of a browser prompt | Moving a pawn to the last rank shows four piece buttons; cancelling leaves the pawn unmoved | Partial | Should | P1 | spec §9, scan |
| FR3.4 | The system shall keep both boards in sync in real time and send the full current state when a player reconnects | After a reconnect the board, move list and status equal the server's state | Built | Must | P1 | spec §3, scan |
| FR3.5 | The system shall show the move history in algebraic notation with move numbers | After 1.e4 e5 2.Nf3 the history reads "1. e4 e5 2. Nf3" | Partial | Should | P1 | spec §3, scan |
| FR3.6 | The system shall show whose turn it is, and show check clearly | When a king is in check, the king's square is highlighted and the status says "Check" | Partial | Must | P1 | spec §3, scan |
| FR3.7 | Before sending a move that allows the opponent to checkmate on the next move, the system shall ask the player to confirm and explain why | Playing such a move opens a dialog naming the threat (e.g. "This allows Qh7#"). Cancel keeps the position; Confirm makes the move. Real chess rules are unchanged | New | Must | P1 | obs, Q4, Q13 |
| FR3.8 | Before sending a move that leaves one of the player's non-pawn pieces capturable for free, the system shall ask the player to confirm and explain why | Playing such a move opens a dialog naming the piece and square (e.g. "Your knight on f3 can be taken for free"). Cancel and Confirm behave as in FR3.7. "For free" is defined under Assumptions | New | Must | P1 | obs, Q13, Q15 |
| FR3.9 | The system shall offer one setting, on by default, that turns off both blunder warnings (FR3.7, FR3.8) | With the setting off, neither dialog appears; the choice is remembered on that device | New | Must | P1 | Q15 |
| FR3.10 | The system shall reject duplicate or out-of-order move submissions using a game version number | Sending the same move twice, or a move based on an old version, is rejected and the position changes once only | Partial | Should | P1 | spec §3, §7, scan |
| FR3.11 | The system shall support drag-and-drop moves on desktop | Dragging a piece onto a legal square makes the move | New | Could | P3 | spec §3, scan |
| FR3.12 | The system shall optionally show captured material | A captured-pieces row per side can be shown; it is never confused with the win count | New | Could | P3 | spec §3, scan |

### FR4 Game end and match

| ID | Requirement | Pass/fail criterion | Status | Priority | Phase | Origin |
|---|---|---|---|---|---|---|
| FR4.1 | When a game ends, the system shall show a clear end-of-game message naming the winner (or draw) and the reason, and visibly lock the board | On checkmate, both players see e.g. "Checkmate — White wins" over the board, and no piece can be selected | Partial | Must | P1 | obs, Q3, scan |
| FR4.2 | The system shall end a game automatically on checkmate, stalemate, insufficient material, fivefold repetition and the 75-move rule | Each condition ends the game with the matching reason, with no player action | Partial | Must | P1 | spec §3, Q14, scan |
| FR4.3 | The system shall let a player claim a draw when threefold repetition or the 50-move rule applies, and only then | A "Claim draw" button appears only while a claim is valid; using it ends the game as a draw with that reason | New | Must | P1 | spec §3, Q14, scan |
| FR4.4 | After a game ends, the system shall offer "Play again", which starts a new game in the same room with colours swapped | When both players have pressed Play again, a new game starts with the previous Black now playing White | New | Must | P1 | Q3 |
| FR4.5 | The system shall keep a room scoreboard of wins for each player and draws across all games in the room | After two games (one win each) the scoreboard shows 1 – 1 with 0 draws | Partial | Must | P1 | spec §3, Q3, scan |
| FR4.6 | The system shall let a player resign | Resign asks for confirmation and then ends the game as a win for the opponent | New | Should | P2 | spec §3 |
| FR4.7 | The system shall let a player offer a draw, which the opponent can accept or decline | An accepted offer ends the game as an agreed draw | New | Should | P2 | spec §3 |
| FR4.8 | The system shall handle abandoned games | A game whose player has been disconnected beyond a set time can be ended by the other player | New | Could | P2 | spec §3 |

### FR5 Board and game screen

| ID | Requirement | Pass/fail criterion | Status | Priority | Phase | Origin |
|---|---|---|---|---|---|---|
| FR5.1 | The system shall colour the board correctly | Square a1 is dark and h1 is light | Partial | Must | P1 | scan |
| FR5.2 | The system shall show each player's own pieces at the bottom of the board | The player with Black sees rank 8 at the bottom and rank 1 at the top | New | Must | P1 | spec §3, scan |
| FR5.3 | The system shall label files a–h and ranks 1–8. By default the labels sit inside the edge squares; a setting moves them outside the board | The default view shows the letters in the bottom row and the numbers in the left column, matching the board orientation. Switching the setting moves them outside, and the choice is remembered on that device | New | Must | P1 | obs, Q11 |
| FR5.4 | During a game, the system shall show a slim top bar (logo, room code, Share) with the board directly below it, as large as the screen allows. Status, move list and score go below the board | On a 390 × 844 phone viewport, the board's top edge is at most 72 px from the top and the board is at least 374 px wide (viewport minus 16 px) | New | Must | P1 | obs, Q10 |
| FR5.5 | During a game, the system shall hide the lobby and show "Learn openings" collapsed to a single line reading "Learn openings — your game keeps running", which opens on tap | With a game in progress, the lobby is not visible, the lessons line is visible below the game, and tapping it opens the lessons | New | Must | P1 | obs, Q10, Q12, Q16 |
| FR5.6 | While a lesson is open during a game, the system shall keep the game live: moves still arrive and turn alerts still fire | An opponent move made while a lesson is open shows on the game board and triggers the turn alert (FR6) | Partial | Must | P1 | obs, Q12 |

### FR6 Notifications

| ID | Requirement | Pass/fail criterion | Status | Priority | Phase | Origin |
|---|---|---|---|---|---|---|
| FR6.1 | The system shall show a waiting message after a room is created and alert the creator when the opponent joins | The creator sees "Waiting for your opponent" and gets an alert when Black joins | Partial | Must | P1 | spec §4, scan |
| FR6.2 | The system shall alert a player when the opponent has moved and it is their turn, and when the game ends | Each opponent move produces a turn alert for the player to move | Partial | Must | P1 | spec §4, obs, scan |
| FR6.3 | The system shall ask for notification permission only after an explicit player action, and fall back to an in-page banner when permission is refused or unsupported | With permission denied, a "Your turn" banner still appears in the page | Partial | Must | P1 | spec §4, scan |
| FR6.4 | The system shall show system notifications through a service worker while the page is open in the background | On Android Chrome with the tab in the background, a turn alert appears as a system notification | New | Must | P1 | obs, Q5 |
| FR6.5 | The system shall deliver Web Push notifications when the page is closed, where the browser supports it | With the tab closed on Android Chrome (or an iPhone home-screen app, iOS 16.4+), an opponent move produces a notification | New | Must | P1 | spec §4, Q5 |
| FR6.6 | The system shall send each player at most one alert per opponent move, across the in-page, local and push channels | No path (open page, background tab, closed page, reconnect) produces two alerts for the same move | New | Must | P1 | Q5 |
| FR6.7 | The system shall store only the minimal push-subscription data, let a player turn notifications off, and remove invalid subscriptions | Turning notifications off stops all alerts for that device; a subscription the push service reports as gone is deleted | New | Must | P1 | spec §4, §7 |
| FR6.8 | The system shall not send repeated alerts and shall not report an alert as delivered until the platform confirms it | Only join, opponent move and game end produce alerts | Partial | Must | P1 | spec §4, scan |

### FR7 Training

| ID | Requirement | Pass/fail criterion | Status | Priority | Phase | Origin |
|---|---|---|---|---|---|---|
| FR7.1 | The system shall offer a guided walkthrough with Back, Next and Restart and an explanation for each move | Next plays the next move and shows its note; Back undoes it; Restart returns to the start | Built | Must | P1 | spec §5, scan |
| FR7.2 | The walkthrough shall animate each move and highlight important squares | Each step animates the moving piece and highlights its from- and to-squares | New | Should | P1 | spec §5, §9, scan |
| FR7.3 | In practice mode, the learner shall play only their side while the trainer plays the opponent's scripted replies | After the learner's correct move, the trainer's reply is played automatically | Partial | Must | P1 | spec §5, Q8, scan |
| FR7.4 | In practice mode, the system shall give hints, allow retries and explain the expected move after a mistake | A wrong move shows "Try again" with a hint; after a set number of misses the expected move and its note are shown | Partial | Must | P1 | spec §5, scan |
| FR7.5 | In practice mode, the system shall tell an illegal move apart from a legal move that is outside the taught line, and offer free play or a return to the line | An illegal move is refused as illegal; a legal off-line move shows "Legal, but not this line" with the two choices | New | Should | P1 | spec §5, scan |
| FR7.6 | The system shall load lessons from YAML or JSON data files, so content changes need no code changes | Adding a lesson file makes a new lesson appear with no change to `app.py` | New | Must | P1 | spec §2, §6, Q14, scan |
| FR7.7 | Each lesson shall store its name, aliases, ECO code (where verified), start position, moves in SAN and UCI, notes, alternative lines and learning objectives | A lesson file missing a required field is reported at startup | Partial | Should | P1 | spec §5, scan |
| FR7.8 | The system shall model openings as a branching tree with several possible opponent replies, chosen at random from the scripted ones | Repeating practice of one lesson produces different scripted replies where the tree branches | New | Should | P2 | spec §5, scan |
| FR7.9 | The system shall explain when to abandon or switch the intended plan after the opponent deviates | A branch with a known deviation shows a "when to switch plans" note | New | Should | P2 | spec §5, §6 |
| FR7.10 | The system shall recognise move-order transpositions by board position, not just by move history | Reaching a known position by a different move order continues the matching lesson | New | Could | P2 | spec §5, scan |
| FR7.11 | The system shall explain traps and common mistakes for both sides, and offer quizzes and variation recognition | A lesson with traps shows them; a quiz asks the learner to name or play a variation | New | Could | P2 | spec §5, §6 |
| FR7.12 | The system shall save training progress on the device | Completed lessons stay marked after a reload | New | Could | P3 | spec §5 |

### FR8 Opening catalog

| ID | Requirement | Pass/fail criterion | Status | Priority | Phase | Origin |
|---|---|---|---|---|---|---|
| FR8.1 | The catalog shall contain the Italian Game and the French Defense Exchange — Monte Carlo Variation (`1.e4 e6 2.d4 d5 3.exd5 exd5 4.c4`) | Both lessons load and play their full lines | Built | Must | P1 | spec §6, scan |
| FR8.2 | The catalog shall add the foundational openings: Ruy Lopez, Sicilian Defense, French Defense, Queen's Gambit, London System, King's Indian Defense and Vienna Game | Each is available as a lesson | New | Should | P2 | spec §6 |
| FR8.3 | The catalog shall add the named lines: Albin Countergambit, Traxler Counterattack, Fried Liver Attack and Vienna Gambit | Each is available as a lesson | New | Should | P2 | spec §6 |
| FR8.4 | The catalog shall add the unusual openings: Danish Gambit, Bird's Opening, Grob's Attack and Orangutan Opening | Each is available as a lesson | New | Could | P3 | spec §6 |
| FR8.5 | The Monaco Variation shall be published only after its exact opening, aliases and move order are verified | No Monaco lesson exists until a verified source is recorded in its lesson file | New | Could | P3 | spec §6 |
| FR8.6 | Every published lesson shall include its ideal sequence, purpose, typical responses, branches, common mistakes, traps and a "when to switch plans" note | A lesson that is missing any of these is flagged as incomplete | New | Should | P2 | spec §6 |

### FR9 Chess engine availability

| ID | Requirement | Pass/fail criterion | Status | Priority | Phase | Origin |
|---|---|---|---|---|---|---|
| FR9.1 | The app installs a pinned, checksum-verified Stockfish at boot when none is present, and starts normally when it cannot | With no `STOCKFISH_PATH`, no `stockfish` on PATH and no earlier install, boot downloads the pinned `sf_19` build, installs it only if its SHA-256 matches, and `GET /api/engine` reports it as available; with `STOCKFISH_AUTO_INSTALL=0`, an unsupported platform or a failed download or checksum, the app still starts and `GET /api/engine` reports it as not available | Built | Must | P1 | build-scope answer at Code Generation ("1, but also include the stockfish install upon boot") |

## 3. Non-functional requirements

| ID | Requirement | Pass/fail criterion | Priority | Phase | Origin |
|---|---|---|---|---|---|
| NFR1 | Seat authority. The server shall be the only source of truth, check seat ownership on every move, and never trust client-sent moves, identity, state or scores. A room code alone shall never control a seat | A move sent with only the room code, or with the other seat's role, is rejected | Must | P1 | spec §2, §8, scan |
| NFR2 | Secrets. Seat tokens shall have at least 128 bits of randomness, be stored only as hashes, and never appear in URLs (including invite links) or logs | The database holds no plaintext token; invite links contain only the room code | Must | P1 | spec §7, §8, Q14, scan |
| NFR3 | Transport. Production shall run only over HTTPS and WSS, which Web Push also requires | A plain-HTTP request in production is redirected to HTTPS | Must | P1 | spec §8, Q5 |
| NFR4 | Integrity. Room creation, seat assignment, moves and result updates shall be atomic and race-safe | Concurrent joins seat only one Black; concurrent moves apply only one | Must | P1 | spec §3, §8, scan |
| NFR5 | Responsiveness. A move shall reach the opponent's board quickly | On a normal connection, 95% of moves appear on the opponent's board within 1 second | Should | P1 | spec §3 |
| NFR6 | Accessibility. Touch targets shall be at least 44 × 44 px, the game shall be playable by keyboard, text contrast shall meet WCAG 2.1 AA, and every square shall have a screen-reader label with its coordinate and piece | An automated accessibility check reports no AA contrast failures; every square is reachable and movable by keyboard | Should | P1 | spec §3, scan |
| NFR7 | Retention and operations. Define how long rooms and push subscriptions are kept, a backup routine, a health check and error logging | A health endpoint answers OK; data older than the retention period is removed automatically | Should | P2 | spec §8 |
| NFR8 | Abuse limits. Room creation, joining and moves shall be rate-limited, request sizes bounded, and the WebSocket Origin validated | Requests beyond the limit get HTTP 429; a WebSocket from a foreign origin is refused | Should | P2 | spec §8, scan |
| NFR9 | Tests. Automated tests shall cover chess rules and move validation, seat identity checks, race conditions, game-end and draw logic, blunder detection, notification de-duplication and training transitions | The test suite runs with `uv run` and passes; each area listed has at least one test | Must | P1 | spec §8, §10, scan |
| NFR10 | Deployment. The app shall run as a single-process FastAPI service in Docker, with a persistent volume for SQLite | `docker run` with a mounted volume serves the app, and data survives a container restart | Should | P2 | spec §2, scan |

## 4. Data model (target)

This follows the spec, as agreed in Q14, because rematch (FR4.4) and Web Push (FR6.5) need it (spec §7, scan):

- **games**: room code, FEN, status, side to move, end reason, version, timestamps.
- **game_players**: room, hashed token, side, reconnect metadata.
- **moves**: room, game number, ply number, UCI, SAN, timestamp.
- **results**: room, game number, winner or draw, reason.
- **push_subscriptions**: player, endpoint, keys, created and last-used dates.
- **Lessons**: version-controlled YAML or JSON files, not stored in the database (FR7.6).

## 5. Constraints

- Python 3.11+, FastAPI, Jinja2 and python-chess for all authoritative chess rules (spec §2, scan).
- The frontend is server-rendered HTML with a small plain-JavaScript board controller and responsive CSS. HTMX is not used and its script tag is removed (Q14, scan).
- Persistence is SQLite. Dependencies are managed with `uv` and `pyproject.toml`, and `uv.lock` is committed (spec §2, scan).
- A single process. If the app ever runs several processes, WebSocket broadcast moves to Redis pub/sub or similar (spec §2).
- No accounts, registration, subscriptions, payments, matchmaking or computer opponent (spec §1).
- A chess engine (Stockfish) may be installed so it is available (FR9.1), but the app does not use it yet. Using it for analysis, such as blunder warnings or practice judgement, is a later decision. Until then the app never claims to judge arbitrary moves or find the objectively best one, and blunder warnings (FR3.7, FR3.8) are limited to the two checks defined here (spec §5, Q13, build-scope answer at Code Generation).

## 6. Assumptions

- "Free" capture (FR3.8): after the move, the opponent can capture one of the mover's knights, bishops, rooks or queen on a square that none of the mover's pieces defends, or with a piece of lower value. Rationale: this is detectable without an engine, which matches Q13.
- Rematch (FR4.4) starts only when both players have pressed "Play again", so neither player is forced into a new game. Rationale: Q3 asked for a rematch button but did not say who decides.
- Web Push on iPhone works only when JustChess is added to the home screen (iOS 16.4+). Rationale: this is a platform limit, not a product choice.
- The settings in FR3.9 and FR5.3 are stored per device, in the browser. Rationale: there are no accounts (constraint).
- The phase for each P2 and P3 item is my proposal from Q9 ("keep all, prioritised"); you confirm or adjust it at approval.

## 7. Out of scope

- Accounts, payments, matchmaking and computer opponents (spec §1).
- Engine evaluation (for example using Stockfish to judge moves). It remains possible future work, not a requirement; only making the engine available is in scope (FR9.1) (spec §5).
- Separate documentation folders. Requirements live in AI-DLC records (Q1, intent statement).

## 8. Definition of done for P1

Two players can do all of the following, on a phone or a desktop:
- start a game from a shared link;
- see a correctly coloured and oriented board with labels, as large as the screen allows;
- get warned before blunders;
- receive exactly one alert per opponent move, even with the page closed;
- see a clear result;
- play again in the same room with a running score.

A learner can practise both catalog lessons with the trainer playing the opponent's replies, loaded from data files.

Automated tests cover NFR9. Seat tokens are hashed, production runs over HTTPS, and REQUIREMENTS.md has been removed (spec §10, Q1–Q16).

## 9. Open questions

None blocking. The P2/P3 phase split (assumption above) is for you to confirm at approval.
