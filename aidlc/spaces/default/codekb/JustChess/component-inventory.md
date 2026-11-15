# Component Inventory

> Historical baseline retained from earlier scans. The Current footer sections below supersede conflicting identity/presentation statements. Outside-focus prose is preserved, not newly verified.

## Env File Loader

justchess/envfile.py loads optional .env without overriding process environment; secrets are not logged.

## App Entry Point

app.py loads environment before resolving the SQLite fallback path; DATABASE_URL is resolved at startup and constructs the ASGI application.

## App Factory and Services

justchess/api.py wires lifespan, injectable stores, room locks, engine, notifications and housekeeping.

## Game API

api.py exposes room, seat, move, draw, rematch and computer operations; server validates every move.

## Lesson API

api.py exposes catalog, lesson detail and stateless legal position moves.

## Push API

api.py exposes VAPID key and authenticated subscription management.

## Engine Status API

api.py exposes availability and path source without disclosing the binary path.

## Rooms Module

rooms.py owns hashed seat credentials, join requests, modes, continuation links and scores.

## Games Module

games.py replays persisted UCI history, validates versions and turns, and computes outcomes.

## Live Hub

live.py broadcasts viewer-specific snapshots and tracks visibility, pings and seat replacement.

## Persistence (SQLite)

db.py owns schema version 4, short connections and explicit transactions for SQLite and PostgreSQL.

## Housekeeping

housekeeping.py expires join requests and removes rooms idle for the configured retention.

## Security Middleware

security.py checks supplied origins and limits request bodies; ratelimit.py limits selected operations.

## Blunder Analysis

analysis.py finds mate-in-one and newly hanging pieces under a bounded analysis budget.

## Lesson Store

lessons.py validates safe YAML/JSON files, legal SAN/UCI sequences and cached catalogs.

## Lesson Files

lessons/ contains eighteen openings, traps and defence walkthroughs with practice metadata.

## Notifications Service

notifications.py validates push destinations, deduplicates events and delivers background web push.

## VAPID Keys

vapid.py loads environment or protected external key files; generation refuses overwriting keys.

## Stockfish Installer

stockfish_install.py resolves configured/PATH/cached binaries or verifies pinned release downloads.

## Page Template

templates/index.html supplies the shared shell, dialogs, announcer and serialized gameplay settings.

## App Shell and Router

static/js/app.js routes rooms and training screens and guards stale asynchronous navigation.

## HTTP Client

api.js supplies JSON requests and normalized HTTP errors; seat secrets travel in bodies or a header.

## Live Client

live.js reconnects sockets with capped backoff and rejects stale game/version updates.

## Room Flow

room-flow.js orchestrates creation, joining and continuation; pending requests use session storage.

## Screen State

screen-state.js derives screen transitions from room and request state.

## View Model

view-model.js derives status, scores, turn permissions and capture displays.

## Seat Store

seat-store.js stores per-room credentials locally with a memory fallback.

## Share Helpers

share.js builds invitation URLs and external share destinations without seat credentials.

## Hooks

hooks.js coordinates move hooks; blunder hooks handle stale results and bounded network waits.

## Board Component

board modules implement accessible squares, legal interactions, promotion, arrows and capture animation.

## Lobby Screen

lobby and computer modules offer friend/computer creation and saved-room reopening.

## Game Screen

game.js renders board, status, scoresheet, requests, computer controls and rematch actions.

## Blunder Warnings UI

blunder modules display move warnings and confirmation with stale-version protection.

## Settings

settings modules persist presentation preferences and expose a keyboard-accessible drawer.

## Notifications Client

notification modules coordinate visible banners, service-worker notifications and push registration.

## Service Worker

static/sw.js validates same-origin notification destinations; it does not cache application resources.

## Opening Trainer

trainer.js runs walkthroughs, either-side practice, hints and off-line free play.

## Contrast Audit

contrast.js measures theme text contrast and provides a development audit.

## Stylesheets

five authored CSS files implement theme tokens, layout, board and responsive training presentation.

## Persistence Backend

