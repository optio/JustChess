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

from justchess import envfile

envfile.load()

import stockfish_install  # noqa: E402  (after .env, so its settings apply)
from justchess.api import create_app  # noqa: E402
from justchess.db import resolve_db_path  # noqa: E402

DB: Path = resolve_db_path()
ENGINE_DIR: Path = Path(__file__).resolve().parent / ".engines" / f"stockfish-{stockfish_install.PINNED_VERSION}"

app = create_app(db_path=lambda: DB, engine_dir=lambda: ENGINE_DIR,
                 database_url=lambda: os.environ.get("DATABASE_URL"))
