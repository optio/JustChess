# Technology Stack: JustChess

## Languages

| Language | Where | Version / notes |
|---|---|---|
| Python | `app.py`, `stockfish_install.py`, `justchess/`, `tests/` | `requires-python >=3.11` (`pyproject.toml`). Uses `X | None` unions, `from __future__ import annotations`, dataclasses, `functools.cached_property`, `asyncio.to_thread`. Local bytecode caches suggest CPython 3.14 (file names only, prior run). |
| JavaScript | `static/js/`, `static/sw.js` | Native ES modules in the browser (`<script type="module">`), plus two classic scripts (`boot.js`, `sw.js`). Modern syntax (optional chaining, `Object.hasOwn`, private-free closures). No transpiler, bundler or npm dependency. |
| HTML | `templates/index.html` | HTML5 shell rendered through Jinja2 with no template logic |
| CSS | `static/css/` | Plain CSS with custom properties (tokens), grid, `aspect-ratio`, `color-mix`, media queries for width, `prefers-color-scheme` and `prefers-reduced-motion`. No preprocessor. |
| SQL | inline in `justchess/*.py` | SQLite dialect, parameterised everywhere |
| YAML / JSON | `lessons/` | Lesson data |

## Backend

| Component | Declared (`pyproject.toml`) | Resolved (`uv.lock`, prior run) | Role |
|---|---|---|---|
| FastAPI (`[standard]`) | `>=0.115,<1` | 0.162.4 | Routing, validation, WebSocket, templates, static files, background tasks |
| Starlette | transitive | 1.10.0 | ASGI toolkit; `security.py` and `live.py` use its types directly |
| Pydantic | transitive | 2.14.3 | Request models |
| Uvicorn (`[standard]`) | `>=0.30,<1` | 0.54.0 | ASGI server, one worker |
| websockets | transitive | 17.4 | WebSocket protocol for Uvicorn |
| Jinja2 | `>=3.1,<4` | 3.1.6 | Page shell |
| python-chess | `>=1.999` | 1.999 (shim) | Installs `chess` |
| chess | transitive | 1.11.2 | Rules, SAN/UCI, FEN, outcomes, repetition, analysis; also ships `chess.engine` (UCI), unused so far |
| PyYAML | `>=6.0.3` | not re-read | `yaml.safe_load` for lessons |
| pywebpush | `>=2.5.0` | not re-read | Web Push encryption and send |
| py_vapid, cryptography, requests | transitive (pywebpush) | not re-read | VAPID signing, P-256 key checks, HTTP session without redirects |
| python-multipart | `>=0.0.9` | 0.0.33 | Declared, unused |
| python-dotenv | transitive only (`uv.lock`) | 1.2.4 | Not imported; `.env` is parsed by `justchess/envfile.py` |
| SQLite (`sqlite3`) | standard library | | Persistence, schema version 3 |

The resolved column is kept from the prior run's reading of `uv.lock`; this run only searched the lockfile for `python-dotenv`. Versions marked "not re-read" were added to `pyproject.toml` after that reading.

## Frontend

| Component | Version | Role |
|---|---|---|
| Browser ES modules | | Router, clients, state machines, views; no framework |
| Web Animations API | | Piece slides, capture fade, check pulse, win sequence |
| WebSocket | | Live room updates |
| Service Worker, Push API, Notification API | | Notifications when the tab is hidden or closed |
| `navigator.share`, Clipboard API | | Invite and result sharing |
| `localStorage` / `sessionStorage` | | Seats (`justchess.seat.<CODE>`), settings (`justchess.settings.v1`), shown alert keys (`justchess.notify.shown.v1`) |
| cburnett SVG pieces | pinned, sha256 in `static/ASSETS.md` | CC BY-SA 3.0 (Lichess copy lists GPLv2+) |
| Fonts | `@fontsource` 5.3.0 files | Libre Caslon Display, Libre Caslon Text, Atkinson Hyperlegible (OFL 1.1), self-hosted woff2 |

No CDN scripts, CSS frameworks, icon sets or web app manifest. The former HTMX script tag is gone.

## External Runtime Component

| Component | Version | Role |
|---|---|---|
| Stockfish | `sf_19` official universal builds (Linux arm64, Linux x86-64, macOS), SHA-256 pinned | Installed at boot into `.engines/stockfish-sf_19/` when not found; not used by any feature. GPLv3. |

## Tooling

| Tool | Version | Role |
|---|---|---|
| uv | lockfile version 1 | Dependencies and runner; `package = false` |
| pytest | `>=8,<10` (dev group) | Python tests; `testpaths = ["tests"]`, `pythonpath = ["."]` |
| httpx | `>=0.27,<1` (dev group) | FastAPI `TestClient` |
| Node.js | 24 (README) | `node --test tests/js/` |
| Headless Chromium | optional (`JUSTCHESS_CHROMIUM`) | Browser tests; skipped when missing |

Not present: formatter or linter configuration, type checker, coverage tool, CI pipeline, Dockerfile. Source carries Ruff-style `# noqa` codes, but there is no `[tool.ruff]` section.

## Runtime and Deployment

- One process, one Uvicorn worker (in-memory room locks and socket hub).
- Run from the project root: `ROOT` for `templates/`, `static/` and `lessons/` is resolved from the package location, but the default database path `justchess.sqlite3` is relative to the working directory unless `JUSTCHESS_DB` is set.
- `.env` at the project root is loaded by `app.py` before anything else; shell variables win.
- No container and no HTTPS termination in the app; Web Push beyond `localhost` needs HTTPS hosting.
- Workspace platform: Linux aarch64 (Raspberry Pi kernel), which has a pinned Stockfish build. Engine work on this hardware should be bounded by time or depth.
