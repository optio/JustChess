# Developer Code Scan — JustChess

Head commit: `50e87bdd5a4e3ad22903a8d49df32a0718a2853c` (working tree also carries uncommitted `pyproject.toml`, `.gitignore` and untracked `uv.lock` changes; scanned as on disk).

## Developer Code Scan Results

### Scan Coverage
- **Analyzed deeply**:
  - `app.py` (195 lines — the entire backend)
  - `static/app.js` (23 long minified-style lines — the entire frontend controller)
  - `templates/index.html` (single page)
  - `static/style.css` (single line)
  - `pyproject.toml`
  - `README.md`
  - `REQUIREMENTS.md` (the spec under review; read in full for comparison)
  - `.gitignore` (project part; AI-DLC's marked block ignored)
- **Skimmed only**:
  - `uv.lock` (generated lockfile; only resolved versions of direct dependencies and key transitive ones were read)
- **Left out**:
  - `.venv/` (dependency folder)
  - `__pycache__/` (tool cache, gitignored)
  - `justchess.sqlite3` (local database file, gitignored)
  - `.git/`
  - `.claude/`, `.mcp.json` AI-DLC servers, `aidlc/` workspace (AI-DLC install, not project code)

### Packages Found
- `justchess` (root, `[tool.uv] package = false`) — application (not an installable package) — Python 3.11+ — FastAPI web app for anonymous two-player chess plus opening lessons
- Frontend (`templates/`, `static/`) — server-rendered HTML + vanilla JS + CSS — single-page UI

### Build System
- **Type**: uv (PEP 621 `pyproject.toml`, `uv.lock` lockfile version 1); no build backend, no Dockerfile, no Makefile
- **Config Files**: `pyproject.toml`, `uv.lock`
- **Build Dependencies**: none between internal packages (single module `app.py`); run command per README: `uv run uvicorn app:app --reload`

### APIs Discovered
- REST (FastAPI) — `app.py` — 7 HTTP routes: `GET /`, `POST /api/games`, `POST /api/games/{code}/join`, `GET /api/games/{code}`, `POST /api/games/{code}/moves`, `GET /api/lessons`, `GET /api/lessons/{lesson_id}`
- WebSocket — `app.py:178` — 1 endpoint: `/ws/{code}` (server-push `state` snapshots; inbound messages ignored)
- Static mount — `app.py:47` — `/static`
- Browser APIs used by client — `static/app.js`: `fetch`, `WebSocket`, `sessionStorage`, `Notification`, `navigator.clipboard`, `prompt`

### Frameworks & Libraries
- FastAPI — `>=0.115,<1` (locked 0.162.4) — HTTP/WebSocket framework (Starlette 1.10.0, Pydantic 2.14.3 transitive)
- Uvicorn — `>=0.30,<1` (locked 0.54.0) — ASGI server
- Jinja2 — `>=3.1,<4` (locked 3.1.6) — renders `templates/index.html` (no template variables used)
- python-chess — `>=1.999` (locked 1.999 shim -> `chess` 1.11.2) — authoritative move legality, SAN, outcomes
- python-multipart — `>=0.0.9` (locked 0.0.33) — declared but no form endpoints use it
- HTMX — 2.0.4 via unpkg `<script>` — loaded but NO `hx-*` attributes anywhere (unused)
- Dev: pytest `>=8,<10` (locked 9.2.0), httpx `>=0.27,<1` (locked 0.28.1) — declared, no tests exist
- Standard library: `sqlite3`, `asyncio`, `secrets`, `json`

### Test Coverage
- **Test Directories**: none
- **Test Frameworks**: pytest + httpx declared in `[dependency-groups] dev`; zero test files
- **Coverage Config**: absent

### Code Quality Indicators
- **Linting**: none configured (no ruff/black/flake8 config in `pyproject.toml`, no `.editorconfig`); `.gitignore` mentions `.ruff_cache/` only as a template entry
- **CI/CD**: none (no `.github/`, no pipeline files)
- **Documentation**: README accurate about prototype status and limits; no docstrings or comments in `app.py`; `static/app.js` written in dense one-statement-per-line style that is hard to read

### Technical Debt Signals
- HTMX script loaded but unused (`templates/index.html:5`); REQUIREMENTS.md §2 and README claim HTMX is part of the stack
- Unused import `JSONResponse` (`app.py:11`); unused dependency `python-multipart`
- `with connect() as db` commits but never closes SQLite connections (`app.py:37,60,94,116,152`)
- In-process state: `rooms` and `locks` dicts grow unbounded and never shrink (`app.py:17-18,108,130`); per-room `asyncio.Lock` only works with one worker
- Relative paths `justchess.sqlite3`, `templates`, `static` depend on the working directory (`app.py:16,19,47`)
- Player tokens stored in plaintext in `games.white`/`games.black` (`app.py:98,117`); spec §7 suggests hashing
- `board.outcome(claim_draw=True)` computed twice in `snapshot` (`app.py:73`) and used in `move` (`app.py:148`): claimable draws (threefold repetition, 50-move) end the game automatically instead of being claimed
- Scoreboard counts only wins (`white_score`/`black_score`); no draws/losses, and with no rematch flow each room plays one game, so scores never exceed 1 (`app.py:150-151`)
- Lessons hard-coded in `LESSONS` dict (`app.py:21-26`), not YAML/JSON files
- Board square colouring inverted: `(x+y)%2===0` marks a1 light and h1 dark (`static/app.js:6`)
- Board never flipped for Black (`static/app.js:6`, loop ranks 8->1 always)
- `game.check` returned by API but never shown in the UI (`static/app.js:7`)
- Promotion uses blocking `prompt()` (`static/app.js:7`)
- WebSocket endpoint has no Origin check and no token; anyone with the code receives live state (`app.py:178-195`)
- No rate limiting, request bounds, room expiry/cleanup, logging, or health endpoint
- No tests, no CI, no linter, no Dockerfile

## Handoff Summary
- **Intent-relevant finding**: REQUIREMENTS.md keeps every requirement as unchecked `[ ]` even though a subset is implemented. Implemented: 6-char room codes from `secrets` with PK-retry (`app.py:90-102`); private 24-byte tokens distinct from code, rejoin via sessionStorage (`app.py:105-119`, `static/app.js:13,19`); third player rejected 409 (`app.py:113-114`); server-side legality incl. castling/en passant/promotion via python-chess (`app.py:127-156`); click-to-move with legal highlights (`static/app.js:7`); WebSocket sync + snapshot on connect + client auto-reconnect (`app.py:178-195`, `static/app.js:8`); SAN history, turn and finished status (`static/app.js:7`); win-only scoreboard; `games` table only (`app.py:38-42`); two linear lessons (Italian, Monte Carlo) with walkthrough back/next/restart and practice (`app.py:21-26,159-175`, `static/app.js:20-23`); open-page Notification API alerts on opponent join/move (`static/app.js:8,10`). Not implemented: HTMX usage, join-by-URL, disconnected/presence status, check display, draw claims, losses/draws scoreboard, resignation/draw offers/rematch/abandonment, version-checked moves, room expiry, `game_players`/`moves`/`results`/`push_subscriptions` tables, token hashing, board flip/keyboard/a11y beyond aria-labels, drag-and-drop, Web Push/service worker, branching lessons, scripted opponent replies in practice (user must play both sides), legal-vs-off-repertoire distinction, transpositions, YAML/JSON lesson files, other catalog openings, rate limits, WS Origin check, retention/observability, Docker, tests.
- **Risks / follow-up**: The spec mixes delivered, planned and aspirational items without status; the requirements analysis must split them. Spec contradictions to surface: §2 HTMX vs actual vanilla JS; §2 per-room data in SQLite "rooms, player identities, moves and results" vs single `games` table; §3 "support claiming a draw" vs automatic claim in code; §1 "scripted opponent moves" vs practice mode that has none. Known UI bug (inverted square colours) should not be mistaken for a requirement gap. README states single Uvicorn worker is required.
