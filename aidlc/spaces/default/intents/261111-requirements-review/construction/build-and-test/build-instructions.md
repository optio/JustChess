# Build Instructions — JustChess

Inputs: `construction/code-generation/code-generation-plan.md`, `construction/code-generation/unit-test-instructions.md`, `construction/code-generation/code-summary.md`.

## Dependency installation

```bash
uv sync            # installs runtime deps and the dev group (pytest, httpx)
```

Use `uv sync --frozen` to install exactly what `uv.lock` pins. Python 3.11+ is required.

## Environment setup

| Variable | Default | Purpose |
|---|---|---|
| `STOCKFISH_PATH` | unset | Use this Stockfish binary instead of searching or downloading |
| `STOCKFISH_AUTO_INSTALL` | on | Set to `0` to stop the app downloading Stockfish at start |

No other configuration is needed. The SQLite file `justchess.sqlite3` is created on first start. Stockfish, when the app downloads it, goes to `.engines/stockfish-sf_19/`, which is git-ignored.

## Build commands

This is a Python app with no compile or bundle step. To check that the sources compile:

```bash
uv run --frozen python -m compileall -q app.py stockfish_install.py tests
```

## Build verification

```bash
uv run --frozen uvicorn app:app --port 8765
curl http://127.0.0.1:8765/api/engine   # {"available": true|false, "path_source": ..., "version": ...}
curl -o /dev/null -w '%{http_code}' http://127.0.0.1:8765/   # 200
```

For development, use `uv run fastapi dev` (auto-reload).

## Troubleshooting

- **`/api/engine` reports `available: false`.** The download failed: no network, an unsupported platform, or a checksum mismatch. The server log says which. Set `STOCKFISH_PATH` to an installed binary, or run `apt install stockfish` so it is found on PATH.
- **Leftover `.stockfish-*` or `*.part` files in `.engines/`.** A reload interrupted an install. They are removed automatically on a start more than 10 minutes later.
- **Slow shutdown right after the first start.** The first download may still be running. It finishes, or gives up, within about 60 s.
