# Business Overview: JustChess

## Purpose

JustChess is a self-hosted web app (page title "JustChess — Play a friend. Learn an opening."; lobby line "No accounts. No subscriptions. Just chess.") with two capabilities:

1. **Anonymous two-player chess.** One person starts a room, sends the invite link `/r/{CODE}` (or the six-character code), and a second person takes the other seat. Seats are proven by private tokens kept in the browser. A third visitor watches read-only.
2. **Opening training.** A trainer at `/learn` and inside the game's "Learn openings" drawer walks through curated opening lines move by move, then lets the learner practise one side against scripted replies.

Around these sit blunder warnings before a move is sent, notifications (in-page banner, local notification, Web Push), rematches with colours swapped, a room score per player, "continue on another device" links, per-device display settings, and a background Stockfish install that no feature uses yet.

By design there are no accounts, payments, matchmaking or computer opponents today (README). The README calls the build an "unverified MVP". The product specification lives in `aidlc/spaces/default/intents/261111-requirements-review/inception/requirements-analysis/requirements.md` (stable IDs FR, NFR); this store no longer keeps a requirement-by-requirement conformance table, because the code was rebuilt by the units U1 to U6 named in the module headers.

## Business Transactions

| Transaction | Actor | Outcome | Where |
|---|---|---|---|
| Start a game | Player A | Room with a code, seat A (White in game 1) and game 1 `waiting`; seat token returned once and stored in the browser | `POST /api/rooms` |
| Join by link or code | Player B | Seat B created, game 1 `playing`, seat A alerted "Your opponent has joined" | `POST /api/rooms/{code}/join` |
| Rejoin | Either player | Same seat restored from the stored token; a stale token is replaced and the screen says so | same route, with the token |
| Watch | Anyone with the code | Read-only snapshots over the socket; no legal moves | `GET /api/rooms/{code}`, `/ws/{code}` |
| Make a move | Seat to move | Server checks seat, status, version, turn and legality; ends the game on mate, stalemate, insufficient material, fivefold or 75 moves; opponent alerted | `POST /api/rooms/{code}/moves` |
| Blunder check | Seat to move | Before posting, the client asks whether the move allows mate in one or leaves a piece hanging; a dialog asks to confirm | `POST /api/rooms/{code}/check-move` |
| Claim a draw | Seat to move | Threefold repetition or 50-move rule, only when claimable | `POST .../claim-draw` |
| Claim a win | Seated player | When the opponent has been away for more than 24 hours | `POST .../claim-win` |
| Rematch | Both players | First request is recorded; the second starts the next game with colours swapped | `POST .../rematch` |
| Continue on another device | Seated player | One-use link valid 10 minutes; the old device becomes a watcher | `POST .../continue-link`, `POST .../continue` |
| Turn on notifications | Seated player | Permission prompt; service worker; Web Push subscription when the server has VAPID keys | `GET /api/push/key`, `POST .../push/subscribe` |
| Learn an opening | Learner | List, walkthrough, practice with hints, arrow after 3 misses, free play off the line | `GET /api/lessons`, `GET /api/lessons/{id}`, `POST /api/position/move` |
| Check engine | Any client | Whether Stockfish is available and where it came from | `GET /api/engine` |
| Idle cleanup | System | Rooms idle for 30 days are deleted at startup and hourly, with their games, moves, subscriptions and alert records | `justchess/housekeeping.py` |

How these flow across components: `architecture.md`, Interaction Diagrams.

## User Experience Today

Visual and behavioural facts owned here; the code behind them is in `component-inventory.md`.

