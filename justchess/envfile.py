"""Load settings from a ``.env`` file into the process environment.

The app reads all of its settings (``JUSTCHESS_DB``, ``JUSTCHESS_VAPID_KEY_FILE``
and the others listed in ``.env.example``) from environment variables. This
module lets them live in a ``.env`` file at the project root instead of being
exported in every shell.

Rules:

- one ``KEY=VALUE`` per line; blank lines and lines starting with ``#`` are
  ignored; a leading ``export`` is allowed;
- a value wrapped in matching single or double quotes is unwrapped;
- a variable that is already set in the real environment wins, so a shell
  ``export`` or a test can always override the file;
- a missing file is not an error; an unreadable or malformed line is logged
  by line number (never with its value) and skipped.

Secrets do not belong in ``.env`` itself: the Web Push key stays in its own
file outside the repository and ``.env`` only names that file. ``.env`` is
ignored by git; ``.env.example`` documents every setting.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import MutableMapping
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"

_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def parse(text: str) -> tuple[dict[str, str], list[int]]:
    """Parse ``.env`` text; return the values and the numbers of the lines skipped as malformed."""
    values: dict[str, str] = {}
    bad: list[int] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, sep, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not _KEY.fullmatch(key):
            bad.append(number)
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values, bad


def load(path: Path | str = DEFAULT_ENV_FILE, environ: MutableMapping[str, str] | None = None) -> list[str]:
    """Copy the file's settings into ``environ`` (default ``os.environ``) without overriding.

    Returns the names that were set from the file.
    """
    env = os.environ if environ is None else environ
    file = Path(path)
    try:
        text = file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except OSError as error:
        logger.warning("Could not read %s: %s", file, error.strerror or error)
        return []
    values, bad = parse(text)
    for number in bad:
        logger.warning("Skipping line %d of %s: expected KEY=VALUE", number, file)
    applied = []
    for key, value in values.items():
        if key in env:
            continue
        env[key] = value
        applied.append(key)
    if applied:
        logger.info("Loaded %s from %s", ", ".join(sorted(applied)), file)
    return applied
