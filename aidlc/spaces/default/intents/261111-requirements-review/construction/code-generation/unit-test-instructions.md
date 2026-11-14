# Unit Test Instructions — docs retirement and Stockfish auto-install

## Test framework setup and configuration

- Runner: pytest 9.x, from the project's `dev` dependency group (`pyproject.toml`), with httpx for FastAPI's `TestClient`.
- Configuration: `[tool.pytest.ini_options]` in `pyproject.toml` with `testpaths = ["tests"]`, added in plan Step 1.
- Prerequisite: run `uv sync` once (installs the dev group). The tests need no network, no Stockfish binary and no database.

## How to run this step's tests

Run exactly this command from the project root (it is scoped to this step's test file only):

```bash
uv run --frozen pytest tests/test_stockfish_install.py -q
```

Before the test file exists, `uv run --frozen pytest --version` confirms the runner is ready (it reports pytest 9.2.0).

## Tests (Minimal strategy: one test per behaviour of the new component)

1. `STOCKFISH_PATH` pointing to an executable is used, with source `env`.
2. With no env path, a `stockfish` found on PATH is used, with source `path`.
3. A binary already installed under the install folder is reused without any download, with source `cached`.
4. A faked download with the correct checksum installs an executable binary, with source `downloaded`.
5. A faked download with the wrong checksum installs nothing and returns an error.
6. An archive member with `..` or an absolute path is refused and nothing is written outside the install folder.
7. `STOCKFISH_AUTO_INSTALL=0`, or an unsupported platform, returns "not available" without calling the downloader.
8. `GET /api/engine` reports the (patched) engine result: availability, source and version, with no file path.

## Expected coverage targets

The `poc` scope sets no coverage floor; the Minimal strategy asks for one test per behaviour above. Build and Test runs this file and checks that the app still starts.

## Mocking / stubbing guidance

- Network: pass a fake `download` callable that copies a tar.gz built in `tmp_path` (with `tarfile`) to the destination; never call GitHub in tests.
- Checksums: compute the real sha256 of the fake archive for the success test, and pass a different value for the mismatch test, by overriding the release table entry through a parameter or `monkeypatch`.
- Environment and PATH: pass `env` dicts and a fake `which` callable instead of changing the real environment.
- Platform: pass the platform key explicitly, or `monkeypatch` `platform_key`.
- Endpoint: `monkeypatch` `stockfish_install.ensure_stockfish` (or `app.state.stockfish`) to a fixed result before creating `TestClient(app)`.

## Test data management

All files (fake binaries, archives, install folders) are created under pytest's `tmp_path` and removed automatically. The real `.engines/` folder and `justchess.sqlite3` are never touched by these tests.
