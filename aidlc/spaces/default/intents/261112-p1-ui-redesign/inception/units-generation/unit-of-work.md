# Units of Work — JustChess P1

These units group the components in `inception/domain-design/components.md`, following `inception/domain-design/decisions.md` (ADR-001 to ADR-006). They cover every P1 requirement in `inception/requirements-analysis/requirements.md`. You approved the 6-unit split (Q1) and the decomposition plan.

**Deployment model:** every unit ships into one FastAPI app on the Raspberry Pi. It is one process, serving the API, the WebSocket, the ES modules and the service worker. No unit deploys on its own.

| Unit ID | Directory | Kind | Size | Components |
|---|---|---|---|---|
| U1 | u1-core-game | service | L | Rooms, Games, LiveUpdates, HttpApi (core routes), Housekeeping, Engine (startup hook kept) |
| U2 | u2-design-system-board | ui | M | WebClient: design tokens, fonts, pieces, themes, board module, settings module |
| U3 | u3-game-screen | ui | L | WebClient: lobby and game modules, end-of-game overlay, designed states |
| U4 | u4-blunder-warnings | service | M | Analysis, the HttpApi blunder route, the WebClient blunder dialog |
| U5 | u5-notifications | service | L | Notifications, HttpApi push routes, the WebClient notifications module and service worker |
| U6 | u6-training | ui | M | Lessons, the HttpApi lesson routes, the WebClient training module |

## U1 — u1-core-game

- **Description**: Restructures `app.py` into a `justchess/` package and builds the P1 game core.
- **Responsibilities**:
  - Module layout: `rooms`, `games`, `live`, `api`, `housekeeping` and `db`; `stockfish_install.py` is kept and wired in.
  - Fresh database schema with a version check; the old file is moved to `.old` (ADR-006).
  - Rooms:
    - codes and join by code or link;
    - hashed seat tokens (128-bit, SHA-256, constant-time compare);
    - continue tokens and seat transfer;
    - per-seat score and rematch requests;
    - last-seen times and the "abandoned" (24 h) answer.
  - Games:
    - one game per room at a time, with colours swapping on rematch;
    - versioned moves;
    - automatic ends with reasons (checkmate, stalemate, insufficient material, fivefold repetition, 75-move rule);
    - draw claims (threefold repetition, 50-move rule);
    - claiming a win after abandonment;
    - a numbered move list in the snapshot.
  - LiveUpdates: Origin check, seat token sent in the first message, snapshot on connect, broadcast, a heartbeat that detects a disconnect within 10 s, and visibility reports.
  - HttpApi: the core routes (create, join, continue link, move, claim draw, claim win, rematch, state); Origin checks and size limits on state-changing calls; orchestration in one database transaction per use case (ADR-003).
  - Housekeeping: hourly cleanup of rooms idle for 30 days, including their games and moves. It calls Games' delete-by-room; this answers review finding R-01 from Domain Design.
  - Removal of the HTMX script tag.
  - Backend tests: rules, draws, versions, seat security, rematch and score, abandonment, cleanup.
- **Implementation notes**:
  - The existing frontend (`static/app.js`) keeps working against the new API until U3 replaces it. U1 keeps the snapshot field names the old client reads, and adds the new fields alongside them.
  - Push and Analysis hooks are not built here; U4 and U5 add their routes.
  - Presence is passed into Notifications and abandonment into Games by HttpApi. This answers review findings R-03 and R-04 from Domain Design.

## U2 — u2-design-system-board

- **Description**: The visual system and the board component from `inception/refined-mockups/design-system-mapping.md`.
- **Responsibilities**:
  - CSS design tokens: light and dark themes, the brass accent with a darker fill in light mode, and 3 board themes.
  - Self-hosted Libre Caslon and Atkinson Hyperlegible fonts, and the cburnett SVG pieces with their licence credit.
  - Board ES module: correct colours (a1 dark), orientation per seat, labels on the squares or in the frame, highlights for last move, selection, legal targets and check, keyboard play, motion (200 ms slide, capture, check pulse), reduced motion, and the promotion picker.
  - Settings module: theme, board theme, labels, blunder warnings and the notifications toggle, stored per device. It shows a notice when storage is blocked.
  - Frontend test harness for the modules (Node test runner on pure functions such as board geometry and settings), plus a static demo page for visual checks.
