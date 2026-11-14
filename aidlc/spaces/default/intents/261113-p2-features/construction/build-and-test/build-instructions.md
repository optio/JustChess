# Build Instructions — JustChess P2

## Prerequisites
- **Python 3.14** and **uv**. The project is a uv project (`pyproject.toml`, `uv.lock`).
- **Node.js 20 or later** for the front-end unit tests. They run with `node --test`; there is no bundler or npm install.
- **Chromium** (`/usr/bin/chromium` on the Pi) for the browser tests. Without it they skip with a reason.
- **Stockfish:** found through `STOCKFISH_PATH`, then `PATH`, then `.engines/`, or downloaded at start-up (`STOCKFISH_AUTO_INSTALL`, on by default). Without it, play the computer, hints and the endgame trainer show as unavailable, and the rest of the site works.
- `zstd` only when you re-run `scripts/curate_puzzles.py`. The curated puzzles are already in `puzzles/`.

## Install
```bash
uv sync --frozen
```

## Configuration
- Copy `.env.example` to `.env` and fill in what you need. Variables already set in the shell win over the file.
- **Main settings:**
  - `JUSTCHESS_DB` (default `justchess.sqlite3`)
  - `JUSTCHESS_ORIGIN`
  - `JUSTCHESS_TRUSTED_PROXIES`
  - `JUSTCHESS_GAMEPLAY_FILE` (default `gameplay.yaml`)
  - `STOCKFISH_PATH`, `STOCKFISH_AUTO_INSTALL`
  - the Web Push VAPID settings (keep the keys outside the project)
- **Gameplay tuning:** `gameplay.yaml` at the repo root. A bad value stops start-up with an error naming the key.
- **Database:** schema version 4. An older database file is moved to `justchess.sqlite3.old` and a fresh one is created.

## Build
There is no compile step: Python runs from source and the front end is native ES modules. To check that the app imports and starts:
```bash
uv run --frozen python -c "import app"
uv run --frozen uvicorn app:app --host 127.0.0.1 --port 8000
```
Check that `GET /api/engine` answers, and that `/`, `/learn` and `/learn/endgames` load.

## Verify
```bash
uv run --frozen pytest -q      # the whole suite, including the node bridge and the browser tests
node --test tests/js/           # the front-end unit tests on their own
```

## Troubleshooting
- **Browser tests skipped:** install Chromium, or set its path as `tests/test_game_screen.py` describes.
- **`GameplayError` at start-up:** fix the key named in the message in `gameplay.yaml`, or in the file `JUSTCHESS_GAMEPLAY_FILE` points to.
- **Computer unavailable:** see `GET /api/engine` for the reason. After two engine crashes, restart the app.
- **"Web Push is disabled":** set the VAPID settings in `.env`.
