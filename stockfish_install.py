"""Find or install a pinned, checksum-verified Stockfish binary.

Resolution order (see ``ensure_stockfish``):

1. ``STOCKFISH_PATH`` environment variable, when it points to an executable file;
2. ``stockfish`` on the system PATH;
3. a binary already installed by this app in ``install_dir``;
4. otherwise download, verify and install the pinned build, unless
   ``STOCKFISH_AUTO_INSTALL=0``.

Every failure is logged and returned in ``EngineResult.error``; nothing here
raises to the caller of ``ensure_stockfish``, so the app always starts.

Network and filesystem lookups are passed in as parameters so tests can
replace them. Standard library only.
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform as _platform
import shutil
import stat
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping

logger = logging.getLogger("justchess.stockfish")

PINNED_VERSION = "sf_19"
BASE_URL = f"https://github.com/official-stockfish/Stockfish/releases/download/{PINNED_VERSION}/"
BINARY_NAME = "stockfish"
DOWNLOAD_TIMEOUT = 60.0
MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024
STALE_AFTER = 10 * 60.0  # seconds; longer than any download + extraction in progress
_CHUNK = 1024 * 1024


@dataclass(frozen=True)
class Release:
    asset: str
    sha256: str


RELEASES: dict[str, Release] = {
    "linux-aarch64": Release(
        "stockfish-linux-arm64-universal.tar.gz",
        "fe26cfd1d9db4c8af3d21e24d9ff34cacb31c1f940085a7583da11796f2bac01",
    ),
    "linux-x86_64": Release(
        "stockfish-linux-x86-64-universal.tar.gz",
        "9defc0d4e55d49c65a6d042f3e571a39fcea499ade6dbe741b53b8c65e03611f",
    ),
    "macos": Release(
        "stockfish-macos-universal.tar.gz",
        "a1f0e3bcc5a6927a11fe6fc8e54a779754645f3c2bae2cf13420fd1957adaa77",
    ),
}


class InstallError(Exception):
    """A Stockfish download, verification or extraction step failed."""


@dataclass(frozen=True)
class EngineResult:
    path: Path | None = None
    source: str | None = None  # "env" | "path" | "cached" | "downloaded"
    version: str | None = None
    error: str | None = None

    @property
    def available(self) -> bool:
        return self.path is not None


Downloader = Callable[[str, Path, float], None]
Which = Callable[[str], "str | None"]


def platform_key(system: str | None = None, machine: str | None = None) -> str | None:
    """Return the ``RELEASES`` key for this machine, or None when unsupported."""
    system = (system or _platform.system()).lower()
    machine = (machine or _platform.machine()).lower()
    if system == "darwin":
        return "macos"
    if system == "linux" and machine in ("aarch64", "arm64"):
        return "linux-aarch64"
    if system == "linux" and machine in ("x86_64", "amd64"):
        return "linux-x86_64"
    return None


def _is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def resolve_existing(env: Mapping[str, str], which: Which, install_dir: Path) -> tuple[Path, str] | None:
    """Find an existing binary: env var, then PATH, then a previous install."""
    env_path = env.get("STOCKFISH_PATH", "").strip()
    if env_path:
        candidate = Path(env_path).expanduser()
        if _is_executable(candidate):
            return candidate, "env"
        logger.warning("STOCKFISH_PATH=%s is not an executable file; ignoring it", env_path)
    found = which(BINARY_NAME)
    if found and _is_executable(Path(found)):
        return Path(found), "path"
    cached = Path(install_dir) / BINARY_NAME
    if _is_executable(cached):
        return cached, "cached"
    return None


def verify_sha256(path: Path, expected: str) -> bool:
    """Return True when the file's SHA-256 matches ``expected`` (hex, any case)."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest() == expected.strip().lower()


def _is_unsafe_name(name: str) -> bool:
    pure = PurePosixPath(name.replace("\\", "/"))
    return pure.is_absolute() or ".." in pure.parts or name.startswith(("/", "\\"))


def _pick_member(members: list[tarfile.TarInfo], member_prefix: str) -> tarfile.TarInfo:
    unsafe = [m.name for m in members if _is_unsafe_name(m.name)]
    if unsafe:
        raise InstallError(f"archive contains unsafe member path(s): {unsafe}")
    candidates = [
        m for m in members
        if PurePosixPath(m.name).name.startswith(member_prefix) and len(PurePosixPath(m.name).parts) <= 2
    ]
    links = [m.name for m in candidates if m.issym() or m.islnk()]
    if links:
        raise InstallError(f"archive member is a link, refusing: {links}")
    files = [m for m in candidates if m.isreg()]
    if len(files) != 1:
        raise InstallError(f"expected exactly one '{member_prefix}*' file in archive, found {len(files)}")
    return files[0]