- **Implementation notes**: no server dependency. The board takes position, legal moves and orientation as inputs, so it can be tested on its own.

## U3 — u3-game-screen

- **Description**: The new page shell, lobby and game screen, built on U1's API and U2's board.
- **Responsibilities**:
  - The new `index.html`, with a slim top bar and the brass Share button (share sheet, or copy-link fallback).
  - Lobby: start a game, join with a code, and join directly from an invite link.
  - Game screen:
    - status line (baize green on your move, check, away, reconnecting);
    - scoresheet;
    - room score;
    - draw claim and win claim buttons, shown only when valid;
    - the continue-on-another-device link and its warning.
  - Game over: the end-of-game overlay with the reason; the win sequence (king tips, board dims, result inked into the scoresheet, overlay, glow); "Play again" and the waiting and lapsed rematch states.
  - Designed states: waiting for opponent, reconnecting, room not found, seats taken, storage blocked, "opened on another device".
  - The collapsed "Learn openings — your game keeps running" line (the drawer only; its content comes from U6).
  - Seat saved in long-lived browser storage.
  - Layout rules: board at least 374 px on 390 px phones, 560–640 px on desktop.
- **Implementation notes**: replaces `static/app.js`. The old client is deleted at the end of this unit.

## U4 — u4-blunder-warnings

- **Description**: Server-side blunder detection and the confirm dialog.
- **Responsibilities**:
  - Analysis: mate-in-one detection; non-pawn pieces capturable without loss; the "creates the problem" and "no alternative" rules.
  - `POST /api/games/{code}/check-move`: checks the seat, then analyses the move against the current game version.
  - Blunder dialog in the game screen, with the safe default focused and the "Play … anyway" button.
  - Honours the blunder-warnings setting.
  - Tests with fixed positions for each rule and corner case.

## U5 — u5-notifications

- **Description**: Notifications that actually arrive, with one alert per event.
- **Responsibilities**:
  - Notifications component: subscriptions per seat, alert records with event keys, Web Push with VAPID keys from the environment or a key file, and cleanup on 404/410.
  - Routes: subscribe, unsubscribe, and the VAPID public key.
  - HttpApi calls on join, opponent move and game end, passing presence in.
  - Service worker: one tag per event, skipped when the room's page is visible, opens the game on tap.
  - Notifications module: permission only after a user action, the in-page "Your turn" banner as fallback, visibility reports, and the toggle.
  - The `pywebpush` dependency.
  - Push verified on `localhost`.
  - Tests for de-duplication, presence rules and subscription cleanup.

## U6 — u6-training

- **Description**: Lessons from files, with a trainer that replies.
- **Responsibilities**:
  - A `lessons/` folder with Italian Game and French Exchange Monte Carlo as YAML files (default side White).
  - Lessons component: loads and validates the files, skipping and reporting bad ones; expands each lesson into steps with the position before and its legal moves.
  - Lesson routes.
  - Training module:
    - walkthrough with animation and square highlights;
    - practice where the trainer replies, with a side switch;
    - hint, then the expected move with a dashed arrow after 3 misses;
    - illegal moves told apart from "legal, but not this line", with free play or return to the line.
  - Training opens inside the lessons drawer from U3 (during a game) and from the lobby's "Learn an opening".
  - Tests for loading, validation and step expansion.
- **Implementation notes**: it uses U2's board. It needs U1's package structure for the routes. Mounting the drawer is a small integration point with U3: if U3 is not there yet, training is reachable from its own route.
