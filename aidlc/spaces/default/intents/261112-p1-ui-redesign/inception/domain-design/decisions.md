# Architecture Decisions — JustChess P1

These decisions trace to `inception/requirements-analysis/requirements.md` and `components.md`. The current structure comes from the code map: `aidlc/spaces/default/codekb/JustChess/architecture.md` and `component-inventory.md`.

## ADR-001: Separate Rooms (seats, match score) from Games (one game's rules)

- **Status**: Accepted (your answer to Q1: "Room + Game").
- **Context**: Today one `games` row is the room, the seats and the single game at once. P1 adds rematches with colour swap (FR4.4), a score that follows the player (FR4.5), hashed seat tokens and continue links (FR1.5, FR1.7, NFR2), and claims after abandonment (FR11.2). Seats and score outlive any single game.
- **Decision**: **Rooms** owns Room and Seat: the code, the two seats, the token hashes, the match score per seat, and rematch requests. **Games** owns Game and Move: one game's position, rules, version and result. A rematch creates a new Game in the same Room, with colours swapped.
- **Consequences**:
  - Positive: the score is keyed by seat, so colour swaps can't confuse it. Token security lives in one place. The chess rules can be tested without rooms.
  - Negative: two tables to keep consistent when a game ends (the result goes to the Game; the score goes to the Room). This is handled in one transaction by HttpApi (ADR-003).
  - Security: seat authorization happens only in Rooms, so every path that changes a game goes through it.
- **Alternatives Rejected**:
  - One Game component owning everything (closest to today): seats and score would be tangled with per-game state, and colour swaps would need special-casing.
  - Score computed from stored results instead of a running count: always correct, but a query on every snapshot. A running count, updated in the same transaction as the result, is enough at this size.

## ADR-002: A separate Analysis component for blunder detection

- **Status**: Accepted (your answer to Q2).
- **Context**: FR3.7, FR3.8 and FR3.11 need server-side checks for mate-in-one and hanging pieces, with rules about "creates the problem" and "no alternative". Stockfish is installed for future analysis (FR9.1).
- **Decision**: **Analysis** is a pure component: position plus candidate move in, finding or nothing out. HttpApi calls it with the same game version the move will use.
- **Consequences**:
  - Positive: it can be tested alone with fixed positions. Later engine features plug in here without touching the rules.
  - Negative: one extra request before a move while warnings are on (a single round trip on the local network).
  - Security: it reads only the position passed in and trusts no client claim.
- **Alternatives Rejected**: Putting the checks inside Games would mix advice with rules, and later engine work would land in the rules code.

## ADR-003: HttpApi orchestrates every cross-component flow (no component cycles)

- **Status**: Accepted.
- **Context**: A finished game must update the Room's score. A move must be broadcast and may trigger a push. If Games called Rooms and Rooms called Games, the graph would have a cycle.
- **Decision**: Rooms, Games, Analysis, Notifications, Lessons and Engine do not call each other. HttpApi runs each use case in order, for example "move": authorize the seat, apply the move, record the result, broadcast, notify. Only LiveUpdates (Rooms, Games) and Housekeeping (Rooms, Notifications) have their own dependencies, and those point one way.
- **Consequences**:
  - Positive: an acyclic graph; each component can be unit-tested without the others; use cases are readable in one place.
  - Negative: HttpApi gets larger, so it must stay a thin orchestration layer with no business rules.
  - Security: origin checks, input validation and size limits sit in one place in front of every component (NFR8a).
- **Alternatives Rejected**: Domain events between components (Games publishes "GameFinished", Rooms subscribes) is loosely coupled, but it is more machinery than a single-process app of this size needs.

## ADR-004: The frontend as native ES modules, with no build step

- **Status**: Accepted (your answer to Q3).
- **Context**: The redesign adds a board component, motion, dialogs, settings, training, a service worker and push. Today's 23 lines with global state cannot hold that. The constraints require plain JavaScript and no HTMX.
- **Decision**: The WebClient is split into native ES modules (board, game, lobby, training, notifications, settings), plus a service worker. The browser loads them directly and nothing is bundled.
- **Consequences**:
  - Positive: no toolchain, files are served as written, it is easy to debug on the Pi, and it matches the constraint.
  - Negative: several small requests on first load (fine over HTTP/2 or the local network) and no minification.
  - Security: no third-party script CDNs. Fonts, pieces and modules are self-hosted (requirements constraint).
- **Alternatives Rejected**: A small esbuild bundle (smaller payload, but it adds a build step and a dependency for little gain at this size). A UI framework (against the constraint).

## ADR-005: One alert per event, enforced on the server and in the service worker

- **Status**: Accepted.
- **Context**: FR6.6 requires at most one alert per opponent move, across in-page alerts, local notifications and Web Push, including after reconnects.
- **Decision**:
  - **Server:** Notifications records an alert key (seat plus event, for example `move:24`) before sending, and never sends twice for the same key. It pushes only when LiveUpdates reports the seat as disconnected or not visible.
  - **Client:** the service worker tags each notification with the same key, so the browser replaces rather than stacks, and skips showing it when a visible page for that room exists. That page shows its in-page banner instead.
- **Consequences**:
  - Positive: duplicates are prevented at both layers, and reconnects can't re-alert.
  - Negative: a small `AlertRecord` table to clean up; Housekeeping covers it.
  - Security: VAPID private keys come only from the environment or a key file outside the repo (NFR3a). Subscriptions are deleted on 404 or 410 and when the user turns notifications off.
- **Alternatives Rejected**: Client-only de-duplication (can't stop a push to a closed page duplicating an alert a reconnect also shows). Push for every event without presence (it would double-alert open pages).

## ADR-006: Fresh schema on upgrade, with no migration

- **Status**: Accepted (from requirements FR11.1, your Q5 answer "Start fresh").
- **Context**: The new tables (rooms, seats, games, moves, push_subscriptions, alert_records) replace the single `games` table with plaintext tokens.
- **Decision**: At startup, a database without the new schema version is moved aside to `justchess.sqlite3.old` and a fresh one is created. There is no data migration.
- **Consequences**:
  - Positive: no plaintext tokens carried forward, and simple code.
  - Negative: open games at upgrade time are lost (accepted: there are no real users).
  - Security: plaintext tokens in the old file stay on disk in the `.old` file until you delete it; the startup log says so.
- **Alternatives Rejected**: In-place migration with token hashing (not needed); deleting the old file outright (keeping it is safer and costs nothing).
