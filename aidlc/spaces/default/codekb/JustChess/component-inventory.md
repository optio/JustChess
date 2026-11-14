# Component Inventory: JustChess

Headings are the canonical component names used by the Scope of Analysis block. The 39 component sections (backend and frontend) were analyzed deeply in this run; the Test Suite was only skimmed. The prior store's names "WebSocket Broadcast", "Frontend Controller" and "Stylesheet" described the pre-redesign single-file app; they are replaced by Live Hub, the frontend components below, and Stylesheets.

**Backend components**

## Env File Loader

- **Location**: `justchess/envfile.py`, called first in `app.py`
- **Responsibility**: Copy `KEY=VALUE` lines from `<root>/.env` into `os.environ` without overriding variables already set; tolerate `export`, comments and quotes; log malformed line numbers, never values.
- **Depends on**: standard library only
- **Used by**: App Entry Point; `tests/test_envfile.py`
- **Notes**: Appeared in the working tree during this scan (with `.env.example`, README "Configuration" and VAPID wording changes). Must run before `justchess.api` is imported, because some settings are read at import.

## App Entry Point

- **Location**: `app.py`
- **Responsibility**: Load `.env`, resolve `DB` (`JUSTCHESS_DB`) and `ENGINE_DIR` (`.engines/stockfish-sf_19` next to `app.py`), and expose `app = create_app(db_path=lambda: DB, engine_dir=lambda: ENGINE_DIR)` for `uvicorn app:app` and `fastapi dev`.
- **Depends on**: Env File Loader, App Factory and Services, Persistence (SQLite), Stockfish Installer
- **Used by**: Uvicorn; tests that patch `app.DB`

## App Factory and Services

- **Location**: `justchess/api.py` (`create_app`, `lifespan`, `Services`, `services`, `_resolve_path`, `_prepare_stockfish`, `_load_lessons`)
- **Responsibility**: Build the FastAPI app with middleware, static mount, templates and route groups; at startup prepare the database, load VAPID keys and push hosts, create `Services` (database, clock, per-room locks, Live Hub, Notifier), scan lessons, and start the Stockfish and housekeeping tasks (cancelled on shutdown). `Services.mutate` runs one use case per room lock and transaction and attaches the latest snapshot to a 409.
- **Depends on**: every backend module
- **Used by**: all route groups
- **Notes**: Every external dependency is a `create_app` parameter so tests inject them.

## Game API

- **Location**: `justchess/api.py` (`_add_room_routes`, `_add_game_routes`, `_add_page_routes` page routes, request models)
- **Responsibility**: Create, join, read, move, check-move, claim draw, claim win, rematch, continue-link and continue; serve the page shell at `/`, `/r/{code}`, `/learn`, `/learn/{id}`.
- **Depends on**: App Factory and Services, Rooms Module, Games Module, Live Hub, Blunder Analysis, Notifications Service
- **Used by**: HTTP Client, Blunder Warnings UI
- **Notes**: Contract in `api-documentation.md`. No route lists several rooms, releases a seat, or creates a local or engine game.

## Lesson API

- **Location**: `justchess/api.py` (`_add_lesson_routes`)
- **Responsibility**: List lessons, return one lesson, and play a stateless free-play move.
- **Depends on**: Lesson Store
- **Used by**: Opening Trainer

## Push API

- **Location**: `justchess/api.py` (`_add_push_routes`)
- **Responsibility**: Serve `/sw.js`, the VAPID public key, and seat-owned subscribe and unsubscribe.
- **Depends on**: Notifications Service, VAPID Keys, Rooms Module
- **Used by**: Notifications Client, Service Worker

## Engine Status API

- **Location**: `justchess/api.py` (`engine` route, `_prepare_stockfish`)
- **Responsibility**: Report whether Stockfish is available, its source and version, never its path.
- **Depends on**: Stockfish Installer (result on `app.state.stockfish`)
- **Used by**: nothing in the UI; tests
- **Notes**: `app.state.stockfish` holds the `EngineResult` with the binary path, the natural hand-off for a future engine service.

## Rooms Module

