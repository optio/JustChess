## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-11-11T20:46:04Z
**Iteration:** 1
**Verdict Dictated:** no

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Minor | stockfish_install.py > _install (archive = install_dir / (asset + ".part")) | The partial-download file name is fixed. Two processes starting together, such as uvicorn workers or a reload plus the parent, write the same `.part` file. One can unlink the other's file in its `finally`, or corrupt the download. The checksum check keeps a bad binary from being installed, but the loser gets a spurious install error and runs with no engine until restart. `os.replace` of the final binary is atomic, so this costs availability only. | Use a unique temp name for the download (for example `tempfile.mkstemp` in install_dir), or take a simple lock file. Alternatively, record in the docs that a single worker is expected. | New |
| R-02 | Minor | stockfish_install.py > RELEASES (pinned sha256 values) and _pick_member | The three SHA-256 values and the "exactly one regular file starting with `stockfish` at depth <= 2" archive layout rule could not be checked against the real sf_19 assets, because this review did not download Stockfish. Tests use a synthetic archive. A wrong hash or a different layout fails safe (logged error, app runs without an engine) but would silently never install. | Before relying on the engine in the P1 features, run one real install on each target platform. Confirm that `/api/engine` reports `available: true` and that the hashes match the release assets. | New |
| R-03 | Minor | stockfish_install.py > download | The deadline is checked only between chunks. `urlopen(timeout=...)` bounds each socket read, not total time, so a slow trickle can overrun 60s by up to one chunk read. The 200 MB cap and the background task keep this harmless to request serving. | Optional. Either accept this and say so in the docstring, or use smaller chunks. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| uv run --frozen pytest tests/test_stockfish_install.py -q | 8 passed in 0.54s | Covers env, PATH, cached, checksum success and mismatch, unsafe archive members, disabled and unsupported-platform paths, and `/api/engine`. This meets the happy-path-plus-error-cases standard. No coverage figure was measured. |

### Summary

The scope is small and sound. `ensure_stockfish` never raises, the install runs in a background thread so startup is not blocked, the download is https-only and size-capped, the checksum is verified before extraction, extraction rejects links and traversal, and `.engines/` is gitignored. Only minor robustness items remain, mainly the shared `.part` file under concurrent starts and real-asset verification that was not done here.
