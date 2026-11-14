"""Tests for the Stockfish auto-installer. No network, no real binary."""

import hashlib
import io
import os
import shutil
import stat
import tarfile
from pathlib import Path

import pytest

import stockfish_install as sf
from stockfish_install import EngineResult, InstallError, Release

PLATFORM = "linux-aarch64"
FAKE_BINARY = b"#!/bin/sh\necho 'Stockfish fake'\n"


def make_executable(path: Path, content: bytes = FAKE_BINARY) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def build_archive(path: Path, members: dict[str, bytes]) -> Path:
    """Build a tar.gz shaped like the official release: stockfish/<binary> + extras."""
    with tarfile.open(path, "w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(data))
    return path


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FakeDownloader:
    def __init__(self, archive: Path | None = None):
        self.archive = archive
        self.calls: list[str] = []

    def __call__(self, url: str, dest: Path, timeout: float) -> None:
        self.calls.append(url)
        if self.archive is None:
            raise AssertionError("downloader must not be called")
        shutil.copyfile(self.archive, dest)


def no_which(_name):
    return None


@pytest.fixture
def release_archive(tmp_path):
    return build_archive(
        tmp_path / "release.tar.gz",
        {
            "stockfish/stockfish-linux-arm64": FAKE_BINARY,
            "stockfish/AUTHORS": b"authors\n",
            "stockfish/src/bitboard.cpp": b"// source\n",
        },
    )


def test_env_path_wins_when_executable(tmp_path):
    env_binary = make_executable(tmp_path / "custom" / "my-stockfish")
    path_binary = make_executable(tmp_path / "bin" / "stockfish")
    downloader = FakeDownloader()

    result = sf.ensure_stockfish(
        tmp_path / "install", {"STOCKFISH_PATH": str(env_binary)},
        which=lambda _n: str(path_binary), downloader=downloader, platform=PLATFORM,
    )

    assert result == EngineResult(path=env_binary, source="env", version=None)
    assert downloader.calls == []


def test_path_binary_used_without_env_and_bad_env_ignored(tmp_path):
    path_binary = make_executable(tmp_path / "bin" / "stockfish")
    not_executable = tmp_path / "plain-file"
    not_executable.write_text("not a binary")

    result = sf.ensure_stockfish(
        tmp_path / "install", {"STOCKFISH_PATH": str(not_executable)},
        which=lambda _n: str(path_binary), downloader=FakeDownloader(), platform=PLATFORM,
    )

    assert result.available
    assert (result.path, result.source) == (path_binary, "path")


def test_cached_binary_reused_without_download(tmp_path):
    install_dir = tmp_path / "install"
    cached = make_executable(install_dir / "stockfish")
    stale = install_dir / ".stockfish-killed"  # left by a process killed mid-extraction
    stale.write_bytes(b"partial")
    old = stale.stat().st_mtime - sf.STALE_AFTER - 60
    os.utime(stale, (old, old))
    fresh = install_dir / ".stockfish-inprogress"  # another process may still be writing it
    fresh.write_bytes(b"partial")
    downloader = FakeDownloader()

    result = sf.ensure_stockfish(install_dir, {}, which=no_which, downloader=downloader, platform=PLATFORM)

    assert (result.path, result.source, result.version) == (cached, "cached", sf.PINNED_VERSION)
    assert downloader.calls == []
    assert not stale.exists() and fresh.exists()


def test_download_with_correct_checksum_installs_executable(tmp_path, release_archive):
    install_dir = tmp_path / ".engines" / "stockfish-sf_19"
    releases = {PLATFORM: Release("stockfish-linux-arm64-universal.tar.gz", sha256_of(release_archive))}
    downloader = FakeDownloader(release_archive)

    result = sf.ensure_stockfish(
        install_dir, {}, which=no_which, downloader=downloader, platform=PLATFORM, releases=releases,
    )

    assert result.error is None
    assert (result.source, result.version) == ("downloaded", sf.PINNED_VERSION)
    assert result.path == install_dir / "stockfish"
    assert result.path.read_bytes() == FAKE_BINARY
    assert os.access(result.path, os.X_OK)
    assert downloader.calls == [sf.BASE_URL + "stockfish-linux-arm64-universal.tar.gz"]
    # only the binary is extracted; the downloaded archive is cleaned up
    assert sorted(p.name for p in install_dir.iterdir()) == ["stockfish"]


def test_checksum_mismatch_installs_nothing(tmp_path, release_archive):
    install_dir = tmp_path / "install"
    releases = {PLATFORM: Release("stockfish-linux-arm64-universal.tar.gz", "0" * 64)}

    result = sf.ensure_stockfish(
        install_dir, {}, which=no_which, downloader=FakeDownloader(release_archive),
        platform=PLATFORM, releases=releases,
    )

    assert not result.available
    assert result.source is None
    assert "checksum mismatch" in result.error
    assert list(install_dir.iterdir()) == []


def test_unsafe_archive_members_are_refused(tmp_path):
    dest = tmp_path / "work" / "install"
    for bad_name in ("../stockfish", "/tmp/justchess-test/stockfish", "stockfish/../../stockfish"):
        archive = build_archive(tmp_path / "bad.tar.gz", {bad_name: FAKE_BINARY})

        with pytest.raises(InstallError, match="unsafe"):
            sf.safe_extract(archive, "stockfish", dest)

    # a symlink named like the binary is refused too
    link_archive = tmp_path / "link.tar.gz"
    with tarfile.open(link_archive, "w:gz") as tar:
        info = tarfile.TarInfo("stockfish/stockfish")
        info.type = tarfile.SYMTYPE
        info.linkname = "/bin/sh"
        tar.addfile(info)
    with pytest.raises(InstallError, match="link"):
        sf.safe_extract(link_archive, "stockfish", dest)

    assert not (tmp_path / "stockfish").exists()
    assert not (tmp_path / "work" / "stockfish").exists()
    assert not dest.exists() or list(dest.iterdir()) == []


def test_auto_install_disabled_or_unsupported_platform_does_not_download(tmp_path):
    downloader = FakeDownloader()

    disabled = sf.ensure_stockfish(
        tmp_path / "a", {"STOCKFISH_AUTO_INSTALL": "0"}, which=no_which,
        downloader=downloader, platform=PLATFORM,
    )
    unsupported = sf.ensure_stockfish(
        tmp_path / "b", {}, which=no_which, downloader=downloader, platform="windows-arm64",
    )

    assert not disabled.available and "disabled" in disabled.error
    assert not unsupported.available and "unsupported platform" in unsupported.error
    assert sf.platform_key("Windows", "AMD64") is None
    assert sf.platform_key("Linux", "aarch64") == "linux-aarch64"
    assert downloader.calls == []


def test_engine_endpoint_reports_patched_result(tmp_path, monkeypatch):
    import importlib
    import time

    from fastapi.testclient import TestClient

    monkeypatch.chdir(Path(__file__).resolve().parent.parent)  # templates/ and static/ are relative
    app_module = importlib.import_module("app")
    monkeypatch.setattr(app_module, "DB", tmp_path / "test.sqlite3")  # never touch justchess.sqlite3
    secret_path = tmp_path / "secret" / "stockfish"
    calls = []

    def fake_ensure(install_dir, env):
        calls.append(install_dir)
        return EngineResult(path=secret_path, source="downloaded", version=sf.PINNED_VERSION)

    monkeypatch.setattr(sf, "ensure_stockfish", fake_ensure)

    with TestClient(app_module.app) as client:
        deadline = time.monotonic() + 5
        body = client.get("/api/engine").json()
        while body["reason"] == "The computer is starting" and time.monotonic() < deadline:
            time.sleep(0.02)
            body = client.get("/api/engine").json()

    # P2 U4 (W8): ``available`` now means the engine process runs; this patched path does not exist, so
    # the found binary is still reported (source, version) with the reason the computer could not start.
    assert body == {"available": False, "path_source": "downloaded", "version": sf.PINNED_VERSION,
                    "reason": "The computer could not be started"}
    assert str(secret_path) not in str(body)
    assert calls == [app_module.ENGINE_DIR]
