# Build Instructions — JustChess P1

## Prerequisites

- Python 3.11 or newer, with `uv` installed.
- Node 20 or newer, which provides the `node --test` runner. Node is used only for the frontend tests; the app itself needs no Node.
- Optional: Chromium, for the browser tests. Set `JUSTCHESS_CHROMIUM` to a browser binary if it is not on `PATH`.

## Install dependencies

```bash
uv sync --frozen
```

This installs FastAPI, python-chess, PyYAML, pywebpush and the dev group (pytest, httpx) from `uv.lock`.

There is no npm install step. The frontend is native ES modules served as static files.

## Environment

| Variable | Purpose | Default |
|---|---|---|
| `JUSTCHESS_DB` | SQLite file | `justchess.sqlite3` |
| `JUSTCHESS_ORIGIN` | Expected origin, for when the app runs behind a proxy | derived from the request |
| `JUSTCHESS_LESSONS_DIR` | Lesson files folder | `lessons/` |
| `JUSTCHESS_VAPID_KEY_FILE` / `JUSTCHESS_VAPID_PRIVATE_KEY` | Web Push signing key, which must live outside the repo | unset, so push is off |
| `JUSTCHESS_VAPID_SUBJECT` | Contact for the push service | `mailto:admin@localhost` |
| `JUSTCHESS_PUSH_HOSTS` | Extra allowed push hosts | built-in allowlist |
| `STOCKFISH_AUTO_INSTALL` | Set to `0` to skip the Stockfish download at start-up | on |

To create a push key outside the project:

```bash
uv run python -m justchess.vapid generate ~/.config/justchess/vapid.pem
export JUSTCHESS_VAPID_KEY_FILE=~/.config/justchess/vapid.pem
```

## Build and run

There is no compile or bundle step.

```bash
uv run fastapi dev app.py --host 0.0.0.0     # development, auto-reload
uv run uvicorn app:app --host 0.0.0.0        # single process (required: rooms use in-process locks)
```

## Build verification

```bash
uv run --frozen pytest -q        # whole suite; also runs the Node suite through tests/test_frontend_js.py
node --test tests/js/            # frontend suite on its own
```

On start-up the server runs the database check. A schema version 2 database is upgraded in place to version 3, and an older one is moved to `justchess.sqlite3.old`.

## Troubleshooting

- **Browser tests skipped:** Chromium was not found. Install it, or set `JUSTCHESS_CHROMIUM`.
- **`/api/push/key` returns 404:** no VAPID key is set, so push is off by design. Local notifications still work while the tab is open.
- **Push on a phone:** service workers and push need HTTPS. Plain HTTP only works on `localhost`, so a phone on your LAN needs HTTPS. Hosting is still an open decision; see the README.
- **"Database has a newer schema" at start-up:** the file came from a newer version of JustChess. The app refuses to touch it.
