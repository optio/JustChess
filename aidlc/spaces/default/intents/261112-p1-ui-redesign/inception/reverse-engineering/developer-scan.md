# Developer Code Scan: JustChess

Full rescan of the whole repository at Standard depth. Snapshot head commit `50e87bdd5a4e3ad22903a8d49df32a0718a2853c`. The working tree has uncommitted changes (`app.py`, `README.md`, `pyproject.toml`, `.gitignore` modified; `REQUIREMENTS.md` deleted; `stockfish_install.py`, `tests/` and `uv.lock` untracked). Every file was scanned as it is on disk, not as committed. Nothing was run: no tests, builds or programs.

## Developer Code Scan Results

### Scan Coverage
- **Analyzed deeply**:
  - `app.py`
  - `stockfish_install.py`
  - `templates/index.html`
  - `static/app.js`
  - `static/style.css`
  - `tests/test_stockfish_install.py`
  - `pyproject.toml`
  - `README.md`
  - `.gitignore` (the project's own part, outside the AI-DLC marked block)
- **Skimmed only**:
  - `uv.lock`: header fields and the resolved versions of direct and key transitive packages only
- **Left out**:
  - `.venv/` (dependencies)
  - `__pycache__/` and `tests/__pycache__/` (bytecode caches)
  - `.pytest_cache/` (tool cache)
  - `.engines/` (downloaded Stockfish binary, git-ignored)
  - `justchess.sqlite3` (local database, git-ignored)
  - `.git/`
  - AI-DLC's own install: `.claude/`, `aidlc/` workspace, `.mcp.json`, the AI-DLC block in `.gitignore`

### Packages Found
- `justchess` (root, `[tool.uv] package = false`): application, Python, an anonymous two-player chess and opening-training web app
- `app` module (`app.py`, 220 lines): FastAPI app with all HTTP and WebSocket routes, the SQLite schema and access, in-code lesson data and the engine status route
- `stockfish_install` module (`stockfish_install.py`, 273 lines): standard-library-only finder and installer for a pinned, SHA-256-verified Stockfish `sf_19` binary
- Frontend (no package): `templates/index.html` (one Jinja2 page, 29 lines), `static/app.js` (24 very long minified-style lines of vanilla JS), `static/style.css` (one minified line)
- `tests` (`tests/test_stockfish_install.py`, 8 pytest tests)

### Build System
- **Type**: uv (PEP 621 `pyproject.toml`, lockfile `uv.lock` version 1 revision 3, `requires-python >=3.11`). No build backend: `package = false`, so the project is run from source.
- **Config Files**: `pyproject.toml` (dependencies, `dev` dependency group, `[tool.pytest.ini_options]` with `testpaths = ["tests"]`, `pythonpath = ["."]`), `uv.lock`
- **Build Dependencies**: `app` imports `stockfish_install`; `tests/test_stockfish_install.py` imports `stockfish_install` and, in one test, `app`. No circular imports. Run command (README): `uv run uvicorn app:app --reload`.

### APIs Discovered
- REST (FastAPI) in `app.py`: 8 HTTP routes
  - `GET /` (HTML page)
  - `POST /api/games`, `POST /api/games/{code}/join`, `GET /api/games/{code}`, `POST /api/games/{code}/moves`
  - `GET /api/lessons`, `GET /api/lessons/{lesson_id}`
  - `GET /api/engine` (new: engine availability, source and version; never the path)
- WebSocket in `app.py`: 1 endpoint, `/ws/{code}` (server push of full `state` snapshots; inbound text is read and ignored)
- Static mount: `/static` serves `static/`
- Browser APIs used by the frontend: `fetch`, `WebSocket`, `sessionStorage` (key `justchess`), `Notification`, `navigator.clipboard`, `prompt`, `alert`
- External network (server side): HTTPS download from `github.com/official-stockfish/Stockfish/releases/download/sf_19/`
- External network (browser): `https://unpkg.com/htmx.org@2.0.4` script tag (loaded, never used)

### Frameworks & Libraries
Declared range in `pyproject.toml`, resolved version from `uv.lock`:
- FastAPI `>=0.115,<1` (with `[standard]`), resolved 0.162.4: web framework, routing, validation, WebSocket
- Starlette 1.10.0 (transitive): ASGI toolkit, `StaticFiles`, `TestClient`
- Pydantic 2.14.3 (transitive): request bodies `Join`, `Move`
- Uvicorn `>=0.30,<1` (with `[standard]`), resolved 0.54.0: ASGI server
- websockets 17.4 (transitive via uvicorn standard): WebSocket protocol
- Jinja2 `>=3.1,<4`, resolved 3.1.6: page template
- python-chess `>=1.999`, resolved 1.999: a shim that installs `chess` 1.11.2, the actual rules library
- python-multipart `>=0.0.9`, resolved 0.0.33: declared but not used (no form endpoints)
- pytest `>=8,<10` (dev), resolved 9.2.0
- httpx `>=0.27,<1` (dev), resolved 0.28.1: needed by `fastapi.testclient`
- HTMX 2.0.4 (CDN, frontend): loaded, no `hx-*` attribute anywhere; the requirements' constraints say it is to be removed
- Stockfish `sf_19` (external binary, GPLv3): installed at runtime, not used by any feature yet

### Test Coverage
- **Test Directories**: `tests/`
- **Test Frameworks**: pytest (fixtures `tmp_path`, `monkeypatch`), FastAPI `TestClient`
- **Coverage Config**: absent (no pytest-cov, no `.coveragerc`)
- **What is tested**: the installer's resolution order (env, PATH, cached), stale leftover cleanup, download with checksum pass and fail, unsafe tar members and links, auto-install off and unsupported platform, and `GET /api/engine` with a patched installer (the DB is redirected to `tmp_path`).
- **What is not tested**: rooms, joining, seat tokens, move validation, game end, scores, lessons, WebSocket broadcast, and all frontend code.

### Code Quality Indicators
- **Linting**: none configured (no Ruff, Flake8, Black, mypy, ESLint or Prettier config; no `[tool.*]` lint sections)
- **CI/CD**: none (no `.github/`, no pipeline files, no Dockerfile)
- **Documentation**: `README.md` is accurate to the code (getting started with uv, implemented features, Stockfish behaviour and licence, limitations). `stockfish_install.py` has a module docstring and docstrings on public functions. `app.py` has one comment and no docstrings. `static/app.js` and `static/style.css` are written as dense one-line blocks with no comments.

### Technical Debt Signals
- `static/app.js` lines 6, 7, 8 and 17: whole functions on single lines (rendering, game click handling, socket handling, training), global mutable state on line 3. Hard to read, diff or test.
- `static/style.css` line 1: the whole stylesheet on one line; no custom properties, no media queries, no focus styles, no transitions.
- `static/app.js` line 6: board colouring is inverted. `dark` is applied when `(x + y) % 2 === 0` with `x` 0-based file and `y` 1-based rank, so a1 renders light (FR5.1 fails). The loop always draws rank 8 at the top, so Black sees the board from White's side (FR5.2).
- `static/app.js` line 7: promotion uses `prompt()`; line 19 shows lesson errors with `alert()`; line 11 uses `alert()` when notifications are unavailable.
- `static/app.js` line 8: the notification text is "Your move!" when the creator's opponent joins (it checks whose turn it is, not what happened); game end produces no alert.
- `static/app.js` line 12: "Copy code" copies only the code, not a link, with no confirmation.
- `templates/index.html` line 22: lesson options are hardcoded and duplicate the `LESSONS` dict; `GET /api/lessons` is never called by the client.
- `templates/index.html` line 6: unused HTMX script from a CDN.
- `app.py` lines 35-38 and every `with connect() as db`: the `sqlite3` context manager commits but does not close; connections are left to garbage collection.
- `app.py` line 20: `DB = Path("justchess.sqlite3")` and lines 25 and 63 (`templates`, `static`) depend on the working directory (the test has to `chdir`).
- `app.py` lines 23-24: `rooms` and `locks` dicts grow forever and are per process (one Uvicorn worker only).
- `app.py` line 89: `board.outcome(claim_draw=True)` is computed twice, returns only the result string (no reason), and ends games automatically on threefold repetition and the 50-move rule, where FR4.3 wants a claim.
- `app.py` lines 44-48: the schema stores seat tokens in plaintext (NFR2), has no version, timestamps or end reason, and keeps one game per room, so scores cannot exceed 1.
- `app.py` lines 27-32: lessons hardcoded in Python (FR7.6).
- `app.py` lines 49-51: the Stockfish task is not cancelled or awaited on shutdown.
- `app.py` lines 94-98: broadcast send failures are dropped silently (no log).
- `pyproject.toml`: `python-multipart` is unused, and `jinja2`, `uvicorn[standard]` and `python-multipart` are already pulled in by `fastapi[standard]`; `python-chess` is a shim for `chess`.
- No TODO, FIXME, HACK or `noqa` markers anywhere in the source.

## Handoff Summary
- **Intent-relevant finding**: The whole UI is one page of three stacked, identical rounded cards (`templates/index.html` lines 12-26) styled by a one-line stylesheet with a single dark-green palette and one beige accent applied to every control (`static/style.css` line 1: `#14241f` background, `#20372f` panels, `#f0d7a2` for the title and all buttons, inputs and selects; `system-ui` font; centred header with a "♞" glyph and tagline). There is no visual hierarchy between primary and secondary actions, no layout change during a game (the lessons card stays fully open below it), and the board is a 480 px maximum grid inside a padded card. The board itself has the inverted square colours, fixed White orientation and no coordinate labels (`static/app.js` line 6). All rendering is imperative DOM rebuilding in `static/app.js` with no module structure, which a redesign will have to restructure rather than restyle.
- **Risks / follow-up**:
  - The client depends on the exact snapshot keys (`fen`, `turn`, `status`, `moves`, `legal`, `white_score`, `black_score`, `check`, `outcome`) and on the `sessionStorage` key `justchess`; changes to `snapshot()` in `app.py` lines 83-89 must keep the frontend in step.
  - P1 data-model changes (versions, hashed tokens, several games per room, end reasons) touch the `games` table created in `app.py` lines 44-48, and there is no migration mechanism; existing local databases would need one.
  - Only the Stockfish installer and `GET /api/engine` have tests; any refactor of `app.py` or `static/app.js` has no regression safety net today.
  - The test for `/api/engine` imports `app` after `chdir` and redirects `DB`; new app-level tests should follow the same isolation so they never touch `justchess.sqlite3`.
