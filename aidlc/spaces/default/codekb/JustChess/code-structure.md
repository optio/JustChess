# Code Structure: JustChess

## Repository Layout

The project's own files as on disk (uncommitted changes included). AI-DLC's install and the skipped folders listed at the end are not part of it. Line counts are from this run.

```
JustChess/
├── app.py                         # Entry: load .env, resolve DB and ENGINE_DIR, app = create_app(...)   (26)
├── stockfish_install.py           # Find or install pinned, verified Stockfish sf_19                     (272)
├── justchess/                     # Backend package, one module per component
│   ├── __init__.py                # DomainError (status, message, extra)                                  (36)
│   ├── api.py                     # Routes, request models, Services, create_app, lifespan                (714)
│   ├── rooms.py                   # Codes, seats, token hashes, presence, score, rematch                  (335)
│   ├── games.py                   # Rules, lifecycle, claims, per-viewer snapshot                         (375)
│   ├── live.py                    # LiveHub: sockets, hello handshake, presence, broadcasts               (260)
│   ├── db.py                      # Schema v3, startup check and upgrade, Database helper                 (287)
│   ├── housekeeping.py            # 30-day idle-room cleanup, hourly                                      (70)
│   ├── security.py                # Origin guard and body limit ASGI middleware                           (132)
│   ├── analysis.py                # Blunder analysis: mate in one, hanging pieces                         (337)
│   ├── lessons.py                 # Lesson files: safe load, validate, expand; free-play move             (429)
│   ├── notifications.py           # Alert events, subscriptions, one-alert claim, Web Push                (502)
│   ├── vapid.py                   # VAPID key loading and generator CLI                                   (232)
│   └── envfile.py                 # .env parser and loader (new during this scan)                         (85)
├── templates/
│   └── index.html                 # Page shell: top bar, share fallback, <main id="app">, announcer       (47)
├── lessons/
│   ├── italian.yaml               # Italian Game, C53, 7 plies                                            (61)
│   └── monte-carlo.yaml           # French Exchange: Monte Carlo Variation, C01                           (57)
├── static/
│   ├── sw.js                      # Service worker: push display, notification click                     (128)
│   ├── js/
│   │   ├── boot.js                # Classic script: theme and board before first paint                    (34)
│   │   ├── app.js                 # Entry module: routing, wiring, room lifecycle, share                  (587)
│   │   ├── api.js                 # Rooms HTTP client                                                     (148)
│   │   ├── live.js                # Socket client: hello, ping, visibility, backoff                       (259)
│   │   ├── hooks.js               # Extension points between units                                        (93)
│   │   ├── room-flow.js           # enterRoom, actionAnswer, submitMove, applyRefusal                     (143)
│   │   ├── screen-state.js        # Pure screen reducer                                                   (168)
│   │   ├── view-model.js          # Pure snapshot-to-view mapping                                         (326)
│   │   ├── seat-store.js          # Seat tokens in localStorage per room                                  (119)
│   │   ├── share.js               # Share sheet, clipboard, field fallback, URLs                          (57)
│   │   ├── settings.js            # Per-device settings store                                             (193)
│   │   ├── settings-panel.js      # Settings form                                                         (167)
│   │   ├── blunder.js             # beforeMove hook and dialog text                                       (162)
│   │   ├── notifications.js       # Permission, worker, push subscription, banner, local notifications    (311)
│   │   ├── notify-core.js         # Pure event keys and decisions (shared block with sw.js)               (167)
│   │   ├── contrast.js            # WCAG contrast audit of tokens.css                                     (249)
│   │   ├── board/
│   │   │   ├── board.js           # Board component (DOM shell, motion)                                   (532)
│   │   │   ├── geometry.js        # Pure squares, FEN, targets, move diff, names                          (294)
│   │   │   ├── interaction.js     # Pure selection / promotion / pending reducer                          (165)
│   │   │   └── promotion.js       # Promotion picker dialog                                               (120)
│   │   ├── screens/
│   │   │   ├── lobby.js           # Lobby view                                                            (143)
│   │   │   ├── game.js            # Game view                                                             (412)
│   │   │   ├── overlay.js         # End-of-game overlay                                                   (112)
│   │   │   ├── win-sequence.js    # Tip, dim, ink, glow                                                   (168)
│   │   │   └── blunder-dialog.js  # Modal alertdialog for warnings                                        (136)
│   │   └── training/
│   │       ├── trainer.js         # Trainer view                                                          (467)
│   │       ├── trainer-state.js   # Pure trainer reducer                                                  (460)
│   │       ├── lessons-api.js     # Lessons HTTP client                                                   (101)
│   │       └── arrow.js           # Arrow geometry and SVG                                                (95)
│   ├── css/
│   │   ├── tokens.css             # Colour, type, radius, motion tokens; themes; board themes             (203)
│   │   ├── base.css               # Fonts, type roles, buttons, focus ring, logo, settings controls      (222)
│   │   ├── board.css              # Frame, grid, squares, labels, highlights, picker                      (208)
│   │   ├── app.css                # Shell, top bar, lobby, game layout, overlay, dialog                   (422)
│   │   └── training.css           # Trainer layout                                                        (187)
│   ├── demo/                      # Design-system demo page (skimmed)
│   ├── fonts/, pieces/cburnett/   # Self-hosted binary assets (not opened)
│   ├── ASSETS.md, logo.svg
├── tests/                         # pytest + node:test (skimmed this run)
├── pyproject.toml, uv.lock, README.md, .gitignore, .env.example
```