- **Shell.** One page shell (`templates/index.html`) with a slim top bar (56 px): the logo (links home) and, inside a room, the room code and a primary **Share** button. Everything else is drawn by `static/js/app.js` into `<main id="app">` with client-side routing: `/` lobby, `/r/{CODE}` room, `/learn` and `/learn/{id}` trainer.
- **Design system "Club Set".** Light and dark page themes following the device unless set; three board themes (Walnut and maple, Tournament green, Rosewood); coordinates on the squares or in the frame; self-hosted fonts (Libre Caslon Display and Text, Atkinson Hyperlegible) and cburnett SVG pieces. Contrast pairs are checked by a test. Reduced motion sets every duration to 0.
- **Lobby.** Hero title "Play a friend. Learn an opening.", one primary action **Start a game**, a secondary **Learn an opening**, a "Have a room code?" field (uppercased, 6 letters or digits), and a non-interactive board in the starting position. There is no list of the games this browser is seated in.
- **Game screen.** Board column (board, then the players line "You play White · Opponent plays Black"); side panel with the status line (tone changes on your move, a dot for check or an away opponent), a 4-second flash line for refusals, the notification banner, claim buttons only while valid, notices, **Game settings** sheet (theme, board, coordinates, blunder warnings, notifications, continue-link row), the scoresheet (collapses to the last 6 rows on phones), the room score "You 1 · Opponent 0 · Draws 0", and the **Learn openings** drawer ("your game keeps running").
- **Layout.** Phone (< 768 px): the board spans the viewport width minus 8 px gutters, the side panel stacks below it. Tablet: board column at most 640 px, centred. Desktop (>= 1024 px): board column 560-640 px on the left, panel on the right. Board size follows width only, so on a short viewport the board's lower part, and on phones the status line, can sit below the fold.
- **Moves and motion.** Tap a piece to see its targets, tap a target; a promotion opens an in-board picker; moves slide (200 ms). A piece captured by the opponent fades and drops 6 px (150 ms); a capture by the viewer's own move is shown at once without that fade. Check pulses the king's square. At the end the losing king tips, the board dims, the result is inked into the scoresheet, an overlay names the reason, the winner and the decisive move, and the winner's pieces glow.
- **Sharing.** **Share** uses the system share sheet where the browser has one, else copies the invite link and shows "Link copied" for 1.6 s, else shows a read-only "Copy this link" field under the top bar. The end overlay has **Share result** (text such as "I won by checkmate on JustChess" with the link). There is no share dialog, no email link and no messenger links.
- **Blunder warnings.** On by default ("Warn me before blunders"). A modal alert dialog titled for the problem offers "Choose another move" (focused) or "Play … anyway". If the check fails or takes more than 2.5 s, the move goes ahead.
- **Notifications.** An open, visible page shows a banner; a background tab gets a local notification through the service worker; a closed tab gets Web Push once VAPID keys are configured. One alert per event.
- **Training.** Lesson list with ECO code, move count and side; walkthrough with a note per move and "Also good" alternatives; practice as either side with **Hint**, a dashed arrow after 3 misses, and an off-line choice ("Keep playing freely" or "Back to the line"). Two lessons ship: Italian Game (C53) and French Exchange: Monte Carlo Variation (C01).
- **Single player.** Not available. Stockfish is installed at boot when missing, but nothing plays or analyses with it.

## Upcoming Work (intent 261113-p2-features)

The active intent asks for nine changes. Where each lands, from this scan:

| Request | Current state | Main seams |
|---|---|---|
| Ongoing sessions on the main screen | Not built. Seats are stored per room in the browser only | `static/js/seat-store.js`, `static/js/screens/lobby.js`, `GET /api/rooms/{code}` |
| Small animation when taking or losing a piece | Partial: opponent's captures fade (150 ms); own captures are not animated | `static/js/board/board.js`, `static/js/board/interaction.js`, `static/css/tokens.css` |
| Unjoined game convertible to pass-along, back to online when someone joins | Not built. Two token-bound seats, turn enforced per seat | `justchess/rooms.py`, `justchess/games.py`, `justchess/api.py`, `static/js/seat-store.js`, `static/js/view-model.js` |
| Board fits above the fold in game | Not met on short viewports: size follows width only | `static/css/app.css`, `static/css/board.css` |
| Share opens a modal with copy, email and messenger links | Not built: share sheet, clipboard or inline field | `static/js/share.js`, `static/js/app.js`, `templates/index.html`, `static/js/screens/blunder-dialog.js` (modal pattern) |
| Single player against Stockfish | Not built: discovery and install only | `stockfish_install.py`, `justchess/api.py` (`app.state.stockfish`), `POST /api/position/move` |
| More openings in the trainer | Two lessons; adding a file adds a lesson | `lessons/`, `justchess/lessons.py` |
| Trainers for specific situations | Not built; the lesson schema already accepts a start FEN | `justchess/lessons.py`, `static/js/training/` |
| Settings from `.env` | Present in the uncommitted working tree during this scan (`justchess/envfile.py`, called first in `app.py`); README documents it | `justchess/envfile.py`, `app.py`, `.env.example` |

## Glossary
- **Room**: a code, two seats (A and B), a sequence of games, a score by seat, and a pending rematch request.
- **Room code**: public 6-character code (A-Z, 0-9), also the invite path `/r/{CODE}`.
- **Seat** (slot A or B): a place in a room proven by a private seat token; seat A plays White in game 1, colours swap each rematch.
- **Seat token**: 256-bit secret, stored only as a SHA-256 hash on the server and under `justchess.seat.<CODE>` in the browser.
- **Watcher**: a client with no valid seat token; gets snapshots without legal moves.
- **Snapshot**: the per-viewer game state the server sends after every change (`api-documentation.md`).
- **Version**: a per-game counter bumped on every accepted change; a move on a stale version gets 409 with the latest snapshot.
- **Presence**: `empty`, `connected`, `away` or `abandoned` (away more than 24 hours) per seat.
- **Continue link**: one-use, 10-minute link moving a seat to another device.
- **Lesson**: a file-defined opening line with a note per move, optional alternatives and objectives.
- **Engine**: the Stockfish binary made available at boot; not used by features yet.
