# Developer Code Scan: JustChess (focused, intent 261113-p2-features)

Focused scan at Standard depth over the snapshot paths named in the brief. Files were read as they are on disk at head commit `50e87bdd5a4e3ad22903a8d49df32a0718a2853c`; almost everything in scope is uncommitted (the `justchess/` package, `static/js/`, `static/css/`, `static/sw.js`, `lessons/` and `stockfish_install.py` are untracked; `app.py` and `templates/index.html` are modified). No tests, builds or programs were run.

## Developer Code Scan Results

### Scan Coverage
- **Analyzed deeply**:
  - `app.py`
  - `stockfish_install.py`
  - `justchess/` (all 13 modules: `__init__`, `api`, `rooms`, `games`, `live`, `db`, `housekeeping`, `security`, `analysis`, `lessons`, `notifications`, `vapid`, `envfile`)
  - `static/js/` (24 top-level and sub-folder modules: `app`, `boot`, `api`, `live`, `hooks`, `room-flow`, `screen-state`, `view-model`, `seat-store`, `share`, `settings`, `settings-panel`, `blunder`, `notifications`, `notify-core`, `contrast`, `board/*`, `screens/*`, `training/*`)
  - `static/css/` (`tokens.css`, `base.css`, `board.css`, `app.css`, `training.css`; layout and motion rules read in full, colour token values sampled)
  - `static/sw.js`
  - `templates/` (`index.html`)
  - `lessons/` (`italian.yaml`, `monte-carlo.yaml`)
- **Skimmed only**:
  - `tests/` (file list, fixtures in `tests/core/conftest.py`, the JS runner `tests/js/index.js`; test bodies not read)
  - `pyproject.toml`
  - `README.md`
  - `uv.lock` (searched for `python-dotenv` only)
  - `static/demo/`, `static/ASSETS.md`, `static/logo.svg` (outside the snapshot paths; noted only)
  - `static/fonts/`, `static/pieces/` (binary assets; file names listed only)