## File Classification

| Area | Category |
|---|---|
| `app.py` | Configuration (entry point) |
| `justchess/api.py` | Controller/Handler, Configuration (factory, lifespan), Service orchestration |
| `justchess/rooms.py`, `justchess/games.py` | Service/UseCase plus Repository (inline parameterised SQL on a passed connection), Model (frozen dataclasses) |
| `justchess/db.py` | Repository infrastructure, Migration (schema create and v2 to v3 upgrade) |
| `justchess/live.py` | Controller (WebSocket), Service (presence) |
| `justchess/security.py` | Middleware |
| `justchess/housekeeping.py` | Service (scheduled job) |
| `justchess/analysis.py` | Service (pure domain logic) |
| `justchess/lessons.py` | Repository (file-backed catalog), Service (validation, expansion) |
| `justchess/notifications.py` | Service, Repository (subscriptions, alert records), Adapter (pywebpush) |
| `justchess/vapid.py`, `justchess/envfile.py` | Configuration |
| `stockfish_install.py` | Service, Utility (standard library only, injected I/O) |
| `static/js/app.js` | Controller (client shell) |
| `static/js/api.js`, `live.js`, `training/lessons-api.js` | Adapter (HTTP, WebSocket) |
| `screen-state.js`, `view-model.js`, `board/geometry.js`, `board/interaction.js`, `training/trainer-state.js`, `notify-core.js`, `room-flow.js`, `blunder.js` | Service (pure logic) |
| `board/board.js`, `board/promotion.js`, `screens/*`, `training/trainer.js`, `training/arrow.js`, `settings-panel.js` | View (DOM) |
| `seat-store.js`, `settings.js` | Repository (browser storage) |
| `hooks.js`, `share.js`, `contrast.js` | Utility |
| `static/sw.js` | Service worker |
| `static/css/*`, `templates/index.html` | Static/Asset |
| `lessons/*.yaml` | Data |

## Module Internals

### Backend