def safe_extract(archive: Path, member_prefix: str, dest: Path) -> Path:
    """Extract the single ``member_prefix*`` regular file to ``dest/stockfish``.

    Refuses absolute paths, ``..`` components and links. Raises InstallError.
    """
    dest = Path(dest)
    try:
        with tarfile.open(archive, "r:*") as tar:
            member = _pick_member(tar.getmembers(), member_prefix)
            source = tar.extractfile(member)
            if source is None:
                raise InstallError(f"cannot read archive member {member.name}")
            dest.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(dir=dest, prefix=".stockfish-")
            try:
                with os.fdopen(fd, "wb") as out, source:
                    shutil.copyfileobj(source, out)
                os.chmod(tmp_name, os.stat(tmp_name).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                target = dest / BINARY_NAME
                os.replace(tmp_name, target)
            except BaseException:
                Path(tmp_name).unlink(missing_ok=True)
                raise
    except (tarfile.TarError, OSError) as exc:
        raise InstallError(f"extraction failed: {exc}") from exc
    return target


def download(url: str, dest: Path, timeout: float = DOWNLOAD_TIMEOUT) -> None:
    """Download ``url`` (https only) to ``dest`` within ``timeout`` seconds."""
    if not url.startswith("https://"):
        raise InstallError(f"refusing non-https download URL: {url}")
    deadline = time.monotonic() + timeout
    received = 0
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response, open(dest, "wb") as out:
            while chunk := response.read(_CHUNK):
                received += len(chunk)
                if received > MAX_DOWNLOAD_BYTES:
                    raise InstallError(f"download exceeds {MAX_DOWNLOAD_BYTES} bytes")
                if time.monotonic() > deadline:
                    raise InstallError(f"download timed out after {timeout:.0f}s")
                out.write(chunk)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise InstallError(f"download failed: {exc}") from exc


def _remove_leftovers(install_dir: Path, min_age: float = STALE_AFTER) -> None:
    """Delete temp/partial files left by a process killed mid-install (e.g. a dev reload)."""
    if not install_dir.is_dir():
        return
    now = time.time()
    for leftover in [*install_dir.glob(".stockfish-*"), *install_dir.glob("*.part")]:
        try:
            if now - leftover.stat().st_mtime > min_age:
                leftover.unlink()
                logger.info("removed stale Stockfish install leftover %s", leftover.name)
        except OSError as exc:
            logger.warning("could not remove stale leftover %s: %s", leftover, exc)


def _auto_install_enabled(env: Mapping[str, str]) -> bool:
    return env.get("STOCKFISH_AUTO_INSTALL", "1").strip() != "0"


def _install(install_dir: Path, release: Release, downloader: Downloader) -> Path:
    install_dir.mkdir(parents=True, exist_ok=True)
    archive = install_dir / (release.asset + ".part")
    try:
        downloader(BASE_URL + release.asset, archive, DOWNLOAD_TIMEOUT)
        if not verify_sha256(archive, release.sha256):
            raise InstallError(f"checksum mismatch for {release.asset}")
        return safe_extract(archive, BINARY_NAME, install_dir)
    finally:
        try:
            archive.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("could not remove %s: %s", archive, exc)


def ensure_stockfish(
    install_dir: Path,
    env: Mapping[str, str] | None = None,
    auto_install: bool | None = None,
    *,
    which: Which = shutil.which,
    downloader: Downloader = download,
    platform: str | None = None,
    releases: Mapping[str, Release] = RELEASES,
) -> EngineResult:
    """Return a usable Stockfish, installing the pinned build if needed. Never raises."""
    env = os.environ if env is None else env
    install_dir = Path(install_dir)
    try:
        _remove_leftovers(install_dir)
        existing = resolve_existing(env, which, install_dir)
        if existing:
            path, source = existing
            version = PINNED_VERSION if source == "cached" else None
            logger.info("Stockfish found (%s)", source)
            return EngineResult(path=path, source=source, version=version)
        if auto_install is None:
            auto_install = _auto_install_enabled(env)
        if not auto_install:
            logger.info("Stockfish not found and STOCKFISH_AUTO_INSTALL=0; running without an engine")
            return EngineResult(error="not installed (auto-install disabled)")
        key = platform if platform is not None else platform_key()
        release = releases.get(key) if key else None
        if release is None:
            logger.warning("no pinned Stockfish build for platform %r; running without an engine", key)
            return EngineResult(error=f"unsupported platform: {key}")
        path = _install(install_dir, release, downloader)
        logger.info("Stockfish %s installed", PINNED_VERSION)
        return EngineResult(path=path, source="downloaded", version=PINNED_VERSION)
    except InstallError as exc:
        logger.error("Stockfish install failed: %s", exc)
        return EngineResult(error=str(exc))
    except Exception as exc:  # boot must never fail because of Stockfish
        logger.exception("unexpected error while preparing Stockfish")
        return EngineResult(error=f"unexpected error: {exc}")