- **Left out**:
  - `.venv/`
  - `__pycache__/` (every package folder)
  - `.pytest_cache/`
  - `.engines/`
  - `.git/`
  - `justchess.sqlite3`, `justchess.sqlite3.old` (local data, git-ignored)
  - `.env` (git-ignored, may hold secrets; its existence noted, contents not opened), `.env.example` (outside the brief's paths; existence noted)
  - AI-DLC's own install: `.claude/`, `aidlc/`, `.mcp.json`, the AI-DLC block of `.gitignore`

### Packages Found
- `justchess` — Python package (not installable, `package = false`) — Python — backend: one module per component (rooms, games, live socket hub, persistence, housekeeping, security middleware, blunder analysis, lessons, notifications, VAPID keys, `.env` loader, HTTP routes and app factory)
- `app` (`app.py`) — ASGI entry module — Python — loads `.env`, resolves `DB` and `ENGINE_DIR`, builds `app = create_app(...)`
- `stockfish_install` (`stockfish_install.py`) — standalone module — Python (standard library only) — finds or installs a pinned, checksum-verified Stockfish `sf_19`
- `static/js` — browser ES modules, no build step — JavaScript — app shell and router, HTTP and socket clients, pure state machines and view model, board component, screens, blunder UI, notifications client, opening trainer
- `static/css` — plain CSS — "Club Set" design tokens, base, board, app layout, trainer
- `static/sw.js` — classic service worker — JavaScript — Web Push display and notification click
- `templates/index.html` — Jinja2 page shell (no template logic) — HTML
- `lessons/` — data — YAML — two opening lessons loaded at runtime

### Build System
- **Type**: uv (`[tool.uv] package = false`); no JS bundler, no CSS build; Node 24 built-in test runner for JS tests
- **Config Files**: `pyproject.toml`, `uv.lock`, `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `pythonpath = ["."]`)
- **Build Dependencies**: `app.py` -> `justchess.envfile`, `stockfish_install`, `justchess.api`, `justchess.db`; `justchess.api` -> every other `justchess` module plus `stockfish_install`; `templates/index.html` -> `static/js/boot.js`, `static/css/*.css`, `static/js/app.js` (module graph from there)

### APIs Discovered
- REST (FastAPI) — `justchess/api.py` — 23 HTTP routes: 4 page routes (`/`, `/r/{code}`, `/learn`, `/learn/{lesson_id}`), `GET /sw.js`, `GET /api/engine`, 3 lesson routes (`GET /api/lessons`, `GET /api/lessons/{id}`, `POST /api/position/move`), 10 room/game routes under `/api/rooms`, 3 push routes (`GET /api/push/key`, `POST .../push/subscribe`, `POST .../push/unsubscribe`), plus the `/static` mount
- WebSocket — `justchess/api.py` `/ws/{code}` served by `justchess/live.py` `LiveHub` — hello/state/ping/visibility/seat-moved protocol
- Browser clients — `static/js/api.js` (rooms), `static/js/training/lessons-api.js` (lessons), `static/js/live.js` (socket), `static/js/notifications.js` (push key and subscriptions)
- Outbound — `stockfish_install.download` (GitHub releases, HTTPS), `notifications.WebPushSender` (pywebpush to allow-listed push services)

### Frameworks & Libraries
- FastAPI (`[standard]`) — `>=0.115,<1` — routing, validation, WebSocket, templates, static files
- Uvicorn (`[standard]`) — `>=0.30,<1` — ASGI server
- Jinja2 — `>=3.1,<4` — page shell
- python-chess — `>=1.999` (shim for `chess`) — rules, SAN/UCI, FEN, outcomes, analysis
- PyYAML — `>=6.0.3` — `yaml.safe_load` for lessons
- pywebpush — `>=2.5.0` — Web Push sends (brings `py_vapid`, `cryptography`, `requests`)
- python-multipart — `>=0.0.9` — declared, unused
- Browser: vanilla ES modules, Web Animations API, Service Worker, Push API, Notification API, `navigator.share`, Clipboard API
- Exact resolved versions are in `uv.lock` (not re-read this run; the prior store's table is kept in `technology-stack.md`)

### Test Coverage
- **Test Directories**: `tests/` (12 Python files at top level), `tests/core/` (U1 backend: rooms, games, live, db, api), `tests/js/` (19 `*.test.mjs` files plus `index.js`)
- **Test Frameworks**: pytest with FastAPI `TestClient` (httpx); Node 24 `node:test`; a headless Chromium run in `tests/test_game_screen.py` and `tests/test_accessibility_browser.py`, skipped when no browser is found; `tests/test_frontend_js.py` runs the Node suite from pytest
- **Coverage Config**: absent (no coverage tool configured). About 153 Python test functions and about 139 JS `test(...)` calls by name count; a new `tests/test_envfile.py` appeared during this scan

### Code Quality Indicators
- **Linting**: no linter or formatter configured in the repository; `# noqa` markers in `app.py` and `justchess/notifications.py` show Ruff-style codes are expected (a `ruff` binary exists on this machine but no `[tool.ruff]` config)
- **CI/CD**: none (no `.github/`, no pipeline file, no Dockerfile)
- **Documentation**: every module has a header docstring or block comment naming its unit and business rules; `README.md` is current (configuration table, lessons schema, Stockfish, design system); `static/ASSETS.md` pins third-party assets with sha256

### Technical Debt Signals
- Board size is driven by width only; no rule caps it by viewport height (`static/css/app.css` breakpoints: phone = viewport width, tablet <= 640 px, desktop 560-640 px column), so on short screens the board and the status below it can fall under the fold
- The mover's own captures are never animated: `board.js` applies the move optimistically (`applyOptimistic` removes the captured piece at once) and the confirming position then equals what is shown, so `interaction.js` `onPosition` passes `animation: null`; only the opponent's captures get the 150 ms `fadeCaptured`
- End-reason wording is duplicated in four places (`justchess/notifications.py` `END_TITLES`, `static/js/view-model.js` `END_TITLES`, `static/js/notify-core.js` `END_TEXT`, and the copy inside `static/sw.js`); only the `notify-core`/`sw.js` pair is pinned equal by a test
- `justchess/api.py` is 714 lines holding the app factory, `Services`, request models and all route groups
- In-memory room locks (`weakref.WeakValueDictionary`) and the `LiveHub` socket registry tie the app to one process
- `seat-store.js` keeps one seat per room code; there is no index of rooms a browser holds, and no server route that answers for several rooms at once
- Lesson `alternatives` are shown as text only; in practice mode an alternative is treated as "Legal, but not this line" (`trainer-state.js` `onLearnerMove`)
- `python-multipart` is unused; `uvicorn[standard]` and `jinja2` are already brought by `fastapi[standard]`; `python-chess` is a shim for `chess`
- Source files in scope changed during the scan (`app.py`, `justchess/envfile.py`, `justchess/vapid.py`, `tests/test_envfile.py` between 14:59 and 15:01 local time), so someone is editing this area concurrently
- No TODO, FIXME or HACK markers in the analyzed source

## Handoff Summary
- **Intent-relevant finding**: The nine upcoming features land on these seams. (1) Ongoing-games list: seats live only in the browser under `localStorage` keys `justchess.seat.<CODE>` (`static/js/seat-store.js` `KEY_PREFIX`), the lobby (`static/js/screens/lobby.js`) shows none, and the only per-room read is `GET /api/rooms/{code}` with `X-Seat-Token` (`justchess/api.py` `room_state`). (2) Capture animation: `static/js/board/board.js` `fadeCaptured` (tokens `--t-capture: 150ms`, `--capture-drop: 6px` in `static/css/tokens.css`), skipped for the mover's own captures as described above. (3) Pass-and-play: the server enforces two token-bound seats and turn by slot (`justchess/games.py` `_require_turn`, `require_move_turn`; `justchess/rooms.py` `join_room` gives seat B to any tokenless join), legal moves go only to the seat to move (`GameView.snapshot`), and there is no route to release a seat. (4) Board above the fold: `static/css/app.css` sizes by width only. (5) Share modal: `static/js/share.js` (share sheet, then clipboard, then the `#share-fallback` field in `templates/index.html`); the only modal pattern is `static/js/screens/blunder-dialog.js`. (6) Stockfish: only discovery and install exist (`stockfish_install.ensure_stockfish`, result on `app.state.stockfish`, `GET /api/engine`); no UCI process wrapper, and analysis uses python-chess alone. (7, 8) Lessons and situation trainers: dropping a YAML or JSON file adds a lesson (`justchess/lessons.py`), the schema already accepts `start: <FEN>`, the trainer is a linear line with scripted replies, and free play uses the stateless `POST /api/position/move`. (9) `.env`: `justchess/envfile.py` (new, a hand-written parser, no python-dotenv) is called at the top of `app.py` before any other import, so `JUSTCHESS_DB` (read at import in `app.py`), `JUSTCHESS_ORIGIN` and `JUSTCHESS_LESSONS_DIR` (read in `create_app` at import), VAPID and push hosts (read in the lifespan) and `STOCKFISH_*` (read in the boot task) all see it.
- **Risks / follow-up**: (a) The `.env` item appears already implemented in the uncommitted working tree, and the files changed while this scan ran; the source fingerprint may not match at publish, and the requirements stage should confirm what is left of that item. (b) The single-process constraint (in-memory locks and socket hub) bounds any Stockfish design: engine work must not block the event loop (the blunder check already uses `asyncio.to_thread`), and Stockfish is GPLv3. (c) Pass-and-play "and back" needs either a seat-release route or a client-side mode; both touch `rooms.py`, `seat-store.js`, `view-model.js` (orientation follows the viewer's colour) and notifications (alerts assume the other seat is another device). (d) `tests/` was not deeply analyzed this run; its prior deep coverage is not re-verified.
