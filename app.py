"""JustChess entry point.

Keeps ``uv run fastapi dev`` and ``uvicorn app:app`` working. The application
itself lives in the ``justchess`` package.

``DB`` and ``ENGINE_DIR`` are read when the app starts (not at import), so they
can be overridden before startup, for example by tests.

Settings in the project's ``.env`` file are loaded first; a variable already
set in the shell wins over the file (see ``justchess.envfile``).
"""

from pathlib import Path
import os
import tempfile

from justchess import envfile

if os.environ.get("VERCEL") != "1":
    envfile.load()

import stockfish_install  # noqa: E402  (after .env, so its settings apply)
from justchess.api import create_app  # noqa: E402
from justchess.db import DatabaseStartupError, resolve_db_path  # noqa: E402

DB: Path = resolve_db_path()
ENGINE_DIR: Path = Path(__file__).resolve().parent / ".engines" / f"stockfish-{stockfish_install.PINNED_VERSION}"
if os.environ.get("VERCEL") == "1":
    root = Path(__file__).resolve().parent
    runtime_platform = stockfish_install.platform_key()
    bundled_dir = root / ".vercel-stockfish" / runtime_platform if runtime_platform else None
    bundled_binary = bundled_dir / stockfish_install.BINARY_NAME if bundled_dir else None
    if bundled_binary and bundled_binary.is_file() and os.access(bundled_binary, os.X_OK):
        os.environ.setdefault("STOCKFISH_PATH", str(bundled_binary))
        ENGINE_DIR = bundled_dir
    else:
        ENGINE_DIR = Path(tempfile.gettempdir()) / "justchess-engines" / f"stockfish-{stockfish_install.PINNED_VERSION}"

def configured_database_url():
    value = os.environ.get("DATABASE_URL")
    if os.environ.get("VERCEL") == "1" and not value:
        raise DatabaseStartupError("Vercel requires DATABASE_URL; no ephemeral database fallback")
    return value


app = create_app(db_path=lambda: DB, engine_dir=lambda: ENGINE_DIR,
                 database_url=configured_database_url)