| Module | Key symbols |
|---|---|
| `__init__` | `DomainError(status, message, **extra)`; the API's exception handler answers `{"detail": message, **extra}` |
| `api` | Request models `JoinRequest`, `SeatRequest`, `MoveRequest` (uci 1-8 chars, `version >= 0`), `ContinueRequest`, `PositionMoveRequest` (fen <= 100), `SubscribeRequest`, `UnsubscribeRequest`; `Services` (db, clock, room locks, `LiveHub`, `VapidConfig`, `Notifier`; `mutate`, `read_move_check`, snapshot builders, hub callbacks, `schedule_alert`); `create_app(db_path, clock, engine_dir, receive_timeout, origin, cleanup_hooks, lessons_dir, vapid, push_sender)`; route groups `_add_page_routes`, `_add_lesson_routes`, `_add_room_routes`, `_add_game_routes`, `_add_push_routes`, `_add_socket_route`; `_judge_move` (replay + analyse) |
| `rooms` | `Room`, `Seat`, `JoinResult`, `Transfer`; `normalize_code`, `generate_code`, `issue_token` (32 bytes), `hash_token`, `token_matches`; `create_room` (10 tries, else 503), `join_room`, `authorize_seat` (403), `issue_continue_token` (10 min), `redeem_continue_token`; `touch_room`, `touch_seat` (60 s throttle), `seat_presence`, `is_abandoned` (24 h); `record_result`, `request_rematch`, `rematch_state`; `list_idle_rooms`, `delete_room` |
| `games` | `Game` (`colour_of`, `slot_of`), `StoredMove`, `End`, `RoomView`, `GameView` (cached legal moves and claim); `current_game` (highest number), `load_moves`, `replay_board`; `start_game`, `create_first_game` (A white, waiting), `start_rematch` (colours flipped, playing), `mark_playing`, `bump_version`; `automatic_end`, `claimable_draw`, `parse_legal_move`, `require_move_turn`, `apply_move`, `claim_draw`, `claim_win`; `numbered_moves`; `delete_games_for_room` |
| `live` | `Connection` (ws, slot, token hash, visible, last_heard), `LiveHub` (`connected_slots`, `is_visible`, `is_fresh_visible`, `broadcast`, `notify_seat_moved`, `serve`); close codes 1003, 1008, 1009, 1011, 4408 |
| `db` | `SCHEMA_VERSION = 3`, `BASE_SCHEMA`, `V3_SCHEMA`; `Database` (`connect`, `transaction`, `read`); `prepare_database`; `resolve_db_path` (`JUSTCHESS_DB`) |
| `housekeeping` | `RETENTION` 30 days, `INTERVAL` 1 hour; `run_cleanup`, `run_forever`; per-room transaction with hooks first |
| `security` | `OriginGuardMiddleware`, `BodyLimitMiddleware` (`MAX_BODY_BYTES = 4096`), `expected_origin` |
| `analysis` | `analyse(board, move, budget_ms=250)`, `BlunderWarning`; piece values; static exchange evaluation by pushing real moves; "only new problems" via a null move; no-alternative sweep |
| `lessons` | `LESSON_ID`, `ECO_PATTERN`, `MAX_FILE_BYTES` 64 KB, `MAX_MOVES` 60; `validate`, `expand`, `load_catalog`, `LessonStore.catalog`, `LessonCatalog.summaries/get`; `position_move` |
| `notifications` | `AlertEvent` (url, tag, payload), `joined_event`, `event_after_move`, `event_after_claim`, `Presence`; `validate_subscription` (https, allow-listed host, P-256 keys), `save_subscription` (keep 5), `delete_*`; `claim`, `mark`; `WebPushSender` (no redirects, TTL 3600, 10 s), `Notifier.dispatch` |
| `vapid` | `VapidConfig`, `load_vapid` (env key, else key file outside the project), `generate`, CLI `python -m justchess.vapid generate <path>` |
| `envfile` | `parse(text)`, `load(path=<root>/.env, environ=os.environ)`: no override, logs bad line numbers only |

### Frontend