- **Location**: `justchess/rooms.py`
- **Responsibility**: Room codes, seats A and B, hashed tokens with constant-time checks, rejoin and seat B creation, continue tokens, activity and presence, score by seat, rematch requests, idle-room listing and deletion.
- **Depends on**: `sqlite3` connection from the caller, `DomainError`
- **Used by**: App Factory and Services, Game API, Push API, Housekeeping, Notifications Service
- **Notes**: Exactly two slots (`SLOTS = ("A", "B")`); any tokenless join takes a free seat B.

## Games Module

- **Location**: `justchess/games.py`
- **Responsibility**: Game lifecycle (first game, rematch with colours flipped, waiting to playing), move validation by replaying stored moves, automatic ends, draw and win claims, version bumps, and the per-viewer snapshot.
- **Depends on**: python-chess, caller's connection
- **Used by**: App Factory and Services, Game API, Housekeeping, Notifications Service
- **Notes**: Turn is enforced by slot (`slot_of(board.turn)`); games always start from the standard position.

## Live Hub

- **Location**: `justchess/live.py`
- **Responsibility**: Accept sockets, run the hello handshake, track presence and visibility per socket, broadcast per-viewer snapshots, tell moved seats, and record lastSeenAt through a callback.
- **Depends on**: callbacks from Services (identify, mark seen, snapshot source)
- **Used by**: Game API, App Factory and Services, Notifications Service (presence read in the handler)
- **Notes**: In-process registry; one worker only.

## Persistence (SQLite)

- **Location**: `justchess/db.py`
- **Responsibility**: Schema version 3, startup check (keep, upgrade v2 in place, refuse newer, else move aside and recreate), short-lived connections with foreign keys, `BEGIN IMMEDIATE` transactions.
- **Depends on**: `sqlite3`, `JUSTCHESS_DB`
- **Used by**: Rooms Module, Games Module, Notifications Service, Housekeeping, App Factory and Services
- **Notes**: Schema in `api-documentation.md`, Data Store. Upgrade path exists only from version 2.

## Housekeeping

- **Location**: `justchess/housekeeping.py`
- **Responsibility**: Delete rooms idle for 30 days at startup and hourly, one transaction per room, cleanup hooks first.
- **Depends on**: Persistence (SQLite), Rooms Module, Games Module; hook `notifications.delete_room_data`
- **Used by**: App Factory and Services (background task)

## Security Middleware

- **Location**: `justchess/security.py`
- **Responsibility**: Refuse cross-origin state changes and sockets; limit request bodies to 4 KB.
- **Depends on**: Starlette types, `JUSTCHESS_ORIGIN`
- **Used by**: App Factory and Services

## Blunder Analysis

- **Location**: `justchess/analysis.py`
- **Responsibility**: Judge one candidate move: mate in one allowed, or a knight, bishop, rook or queen newly hanging by static exchange; only new problems; dropped when every legal move has the same problem; 250 ms sweep budget.
- **Depends on**: python-chess only
- **Used by**: Game API (`check-move` via `_judge_move` in a worker thread)

## Lesson Store

- **Location**: `justchess/lessons.py`
- **Responsibility**: List lesson files safely, parse YAML (`safe_load`) or JSON, validate (BR1.2), expand into steps with FEN, legal moves and SAN/UCI, rescan when the folder stamp changes, and play stateless free-play moves.
- **Depends on**: PyYAML, python-chess, the lessons folder
- **Used by**: Lesson API, App Factory and Services (startup scan)
- **Notes**: Supports `start: <FEN>`, so lines can begin mid-game; alternatives are notes only.

## Lesson Files

- **Location**: `lessons/italian.yaml`, `lessons/monte-carlo.yaml`
- **Responsibility**: The two shipped opening lines (Italian Game C53, 7 plies, side white; French Exchange: Monte Carlo Variation C01, side white).
- **Depends on**: the schema in Lesson Store
- **Used by**: Lesson Store

## Notifications Service

- **Location**: `justchess/notifications.py`
- **Responsibility**: Build alert events (`joined`, `move:<game>:<ply>`, `ended:<game>`), validate and store push subscriptions, claim each event once, skip when a fresh visible page covers it, send Web Push and prune gone endpoints.
- **Depends on**: Persistence (SQLite), VAPID Keys, Rooms Module, Games Module, pywebpush, requests, cryptography
- **Used by**: Game API, Push API, Housekeeping (hook), App Factory and Services
- **Notes**: Alerts assume the target seat is another person; the joined alert always targets seat A.

