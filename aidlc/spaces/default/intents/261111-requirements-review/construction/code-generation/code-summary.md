# Code Summary — docs retirement and Stockfish auto-install

## Files created / modified

| File | Change |
|---|---|
| `REQUIREMENTS.md` | Deleted. The product spec now lives in `aidlc/spaces/default/intents/261111-requirements-review/inception/requirements-analysis/requirements.md` |
| `README.md` | The requirements link points to the AI-DLC requirements record, with a note that requirements live in the AI-DLC records. New "Stockfish" section covering the lookup order, `STOCKFISH_PATH`, `STOCKFISH_AUTO_INSTALL=0`, `.engines/`, `/api/engine` and the GPLv3 note |
| `stockfish_install.py` | New, standard library only. It contains: <br>• the pinned `sf_19` release table for Linux aarch64, Linux x86_64 and macOS, with SHA-256 checksums<br>• `platform_key`, `resolve_existing`, `verify_sha256`, `safe_extract`, `download` and `ensure_stockfish`<br>• the `EngineResult` result object and an `InstallError` exception |
| `app.py` | The lifespan starts the installer in a background task (`asyncio.to_thread`) and keeps the result on `app.state.stockfish`. New read-only `GET /api/engine` endpoint. Existing routes are unchanged |
| `tests/test_stockfish_install.py` | New: 8 tests, no network |
| `pyproject.toml` | Adds `[tool.pytest.ini_options]` with `testpaths = ["tests"]` and `pythonpath = ["."]` |
| `.gitignore` | Adds `.engines/`, outside the AI-DLC block |
| Requirements record (`requirements.md`, its `traceability.json`) | Adds FR9 / FR9.1, "chess engine availability". The "no chess engine" constraint now reads: an engine may be installed, and using it for analysis is a later decision |

## Key implementation decisions

- **Lookup order:**
  1. `STOCKFISH_PATH`
  2. `stockfish` on PATH
  3. the cached binary at `.engines/stockfish-sf_19/stockfish`
  4. download of the pinned build, unless `STOCKFISH_AUTO_INSTALL=0`
- **Safety:**
  - Downloads use https only, with a 60 s timeout and a 200 MB cap.
  - The SHA-256 checksum must match before extraction.
  - Exactly one regular-file member whose name starts with `stockfish` is extracted.
  - Any absolute path, `..` or link in the archive refuses the whole archive.
  - The binary is written to a temp file, made executable, then moved into place atomically.
  - At each start, leftover partial files older than 10 minutes are cleaned up.
- **Failure handling:** every failure is logged and returned in the result, and the app always starts. With no engine, `/api/engine` reports `available: false`.
- **Exposure:** `/api/engine` never exposes the binary's file path. `version` is `sf_19` only for binaries this app installed.
- **Usage:** nothing uses the engine yet. It is there for future features (FR9.1).

## Test coverage summary

`uv run --frozen pytest tests/test_stockfish_install.py -q` gave **8 passed** (run by the developer and again after the build). The tests cover:
- the env path
- PATH
- cache reuse
- a successful download with the correct checksum
- a checksum mismatch
- a path-traversal archive refused
- auto-install off / unsupported platform
- the `/api/engine` endpoint

## Tests written but not executed

None. The real `download()` network call has no unit test by design (the tests use no network). However, the app's own dev server reloaded during the build and ran the real installer. The pinned aarch64 asset downloaded and passed its checksum, so the binary is now installed at `.engines/stockfish-sf_19/stockfish`.

## Deviations from the plan

- `pythonpath = ["."]` was added to the pytest config, because the project is not an installable package and the tests import modules from the project root.
- Leftover-file cleanup was added, after a dev-server reload interrupted one extraction. A 91 MB temp file was left in `.engines/stockfish-sf_19/` and is removed on the next start.
- Known limit: during a first download, shutdown can wait up to 60 s, because the background thread cannot be cancelled.
- The README still says "`uv run pytest` once tests are added". It was not changed, because that line is outside this plan.
