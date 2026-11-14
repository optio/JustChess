# API Documentation: JustChess

All routes are defined in `justchess/api.py`. There are no accounts. A seat is proven by its token: in the JSON body for actions, in the `X-Seat-Token` header for state reads, never in a query string or a log line. Two ASGI middlewares wrap every request (`justchess/security.py`):

- **Origin guard.** Any non-GET/HEAD/OPTIONS request and every WebSocket handshake with an `Origin` header that differs from the app's origin is refused (HTTP 403 `{"detail": "Cross-origin requests are not allowed"}`, socket close 1008). The expected origin is `JUSTCHESS_ORIGIN`, else the request `Host` with the `X-Forwarded-Proto` scheme, else the request scheme. No `Origin` header passes.
- **Body limit.** 4096 bytes, streamed bodies included: 413 `{"detail": "Request body too large"}`; a non-numeric `Content-Length` gets 400.

Errors use `{"detail": "<message>", ...extra}`. A `DomainError` 409 adds `"snapshot"` (the latest per-viewer snapshot). Pydantic validation errors are FastAPI's 422 `{"detail": [...]}`. Database errors are 500 "Something went wrong, please try again", logged with the room code only. There is no CORS configuration and no rate limiting.

## HTTP Endpoints

### Pages and assets

| Method | Path | Answer |
|---|---|---|
| GET | `/`, `/r/{code}`, `/learn`, `/learn/{lesson_id}` | 200 HTML (the same `index.html` shell; the client routes) |
| GET | `/static/*` | Static files (`StaticFiles`) |
| GET | `/sw.js` | `static/sw.js`, `text/javascript`, headers `Service-Worker-Allowed: /`, `Cache-Control: no-cache` |
| GET | `/api/engine` | `{available, path_source, version}`; `{false, null, null}` until the boot task finishes or when no engine was found. `path_source` is `env`, `path`, `cached` or `downloaded`; the binary path is never returned |

### Rooms and games

`{code}` is normalised (trimmed, upper-cased) and must match `^[A-Z0-9]{6}$`, else 400 "Room code must be 6 letters or digits".