## VAPID Keys

- **Location**: `justchess/vapid.py`
- **Responsibility**: Load the Web Push signing key from `JUSTCHESS_VAPID_PRIVATE_KEY` or a key file outside the project; disable push with one logged reason otherwise; generate a new key file (`python -m justchess.vapid generate <path>`).
- **Depends on**: cryptography, py_vapid
- **Used by**: Notifications Service, Push API

## Stockfish Installer

- **Location**: `stockfish_install.py`
- **Responsibility**: Find Stockfish (`STOCKFISH_PATH`, then PATH, then the cached install) or download, verify (SHA-256) and safely extract the pinned `sf_19` build for Linux aarch64, Linux x86-64 or macOS; never raise.
- **Depends on**: standard library only; GitHub releases over HTTPS
- **Used by**: App Factory and Services (boot task), Engine Status API, App Entry Point (`PINNED_VERSION`)
- **Notes**: Only discovery and installation; no UCI communication exists.

## Page Template

- **Location**: `templates/index.html`
- **Responsibility**: The page shell: boot script, five stylesheets, favicon, top bar with logo, room code and Share button, the hidden share fallback field, `<main id="app">`, the screen-reader announcer and the app module.
- **Depends on**: Stylesheets, Settings (`boot.js`), App Shell and Router
- **Used by**: page routes
- **Notes**: No Jinja2 variables.

**Frontend components**

## App Shell and Router

- **Location**: `static/js/app.js`
- **Responsibility**: Client routing (`/`, `/r/{code}`, `/learn`, `/learn/{id}`) with `pushState`; build and destroy screens; open and close rooms (join, state read, socket); dispatch screen events; send moves and seat actions; share the invite and the result; make continue links; register the cross-unit hooks.
- **Depends on**: HTTP Client, Live Client, Room Flow, Screen State, View Model, Seat Store, Share Helpers, Hooks, Settings, Notifications Client, Blunder Warnings UI, Lobby Screen, Game Screen, Opening Trainer
- **Used by**: Page Template

## HTTP Client

- **Location**: `static/js/api.js`
- **Responsibility**: Typed calls to the room routes; validate codes, tokens and UCI before any request; resolve, never reject.
- **Depends on**: `fetch`
- **Used by**: App Shell and Router, Room Flow, Blunder Warnings UI

## Live Client

- **Location**: `static/js/live.js`
- **Responsibility**: The room socket: hello with token, ping every 5 s, visibility, drop older snapshots, reconnect with backoff, stop on 1008, handle `seat-moved`.
- **Depends on**: `WebSocket`, timers, document visibility
- **Used by**: App Shell and Router, Room Flow

## Room Flow

- **Location**: `static/js/room-flow.js`
- **Responsibility**: `enterRoom` (redeem continue, join or rejoin, stale-seat and storage notices), `actionAnswer`, `submitMove` (through `runBeforeMove`), `applyRefusal`.
- **Depends on**: HTTP Client, Hooks, Seat Store
- **Used by**: App Shell and Router

## Screen State

- **Location**: `static/js/screen-state.js`
- **Responsibility**: Pure reducer for the base view, connection flag, latest snapshot, notices, `ended` / `newGame` transitions and lobby errors.
- **Depends on**: nothing
- **Used by**: App Shell and Router

## View Model

