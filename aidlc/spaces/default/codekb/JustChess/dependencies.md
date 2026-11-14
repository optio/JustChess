# Dependencies: JustChess

Versions are owned by `technology-stack.md`; this file covers what depends on what and the risks.

## Direct Runtime Dependencies (`pyproject.toml`)

| Package | Used by | Actually needed? |
|---|---|---|
| `fastapi[standard]` | `justchess/api.py` | Yes. The `standard` extra already brings Uvicorn (standard), Jinja2, python-multipart, httpx and the FastAPI CLI. |
| `uvicorn[standard]` | run command | Yes, but redundant with `fastapi[standard]` |
| `jinja2` | `Jinja2Templates` | Yes, but redundant with `fastapi[standard]` |
| `python-chess` | `import chess` in `games`, `analysis`, `lessons`, `api` | The import is satisfied by `chess`; `python-chess` 1.999 is a shim. Depending on `chess` directly would be clearer. |
| `python-multipart` | nothing | No form or file endpoints |
| `pyyaml` | `justchess/lessons.py` | Yes (`yaml.safe_load`) |
| `pywebpush` | `justchess/notifications.py` (and `py_vapid`, `cryptography`, `requests` through it, imported directly by `notifications.py` and `vapid.py`) | Yes; the three transitive packages are imported directly but not declared |

## Development Dependencies (`[dependency-groups] dev`)

| Package | Used by |
|---|---|
| `pytest` | all Python tests |
| `httpx` | `fastapi.testclient.TestClient` |

## Standard Library (notable)

- `justchess`: `asyncio`, `sqlite3`, `hashlib`, `hmac`, `secrets`, `weakref`, `threading`, `ipaddress`, `urllib.parse`, `base64`, `json`, `re`, `stat`, `os`, `logging`, `dataclasses`, `functools`.
- `stockfish_install.py`: `hashlib`, `tarfile`, `tempfile`, `urllib.request`, `shutil`, `platform`, `stat`, `time`; no third-party packages by design.

## Frontend Dependencies

None from third parties at runtime. Every script, stylesheet, font and piece is served from `/static/` (pinned and hashed in `static/ASSETS.md`, checked by `tests/js/assets.test.mjs`).

## External Services

| Service | When | Failure handling |
|---|---|---|
| GitHub releases (`official-stockfish/Stockfish`, tag `sf_19`) | At boot, only when no engine is found and auto-install is on | Logged; the app runs without an engine |
| Push services (FCM, Mozilla, Windows, Apple, plus `JUSTCHESS_PUSH_HOSTS`) | After a join, move or claim, when VAPID keys are loaded and the seat subscribed | 404/410 or key mismatch deletes the endpoint; other failures are logged and the alert is marked failed; no retries |

## Internal Dependency Graph

```
app.py                     -> justchess.envfile, stockfish_install, justchess.api, justchess.db
justchess.api              -> justchess (DomainError), analysis, games, housekeeping, lessons, notifications, rooms,
                              vapid, db, live, security, stockfish_install, chess, fastapi, pydantic
justchess.housekeeping     -> games, rooms, db
justchess.notifications    -> justchess (DomainError), games, rooms, db, vapid, pywebpush, requests, cryptography
justchess.rooms            -> justchess (DomainError)
justchess.games            -> justchess (DomainError), chess
justchess.live             -> justchess (DomainError), starlette
justchess.analysis         -> chess
justchess.lessons          -> chess, yaml
justchess.vapid            -> cryptography, py_vapid
justchess.db, security, envfile -> standard library (security: starlette types)

templates/index.html       -> static/js/boot.js, static/css/{tokens,base,board,app,training}.css, static/js/app.js
static/js/app.js           -> api, hooks, live, blunder, notifications, room-flow, screen-state, seat-store,
                              training/lessons-api, training/trainer, settings, share, view-model,
                              screens/blunder-dialog, screens/game, screens/lobby, screens/win-sequence
static/js/room-flow.js     -> api, hooks
static/js/screens/game.js  -> board/board, settings-panel, view-model, screens/overlay
static/js/screens/lobby.js -> api, board/board
static/js/board/board.js   -> board/geometry, board/interaction, board/promotion
static/js/training/trainer.js -> board/board, training/arrow, training/lessons-api, training/trainer-state
static/js/training/lessons-api.js -> api
static/js/notifications.js -> settings, notify-core
static/js/settings-panel.js -> settings
static/js/screens/blunder-dialog.js -> blunder
static/sw.js               -> (copy of the notify-core shared block; no imports)
```

No import cycles. Component-level dependencies: `component-inventory.md`, Dependency Summary.

## Risks

- **Single process.** Room locks and the socket hub are in memory; a second worker would break locking and fan-out silently.
- **Undeclared direct imports.** `requests`, `cryptography` and `py_vapid` are imported directly but only arrive through `pywebpush`.
- **Unpinned upper bounds** on `python-chess`, `pyyaml` and `pywebpush`; the lockfile pins them, so this matters on `uv lock --upgrade`.
- **GPLv3 engine.** Downloading Stockfish at runtime does not redistribute it; an image that bundles `.engines/` would. Talking to it over UCI as a separate process (as python-chess `chess.engine` does) keeps the app code separate.
- **Working-directory coupling.** The default database path is relative to the working directory.
- **`.env` load order.** `JUSTCHESS_DB`, `JUSTCHESS_ORIGIN` and `JUSTCHESS_LESSONS_DIR` are read at import of `app.py`; any new setting read at import must stay after `envfile.load()`.
- **Duplicated wording.** End-reason texts exist in `notifications.py`, `view-model.js`, `notify-core.js` and `sw.js`; only the last two are pinned equal.