| Method | Path | Body | Success | Refusals |
|---|---|---|---|---|
| POST | `/api/rooms` | none | 201 `{code, token, slot: "A", colour: "white"}`, header `Location: /r/{code}` | 503 "Could not create a room, try again" (10 code collisions) |
| POST | `/api/rooms/{code}/join` | `{token?}` (<= 256) | 200 `{code, token, slot, colour}` | 404 "Room not found", 409 "This game already has two players" (+snapshot) |
| GET | `/api/rooms/{code}` | header `X-Seat-Token` (optional) | 200 Snapshot for that seat, or the watcher snapshot | 404 |
| POST | `/api/rooms/{code}/moves` | `{token, uci, version}` | 200 Snapshot (mover's view) | 403 "This isn't your seat", 409 "Waiting for an opponent" / "Game is over" / "The board changed, here is the latest position" (+snapshot), 403 "Not your turn", 400 "Illegal move" |
| POST | `/api/rooms/{code}/check-move` | `{token, uci, version}` | 200 `{warning, san, version}` | same as moves, in the same order; never writes, never bumps the version |
| POST | `/api/rooms/{code}/claim-draw` | `{token}` | 200 Snapshot | 409 "A draw can't be claimed right now", plus the seat, status and turn refusals |
| POST | `/api/rooms/{code}/claim-win` | `{token}` | 200 Snapshot | 409 "Your opponent hasn't been away long enough" |
| POST | `/api/rooms/{code}/rematch` | `{token}` | 200 Snapshot | 409 "Finish this game first" |
| POST | `/api/rooms/{code}/continue-link` | `{token}` | 200 `{continueToken, expiresIn: 600}` | 403 |
| POST | `/api/rooms/{code}/continue` | `{continueToken}` | 200 `{code, token, slot, colour}` | 403 "This continue link is no longer valid", 404 |

Behaviour notes:

- **Join.** A token matching seat A or B returns that seat unchanged. Otherwise, while seat B is free, any join (also from the creator's browser without its token) creates seat B with a new token, marks game 1 `playing`, broadcasts and alerts seat A. With both seats taken it is 409.
- **Moves.** Check order: seat token (403), game playing (409), version equals the game's version (409 with snapshot), seat holds the side to move (403), move legal (400). The board is rebuilt by replaying the stored moves. Automatic ends: checkmate, stalemate, insufficient material, fivefold repetition, 75-move rule. On an end, the room score is updated in the same transaction (by seat, not colour).
- **Check-move.** Same checks under the room lock with a read-only connection; then the copied moves are replayed and `analysis.analyse` runs in a worker thread outside the lock. `warning` is `null`, `{kind: "mate_in_one", move, mate}` or `{kind: "hanging_piece", move, piece, square, capturer: {piece, square}, defended}`.
- **Claim draw.** Only for the seat to move, only when `can_claim_fifty_moves` or `can_claim_threefold_repetition`; result `1/2-1/2`.
- **Claim win.** Only while playing and when the opponent's presence is `abandoned` (not connected and lastSeenAt older than 24 hours).
- **Rematch.** First request records `rematch_requested_by`; the same seat again changes nothing; the other seat's request starts game N+1 with colours flipped, already `playing`. A request bumps the version; a rematch alerts nobody.
- **Continue.** The continue token is valid 10 minutes, once. Redeeming gives the seat a new token, deletes that seat's push subscriptions, tells sockets bound to the old token `seat-moved` (they become watchers), and broadcasts.

### Lessons

| Method | Path | Body | Success | Refusals |
|---|---|---|---|---|
| GET | `/api/lessons` | | 200 `[{id, name, aliases, eco, side, moves}]` sorted by name | 500 when the folder cannot be loaded at all |
| GET | `/api/lessons/{lesson_id}` | | 200 Lesson | 404 "Lesson not found" (malformed or unknown id) |
| POST | `/api/position/move` | `{fen (<= 100), uci (<= 8)}` | 200 `{fen, san, legalMoves, check, outcome}` | 400 "Illegal move" or "Invalid position" |

`outcome` (free play) is `checkmate`, `stalemate`, `insufficient_material`, `seventyfive_moves`, `fifty_moves` (claimable, reported as an outcome here) or `null`. The route is stateless, so it cannot see repetitions.

### Push

| Method | Path | Body | Success | Refusals |
|---|---|---|---|---|
| GET | `/api/push/key` | | 200 `{enabled: true, publicKey}` | 404 `{enabled: false, detail}` when no VAPID key is loaded |
| POST | `/api/rooms/{code}/push/subscribe` | `{token, endpoint, keys: {p256dh, auth}}` | 200 `{ok: true}` | 404 push disabled, 400 "Invalid push subscription", 403 |
| POST | `/api/rooms/{code}/push/unsubscribe` | `{token, endpoint}` | 200 `{ok: true, removed}` | 400 when the endpoint is missing, 403 |

Subscription rules: endpoint `https`, port 443, no user info, plain ASCII host, no IP literal, not `localhost`/`.local`, host on the allow-list (`fcm.googleapis.com`, `*.push.services.mozilla.com`, `*.notify.windows.com`, `web.push.apple.com`, `*.push.apple.com`, plus `JUSTCHESS_PUSH_HOSTS`); `p256dh` a 65-byte P-256 point and `auth` 16 bytes, base64url. Upsert on (room, seat, endpoint); only the 5 newest per seat are kept.

## Response Shapes

**Snapshot** (`games.GameView.snapshot`; WebSocket `state` messages add `"type": "state"`):

```json
{
  "code": "K7Q2PX",
  "game": 1,
  "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
  "turn": "black",
  "status": "playing",
  "endReason": null,
  "result": null,
  "check": false,
  "moveList": [{"number": 1, "white": "e4", "black": null}],
  "lastMove": "e2e4",
  "version": 2,
  "claimableDraw": false,
  "claimableDrawReason": null,
  "seats": {"A": {"presence": "connected", "colour": "white"}, "B": {"presence": "connected", "colour": "black"}},
  "score": {"A": 0, "B": 0, "draws": 0},
  "rematch": {"state": "none", "requestedBy": null},
  "slot": "B",
  "colour": "black",
  "legalMoves": ["g8h6", "g8f6", "..."]
}
```

- `status`: `waiting` | `playing` | `finished`. `endReason`: `checkmate`, `stalemate`, `insufficient_material`, `fivefold_repetition`, `seventyfive_moves`, `threefold_claimed`, `fifty_moves_claimed`, `abandoned`. `result`: `1-0`, `0-1`, `1/2-1/2`.
- `presence`: `empty`, `connected`, `away`, `abandoned`. `rematch.state`: `none`, `pending`, `lapsed` (derived: the other seat is abandoned).
- `slot` and `colour` are the viewer's; `null` for a watcher. `legalMoves` is non-empty only for the seat to move while playing.
- `claimableDrawReason`: `threefold`, `fifty_moves` or `null`.

**Lesson** (`lessons.validate` + `expand`):

```json
{
  "id": "italian", "name": "Italian Game", "aliases": ["Giuoco Piano"], "eco": "C53",
  "side": "white", "start": "startpos", "objectives": ["..."],
  "steps": [{"ply": 0, "side": "white", "san": "e4", "uci": "e2e4", "note": "...",
             "fenBefore": "<FEN>", "legalBefore": ["a2a3", "..."], "alternatives": [{"san": "d4", "note": "..."}],
             "fenAfter": "<FEN>"}]
}
```

**Lesson file schema** (YAML or JSON; file name = id `^[a-z0-9][a-z0-9-]{0,47}$`): `name` (required, <= 80), `side` (required, `white` | `black`), `moves` (required, 1-60 items of `{san (required, legal), uci? (must equal the SAN), note (required, <= 280), alternatives? [{san, note}]}`), `aliases?`, `eco?` (`[A-E][0-9]{2}`), `start?` (`startpos` or a legal FEN), `objectives?`. Unknown fields are refused. Files over 64 KB, symlinks and non-regular files are skipped.

## WebSocket `/ws/{code}`

| Direction | Message | Meaning |
|---|---|---|
| client -> server | `{"type": "hello", "token"?, "visible"}` | Must be first. A matching token binds the socket to that seat; otherwise watcher |
| server -> client | `{"type": "state", ...Snapshot}` | After hello, and after every change, composed per socket |
| client -> server | `{"type": "ping"}` | Every 5 s |
| client -> server | `{"type": "visibility", "visible": bool}` | On change; `false` on `pagehide` |
| server -> client | `{"type": "seat-moved"}` | The seat was continued on another device; this socket is now a watcher |

Close codes: 1008 malformed code, unknown room, cross-origin, or first message not a hello; 1003 not JSON; 1009 message over 1 KB; 1011 database error; 4408 silent for 10 s. The client reconnects after 1, 2, 4, 8 s then every 10 s, and stops on 1008. A seat counts as "fresh visible" (push skipped) only with a visible socket heard from in the last 6 s.

## Data Store

SQLite file from `JUSTCHESS_DB` (default `justchess.sqlite3` in the working directory, git-ignored). Each operation opens a short-lived connection (`isolation_level=None`, `PRAGMA foreign_keys = ON`, 5 s busy timeout); writes use `BEGIN IMMEDIATE`. Schema version 3:

| Table | Key | Columns |
|---|---|---|
| `schema_version` | | `version` |
| `rooms` | `code` (6 chars) | `created_at`, `last_activity_at` (indexed), `wins_a`, `wins_b`, `draws`, `rematch_requested_by` (A/B), `rematch_requested_at` |
| `seats` | `seat_id`; unique (`room_code`, `slot`) | `slot` A/B, `token_hash` (unique), `continue_token_hash`, `continue_expires_at`, `last_seen_at` |
| `games` | `game_id`; unique (`room_code`, `number`) | `white_slot`, `fen` (cache), `version`, `status`, `end_reason`, `result`, `started_at`, `ended_at` |
| `moves` | (`game_id`, `ply`) | `uci`, `san`, `played_at` |
| `push_subscriptions` | `id`; unique (`room_code`, `slot`, `endpoint`) | `p256dh`, `auth`, `created_at`; `ON DELETE CASCADE` from rooms |
| `alert_records` | (`room_code`, `slot`, `event_key`) | `status` (`claimed`, `sent`, `skipped`, `failed`), `created_at`, `updated_at`; cascade |

Startup (`prepare_database`): keep version 3; upgrade version 2 in place in one transaction (adds the two push tables); refuse a newer version; move anything else aside to `<name>.old` and create a fresh schema. Housekeeping deletes rooms whose `last_activity_at` is older than 30 days, at startup and hourly.

There is no table or column for a game mode (online, pass-and-play, against an engine), and no notion of an engine seat.

## Client-Side Contract

What the browser relies on, which any API change must keep or update together:

- Snapshot keys used by `view-model.js`, `screen-state.js`, `live.js`, `notify-core.js`: `code`, `game`, `version`, `fen`, `turn`, `status`, `endReason`, `result`, `check`, `moveList`, `lastMove`, `claimableDraw`, `claimableDrawReason`, `seats[slot].presence/colour`, `score`, `rematch`, `slot`, `colour`, `legalMoves`.
- Seat answer keys `code`, `token`, `slot`, `colour`; stored as `{token, slot}` under `localStorage` key `justchess.seat.<CODE>` (one seat per room per browser).
- Error text from `detail`; a 409 `snapshot` is applied like a move answer; 403 "This isn't your seat" means the stored seat is gone.
- Lesson keys listed above; `trainer-state.js` requires `steps[].fenBefore`, `legalBefore`, `uci`, `san`, `note`, `side`.
- Push payload `{title, body, tag: "<code>:<key>", url: "/r/<code>", code, key}`; the service worker only ever opens `/r/<code>` on its own origin.

## External Calls

- Server: HTTPS GET `https://github.com/official-stockfish/Stockfish/releases/download/sf_19/<asset>` at boot, only when no engine is found and `STOCKFISH_AUTO_INSTALL` is not `0` (60 s, 200 MiB, SHA-256 checked).
- Server: Web Push POSTs to allow-listed push services (pywebpush, no redirects, TTL 3600, 10 s timeout, `Urgency: high`).
- Browser: none to third parties. Fonts, pieces and scripts are same-origin (`static/ASSETS.md`).

## Environment Variables

All may be set in `.env` at the project root (`justchess/envfile.py`); a variable already in the environment wins.

| Variable | Read by | When | Effect |
|---|---|---|---|
| `JUSTCHESS_DB` | `db.resolve_db_path` | import of `app.py` | SQLite path |
| `JUSTCHESS_ORIGIN` | `create_app` -> `OriginGuardMiddleware` | `create_app` (import of `app.py`) | Expected origin |
| `JUSTCHESS_LESSONS_DIR` | `lessons.default_lessons_dir` | `create_app` | Lessons folder (default `<root>/lessons`) |
| `JUSTCHESS_VAPID_PRIVATE_KEY` | `vapid.load_vapid` | lifespan | PEM or raw base64url P-256 key |
| `JUSTCHESS_VAPID_KEY_FILE` | `vapid.load_vapid` | lifespan | PEM file outside the project folder |
| `JUSTCHESS_VAPID_SUBJECT` | `vapid.load_vapid` | lifespan | `mailto:` or `https://` contact (default `mailto:admin@localhost`) |
| `JUSTCHESS_PUSH_HOSTS` | `notifications.allowed_hosts` | lifespan | Extra push hosts, comma-separated, `*.` wildcards |
| `STOCKFISH_PATH` | `stockfish_install.resolve_existing` | boot task | Engine executable |
| `STOCKFISH_AUTO_INSTALL` | `stockfish_install._auto_install_enabled` | boot task | `0` disables the download |
| `JUSTCHESS_CHROMIUM` | tests only (README) | test run | Browser binary for browser tests |