Database.read/transaction provide the existing connection seam; domain SQL uses qmark parameters through SQLite or the PostgreSQL compatibility adapter.

## Database Configuration

JUSTCHESS_DB selects the SQLite fallback path; nonempty DATABASE_URL selects PostgreSQL, with fail-fast credential-safe errors.

## Room Persistence Rules

rooms.py enforces unique room seats, hashed capabilities and one pending request per room.

## Game Persistence Rules

games.py serializes moves and updates version, result, captures and counted scores atomically.

## Room Summaries

summaries.py validates up to fifty seats and reads consistent snapshots without updating activity.

## Persistence Regression Tests

tests/core/test_db.py and conftest.py assert SQLite constraints and isolated temporary databases.

## Engine

engine.py serializes UCI work through one process with bounded queues, cancellation and limited recovery.

## Computer Coordination

computer.py tracks version-scoped replies and hints and implements five configured skill levels.

## Gameplay Settings

gameplay.py validates gameplay.yaml and publishes safe client settings at startup.

## Rate Limiter

ratelimit.py uses bounded process-local sliding windows and explicitly trusted proxy handling.

## Puzzle Store

puzzles.py validates six generated theme catalogs and hides solution lines from detail responses.

## Puzzle Trainer

puzzles UI/state modules implement setup, checking, replies, hints and progress.

## Endgame Store

endgames.py validates four categories and replays client histories to judge mate, promotion or draw.

## Endgame Trainer

endgame UI/state modules persist attempts in session storage and request engine defence moves.

## Trainer Hub

training modules provide accessible ordered tabs and catalogs for openings, traps, tactics, defence and endgames.

## Trainer Progress

progress.js stores bounded browser-local completion records.

## Share Dialog and QR

share-dialog and authored QR modules render local invitation QR codes and accessible modal actions.

## Curation Tool

scripts/curate_puzzles.py performs deterministic offline sampling and validates all output before writing.


## PostgreSQL Adapter

postgres.py translates qmarks/transactions, supports named and positional rows and sanitizes driver exceptions into the existing sqlite3 hierarchy.

## Account-free Identity Seam

Historical seam finding: room seats were separate capabilities. The current Player Identity Client now restores profile and associated seats; backend internals were not rescanned.

## Private Continue Link

rooms.py issues one active ten-minute token per seat; redemption rotates authority and clears the link. share.js encodes it in a fragment; game settings exposes it. It is not reusable recovery.

## Result Presentation and Motion

view-model.js maps viewer slot/colour, scores, result and reason to labels. overlay.js renders text with textContent; win-sequence.js tips the loser, dims the board, inks the result and glows the winner, with cancel/clear/reduced-motion handling. No confetti is implemented.

## Selection and Board Theme Settings

interaction.js owns selection and board.js toggles square classes. board.css currently adds only a selected ring. settings/boot/panel/tokens contain three duplicated board allowlists and styles that must agree when adding themes.

## Focused Browser Storage Tests

tests/js/settings.test.mjs and seat-store.test.mjs cover malformed/blocked storage, defaults, cross-tab settings, boot consistency, legacy seats and continue-fragment validation.


## Player Identity Client

player-identity.js stores token/recovery under justchess.player.v1, initializes/restores profiles, attaches seats and exposes nickname/regenerate/link operations. Failed requests preserve credentials; regeneration retains sessions.

## Player Footer

mountPlayerFooter binds a persistent template footer. Current nickname is always editable with a separate submit button; no readonly/pencil state exists. Save my player is an anchor, Copy private link invokes clipboard, and Generate new link uses win.confirm. Status text uses textContent.

## Modal Patterns

share-dialog.js manages a native modal with focus wrapping/restoration; screens/blunder-dialog.js manages a custom labelled alertdialog with safe initial focus, Escape cancellation and focus containment.

## Player Footer Regression Tests

Node tests cover recovery parsing, credential restoration and regeneration session retention. Browser tests submit nickname, use the recovery anchor across devices and stub native confirmation. They do not currently test saved/edit UI or a footer regeneration modal.

