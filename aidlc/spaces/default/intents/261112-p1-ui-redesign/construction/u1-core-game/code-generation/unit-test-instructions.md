# Unit Test Instructions — u1-core-game

## Test framework setup and configuration

- Runner: pytest 9.x, from the `dev` dependency group, with httpx for FastAPI's `TestClient`, which includes WebSocket testing.
- Configuration: `pyproject.toml` `[tool.pytest.ini_options]` already sets `testpaths = ["tests"]` and `pythonpath = ["."]`. Nothing new is needed.
- Prerequisite: run `uv sync` once. The tests need no network and no Stockfish binary. Each test uses a temporary database through `JUSTCHESS_DB` pointing into pytest's `tmp_path`.

## How to run this unit's tests

Run exactly this from the project root (scoped to this unit's test folder):

```bash
uv run --frozen pytest tests/core -q
```

Before the folder exists, `uv run --frozen pytest --version` confirms the runner is ready.

## Tests (Standard strategy: 5–8 per component, plus integration tests at the key boundaries)

| File | Component | Count | Covers |
|---|---|---|---|
| `tests/core/test_db.py` | db | 5 | schema v2; old file moved to `.old`; rollback; unique constraints; unwritable path |
| `tests/core/test_rooms.py` | Rooms | 8 | code format and retry; third join refused; rejoin; hash-only tokens; wrong token; continue redeem and expiry; score follows slot; rematch both seats, idempotent, lapse |
| `tests/core/test_games.py` | Games | 8 | legal and illegal moves; wrong side; stale version; checkmate, stalemate, insufficient material; threefold claimable via replay; fivefold auto-end; claim refused; numbered moves; watcher snapshot |
| `tests/core/test_api.py` | HttpApi (integration) | 8 | full game through HTTP; header-only state token; foreign origin 403; body over 4 KB 413; concurrent moves 200/409; concurrent rematch creates one game; claim win at 24 h; housekeeping deletes an idle room |
| `tests/core/test_live.py` | LiveUpdates (integration) | 6 | hello snapshot; seat vs watcher snapshot; legal moves only for the side to move; away after timeout; seat-moved on transfer; oversized message closes the socket |

The existing `tests/test_stockfish_install.py` must stay green.

## Expected coverage targets

The refactor scope sets no coverage floor. The Standard strategy asks for 5–8 tests per component, which the table meets. Build and Test runs the full suite.

## Mocking and stubbing guidance

- **Time:** Rooms and Games take an injectable `now()` clock, so tests can simulate 24 h abandonment, 30-day retention and the 10-minute continue expiry without sleeping.
- **Heartbeat timeout:** configurable; tests set it to about 0.2 s.
- **Concurrency:** use two threads with TestClient, or `asyncio.gather` against the app, to send simultaneous requests.
- **Startup:** the Stockfish preparation is patched to a no-op in the API tests (as the existing endpoint test does).

## Test data management

- Each test creates its own database in `tmp_path`. The real `justchess.sqlite3` is never opened.
- Positions for the rule tests come from short known move sequences: Fool's mate, a knight shuffle for repetition, and standard stalemate and insufficient-material positions built through moves where possible.
