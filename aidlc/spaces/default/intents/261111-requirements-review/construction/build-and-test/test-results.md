# Test Results

Run on 2026-11-11, Linux aarch64 (Raspberry Pi), Python via uv.

## Build status

- `uv sync --frozen` succeeded: "Checked 65 packages".
- `uv run --frozen python -m compileall -q app.py stockfish_install.py tests` succeeded (exit 0).

## Unit tests

Command, run once (taken from `construction/code-generation/unit-test-instructions.md`):

```
uv run --frozen pytest tests/test_stockfish_install.py -q
........                                                                 [100%]
8 passed in 0.44s
```

| Total | Passed | Failed | Skipped |
|---|---|---|---|
| 8 | 8 | 0 | 0 |

No coverage was measured, because the `poc` scope sets no coverage floor.

## App start check (smoke test)

`uv run --frozen uvicorn app:app --port 8765` was started, queried, then stopped. Results:

- `GET /api/engine` returned `{"available":true,"path_source":"cached","version":"sf_19"}`.
- `GET /` returned 200.
- `GET /api/lessons` returned 200 (an existing route, unchanged).
- The installed binary answers: `.engines/stockfish-sf_19/stockfish` printed "Stockfish 19 by the Stockfish developers".

This also confirms that the pinned aarch64 asset and checksum are correct. The binary was installed earlier by a real download, whose checksum matched.

## Observations

- `.engines/stockfish-sf_19/.stockfish-x3mg3q2s` (91 MB) is still present. It is the leftover from a dev-server reload that interrupted an extraction. The new cleanup rule removes such files only once they are older than 10 minutes, so it will be gone on a later start. Deleting it by hand is also safe.

## Target Verification Matrix

| Target ID | Source | Expected | Actual | Evidence | Owning Stage | Verdict |
|---|---|---|---|---|---|---|
| TC-STRATEGY-1 | Testing Contract, `obligations.strategy_volume` (one test per requirement; one happy-path test per component) | FR9.1 and the installer component have tests | 8 tests cover FR9.1 and `stockfish_install.py`, including the happy path | pytest output above | build-and-test | Met |
| TC-SCOPE-1 | Testing Contract, `obligations.scope_floor` (keep the existing suite green) | No existing test fails | No suite existed before; the new suite is green | pytest output above | build-and-test | Met |
| PLAN-START-1 | `code-generation/unit-test-instructions.md` § Expected coverage targets (the app still starts) | App starts and serves existing routes; `/api/engine` answers | Started; `/` 200, `/api/lessons` 200, `/api/engine` available | smoke check above | build-and-test | Met |
| CI-1 | Testing Contract CI obligation | — | — | — | — | N/A: the plan runs no CI Pipeline |