| Module | Exports / role |
|---|---|
| `app.js` | `startApp({ doc, win, fetchImpl, WebSocketImpl })`; screens `lobby`, `game`, `learn`; routes `/`, `/r/{code}`, `/learn(/id)`; `openRoom`, `startGame`, `onMove`, `seatAction`, `shareInvite`, `shareResult`, `makeContinueLink`; registers hooks `notifications`, `onSnapshot`, `lessonsMount`, `beforeMove` |
| `api.js` | `createApi(fetch)`: `createRoom`, `join`, `state`, `move`, `checkMove`, `claimDraw`, `claimWin`, `rematch`, `continueLink`, `redeemContinue`; always resolves `{ok, status, data | message, snapshot?}` |
| `live.js` | `createLive({...})`, `backoffDelay`, `socketUrl`; drops older snapshots by (game, version) |
| `screen-state.js` | `reduce(state, event)`; views `lobby`, `notFound`, `joining`, `waiting`, `playing`, `gameOver`, `watching`; `transition` `ended` / `newGame` |
| `view-model.js` | `viewModel(snapshot, ctx)` -> board, status, claims, scoresheet, score, players, overlay, notices, yourMove, seat; `announcement`; `END_TITLES` |
| `seat-store.js` | `createSeatStore()`: `get`, `set`, `remove`, `persistent`; keys `justchess.seat.<CODE>`; `parseContinueFragment` |
| `share.js` | `chooseShareMethod`, `shareLink`, `copyText`, `inviteUrl`, `continueUrl`; constants `SHARE_TITLE`, `COPIED_LABEL`, `COPIED_MS` |
| `settings.js` | `createSettings()`, key `justchess.settings.v1`: `theme`, `board`, `labels`, `blunderWarnings`, `notifications`; `applyToDocument` |
| `board/board.js` | `createBoard(el, {fen, orientation, legalMoves, lastMove, check, interactive, labels, piecePath, onMove, onRejectedTap, hintSquare})`: `set`, `reject`, `focus`, `destroy`, `mode`; motion `slide`, `fadeCaptured`, `pulseCheck` |
| `screens/game.js` | `createGameScreen(container, deps)`: `render(view, {endPhase, reconnecting})`, `renderJoining`, `flash`, `showBanner`, `board`, `overlay`, `notifyBanner`, `destroy` |
| `screens/lobby.js` | `renderLobby(container, {onStart, onJoin, onLearn, labels})`: `update`, `setBusy`, `showStartError`, `setLabels`, `destroy` |
| `screens/blunder-dialog.js` | `createBlunderDialog(container)`: `open(text, {version, game, returnFocus})`, `supersede`, `close` |
| `training/trainer.js` | `mountTrainer(el, {api, initialLessonId, variant: "page" | "drawer", settings, onRoute, win})`: `open`, `destroy` |
| `training/trainer-state.js` | `reduce(state, event)`; phases `choosing`, `walkthrough`, `practice`, `offLine`, `freePlay`, `complete`; `TRAINER_DELAY_MS` 500, `ARROW_AFTER_MISSES` 3 |

`templates/index.html` element IDs the shell needs: `app`, `room-bar`, `room-code`, `share`, `share-fallback`, `share-field`, `announcer`, `home-link`; class `topbar`. Everything else is built by the modules.

## Code Patterns

- **One transaction per request, under the room lock.** `Services.mutate(code, action)` wraps `action(conn, now)`; business modules never open connections themselves.
- **Domain refusals as `DomainError`.** Raised with an HTTP status and a player-facing message; a 409 gets the latest snapshot attached.
- **Injected clock and I/O.** `clock` in rooms, games, housekeeping, live, notifications; `which`, `downloader`, `platform` in the installer; `fetchImpl`, `WebSocketImpl`, `timers`, `storage` in the JS modules.
- **Pure core, thin shell.** Reducers return `{state, effects}` (board, trainer) or a new state (screen); DOM modules run the effects.
- **Never throw at boundaries.** `ensure_stockfish`, `Notifier.dispatch_safely`, the JS API clients (resolve, never reject), hooks wrapped by `callSafely` and `runBeforeMove` (fail closed), the blunder hook (fail open).
- **Board answer contract.** After `onMove(uci)` the board is pending until the caller answers with `set({fen})` or `reject()`.
- **Hooks for cross-unit features.** `hooks.beforeMove`, `hooks.notifications`, `hooks.onSnapshot`, `hooks.lessonsMount`.
- **Accessibility built in.** Native buttons with 44 px targets, roving tabindex on the board grid, `aria-live` regions, an `alertdialog` with a focus trap, `data-testid` on interactive elements.
- **Naming.** Python snake_case with docstrings citing business rules (BR, W, U numbers); JS camelCase with a header comment per module describing its contract.

## Skipped Folders

`.venv/`, every `__pycache__/`, `.pytest_cache/`, `.engines/`, `.git/`, `justchess.sqlite3` and `justchess.sqlite3.old`, `.env`, and AI-DLC's own install were not opened. `static/fonts/` and `static/pieces/` hold binary assets and were only listed.
