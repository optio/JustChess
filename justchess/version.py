"""The running app's version: the short commit it was built from.

Resolution order (first one found wins):

1. ``JUSTCHESS_VERSION`` — set it explicitly for any deployment;
2. ``VERCEL_GIT_COMMIT_SHA`` — Vercel's system variable, when exposed at runtime;
3. ``build-version.txt`` next to ``app.py`` — written during a build where git
   is unavailable at runtime (Vercel's install command runs
   ``python -m justchess.version --write build-version.txt``);
4. ``git rev-parse --short HEAD`` in the project folder (local runs);
5. ``"unknown"``.

Only a short, plain token is ever returned (letters, digits, ``.``, ``-``,
``_``, at most 40 characters), so it is safe to put in the page.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD_FILE = ROOT / "build-version.txt"
UNKNOWN = "unknown"
SHORT = 7
_SAFE = re.compile(r"^[A-Za-z0-9._-]{1,40}$")


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    if not value or not _SAFE.fullmatch(value):
        return None
    # A full commit hash is shortened; anything else (a tag, a release name) is kept.
    return value[:SHORT] if re.fullmatch(r"[0-9a-f]{40}", value) else value


def _from_git(root: Path) -> str | None:
    try:
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True,
                                text=True, timeout=2, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return _clean(result.stdout) if result.returncode == 0 else None


def resolve_version(env: Mapping[str, str] | None = None, build_file: Path = BUILD_FILE, root: Path = ROOT) -> str:
    """Return the app's version string (see the module docstring)."""
    env = os.environ if env is None else env
    for value in (env.get("JUSTCHESS_VERSION"), env.get("VERCEL_GIT_COMMIT_SHA")):
        if cleaned := _clean(value):
            return cleaned
    try:
        if cleaned := _clean(build_file.read_text(encoding="utf-8")):
            return cleaned
    except OSError:
        pass
    return _from_git(root) or UNKNOWN


def write_build_file(target: Path, env: Mapping[str, str] | None = None) -> str:
    """Write the resolved version to ``target`` (build step) and return it."""
    version = resolve_version(env, build_file=Path("/nonexistent"))
    target.write_text(version + "\n", encoding="utf-8")
    return version


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--write":
        print(f"build version: {write_build_file(Path(sys.argv[2]))}")
    else:
        print(resolve_version())