- **Location**: `static/js/view-model.js`
- **Responsibility**: Pure mapping from snapshot plus context to board options (orientation follows the viewer's colour), status, claims, scoresheet, score, player names, overlay and notices; live-region announcements.
- **Depends on**: nothing
- **Used by**: App Shell and Router, Game Screen (through the view)

## Seat Store

- **Location**: `static/js/seat-store.js`
- **Responsibility**: Keep `{token, slot}` per room in `localStorage` (`justchess.seat.<CODE>`), fall back to memory when storage is blocked, parse `#continue=` fragments.
- **Depends on**: `localStorage`
- **Used by**: App Shell and Router, Room Flow
- **Notes**: The only record of a browser's games; one seat per room code; no index of codes.

## Share Helpers

- **Location**: `static/js/share.js`
- **Responsibility**: Choose share sheet, clipboard or field; share a link; copy text; build invite and continue URLs.
- **Depends on**: `navigator.share`, `navigator.clipboard`
- **Used by**: App Shell and Router
- **Notes**: No DOM; no email or messenger links.

## Hooks

- **Location**: `static/js/hooks.js`
- **Responsibility**: Named extension points `beforeMove`, `notifications`, `onSnapshot`, `lessonsMount`; `runBeforeMove` fails closed, `callSafely` contains errors.
- **Depends on**: nothing
- **Used by**: App Shell and Router, Room Flow, Game Screen

## Board Component

- **Location**: `static/js/board/board.js`, `geometry.js`, `interaction.js`, `promotion.js`
- **Responsibility**: Accessible 8x8 grid of buttons with roving focus; tap and keyboard moves; optimistic move with a pending lock until the caller answers; promotion picker; last-move, check and hint highlights; slide, capture fade and check pulse animations (Web Animations API, token durations, none under reduced motion).
- **Depends on**: Stylesheets (tokens for motion), piece SVGs
- **Used by**: Game Screen, Lobby Screen, Opening Trainer
- **Notes**: Own captures are not faded (optimistic apply). Size follows its container width.

## Lobby Screen

- **Location**: `static/js/screens/lobby.js`
- **Responsibility**: Hero text, Start a game, Learn an opening, room-code form with validation, and a static starting board.
- **Depends on**: Board Component, HTTP Client (`normalizeCode`)
- **Used by**: App Shell and Router
- **Notes**: No list of ongoing games.

## Game Screen

- **Location**: `static/js/screens/game.js`, `screens/overlay.js`, `screens/win-sequence.js`
- **Responsibility**: Board column and side panel (status, flash, notification banner, claims, notices, Game settings sheet with the continue-link row, scoresheet, room score, lessons drawer); end-of-game overlay with rematch and share; win sequence (king tip, dim, inked result, glow).
- **Depends on**: Board Component, Settings, Opening Trainer (through `lessonsMount`), View Model output
- **Used by**: App Shell and Router

## Blunder Warnings UI

- **Location**: `static/js/blunder.js`, `static/js/screens/blunder-dialog.js`
- **Responsibility**: The `beforeMove` hook (setting check, 2.5 s timeout, failure mapping) and the modal `alertdialog` with focus trap and Escape handling.
- **Depends on**: HTTP Client (`checkMove`), Settings
- **Used by**: App Shell and Router
- **Notes**: The project's only modal dialog; the pattern to reuse for a share modal.

## Settings

- **Location**: `static/js/settings.js`, `static/js/settings-panel.js`, `static/js/boot.js`
- **Responsibility**: Per-device settings (`theme`, `board`, `labels`, `blunderWarnings`, `notifications`) in `localStorage` with cross-tab sync; the settings form; theme and board applied before first paint.
- **Depends on**: `localStorage`
- **Used by**: App Shell and Router, Game Screen, Lobby Screen, Opening Trainer, Blunder Warnings UI, Notifications Client
- **Notes**: Browser-side only; unrelated to server `.env` settings.

## Notifications Client

- **Location**: `static/js/notifications.js`, `static/js/notify-core.js`
- **Responsibility**: Permission prompt inside the click, service worker registration, push subscribe and unsubscribe for the current seat, event keys from snapshots, banner or local notification, de-duplication by tag in `sessionStorage`.
- **Depends on**: Push API, Service Worker, Settings
- **Used by**: App Shell and Router (hooks `notifications` and `onSnapshot`)

## Service Worker

- **Location**: `static/sw.js`
- **Responsibility**: Show push notifications with tag `<code>:<key>` and renotify off; on click focus or open `/r/<code>` on this origin. Caches nothing.
- **Depends on**: a copy of the pure block of Notifications Client (pinned equal by a test)
- **Used by**: browsers, registered by Notifications Client

## Opening Trainer

- **Location**: `static/js/training/trainer.js`, `trainer-state.js`, `lessons-api.js`, `arrow.js`
- **Responsibility**: Lesson list, walkthrough, practice on either side with scripted replies after 500 ms, hints, arrow after 3 misses, off-line choice and free play through the stateless position route; page variant (`/learn`) and drawer variant (in game, own board).
- **Depends on**: Lesson API, Board Component, Settings
- **Used by**: App Shell and Router, Game Screen (drawer)
- **Notes**: Linear lines only; only the taught move counts as correct.

## Contrast Audit

- **Location**: `static/js/contrast.js`
- **Responsibility**: Parse `tokens.css` and check WCAG contrast for pieces, labels (also under highlights), buttons, text, focus ring and the trainer arrow in every board and page theme.
- **Depends on**: the text of `static/css/tokens.css` (one declaration per line)
- **Used by**: `tests/js/contrast.test.mjs`, the demo page

## Stylesheets

- **Location**: `static/css/tokens.css`, `base.css`, `board.css`, `app.css`, `training.css`
- **Responsibility**: All colours as tokens (light, dark, three board themes), motion tokens (`--t-slide` 200 ms, `--t-capture` 150 ms, `--t-pulse` 300 ms, `--capture-drop` 6 px; 0 under reduced motion), fonts and button roles, board frame and squares, page layout per breakpoint, trainer layout.
- **Depends on**: data attributes set by Settings (`data-theme`, `data-board`) and class names from the JS views
- **Used by**: Page Template
- **Notes**: Board size is width-based at every breakpoint; `tokens.css` must keep one declaration per line for the Contrast Audit.

## Test Suite (skimmed)

- **Location**: `tests/` (pytest), `tests/core/` (backend U1), `tests/js/` (`node --test`, run from pytest by `tests/test_frontend_js.py`)
- **Responsibility**: Backend rules, API, sockets, db upgrade, notifications and push, blunder analysis and check-move, lessons and the lessons API, `.env` loading, installer; JS reducers, view model, clients, board geometry and interaction, contrast and assets; headless Chromium runs of a full game, notifications and the trainer (skipped without a browser).
- **Notes**: About 153 Python test functions and about 139 JS tests by name count; not run and not deeply read this run.

## Dependency Summary

| Component | Depends on components |
|---|---|
| Env File Loader | none |
| App Entry Point | Env File Loader, App Factory and Services, Persistence (SQLite), Stockfish Installer |
| App Factory and Services | Persistence (SQLite), Rooms Module, Games Module, Live Hub, Notifications Service, VAPID Keys, Lesson Store, Housekeeping, Security Middleware, Stockfish Installer |
| Game API | App Factory and Services, Rooms Module, Games Module, Live Hub, Blunder Analysis, Notifications Service |
| Lesson API | Lesson Store |
| Push API | Notifications Service, VAPID Keys, Rooms Module |
| Engine Status API | Stockfish Installer |
| Rooms Module | none (caller's connection) |
| Games Module | none (caller's connection) |
| Live Hub | none (callbacks) |
| Persistence (SQLite) | none |
| Housekeeping | Persistence (SQLite), Rooms Module, Games Module, Notifications Service (hook) |
| Security Middleware | none |
| Blunder Analysis | none |
| Lesson Store | Lesson Files |
| Lesson Files | none |
| Notifications Service | Persistence (SQLite), VAPID Keys, Rooms Module, Games Module |
| VAPID Keys | none |
| Stockfish Installer | none |
| Page Template | Stylesheets, Settings, App Shell and Router |
| App Shell and Router | HTTP Client, Live Client, Room Flow, Screen State, View Model, Seat Store, Share Helpers, Hooks, Settings, Notifications Client, Blunder Warnings UI, Lobby Screen, Game Screen, Opening Trainer |
| HTTP Client | Game API |
| Live Client | Game API (socket) |
| Room Flow | HTTP Client, Hooks, Seat Store |
| Screen State | none |
| View Model | none |
| Seat Store | none |
| Share Helpers | none |
| Hooks | none |
| Board Component | Stylesheets |
| Lobby Screen | Board Component, HTTP Client |
| Game Screen | Board Component, Settings |
| Blunder Warnings UI | HTTP Client, Settings |
| Settings | none |
| Notifications Client | Push API, Service Worker, Settings |
| Service Worker | none |
| Opening Trainer | Lesson API, Board Component, Settings |
| Contrast Audit | Stylesheets |
| Stylesheets | none |

No import cycles were found. Server-side, Games and Rooms never import each other; `api.py` composes them.
