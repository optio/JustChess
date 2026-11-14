## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-11-14T00:00:00Z
**Iteration:** 1
**Verdict Dictated:** no

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Minor | aidlc/spaces/default/intents/261113-p2-features/construction/u4-play-the-computer/functional-design/rules.md > BR4.2 logic | The rule still says the computer end check uses the claim-aware outcome with claimable draws. The code uses `board.is_repetition(3)` and `is_fifty_moves()` in `games.end_for`. That is the better behaviour, because a draw the next move could reach does not end the game, and the deviation is recorded in code-summary.md. The rule text now disagrees with the shipped code. | Reword BR4.2 to say the position on the board is checked with `is_repetition(3)` and `is_fifty_moves()`, so the rule matches the code. | New |
| R-02 | Minor | justchess/api.py > `Services._complete_reply` failure branch | A failed reply sets the room's retry backoff even when its game has since been replaced by a rematch. After a rematch with the computer as white, the first resume ask (`computer-move`) can then be held back up to 5 s. The rematch itself asks without the backoff, so the effect is small and only briefly delays a retry. | Set the backoff only when the failed request's game is still the current game, or clear it when a rematch starts. | New |
| R-03 | Minor | aidlc/spaces/default/intents/261113-p2-features/construction/u4-play-the-computer/code-generation/unit-test-instructions.md > Scope table | The per-file test counts differ from code-summary.md (for example 8 against 9 in test_computer_rooms.py, test_engine.py and test_computer_api.py). The unit run itself gave 58 Python tests and 14 JS tests, all passing. | Align the counts in the two documents. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| uv run --frozen pytest -q (the ten unit test files in unit-test-instructions.md, including real Stockfish and headless Chromium) | 58 passed, 1 deprecation warning from python-chess | The unit's Python tests pass, including the NFR1 real-engine timing test and the browser test. |
| node --test tests/js/computer.test.mjs tests/js/computer-panel.test.mjs | 14 passed, 0 failed | The unit's JS tests pass. |

### Summary

The design is implemented as specified. The reply race follows ADR-009: each flag carries gameId, version and requestId, and a reply clears only its own flag in a `finally`. A rematch replaces the flag, and a reply for a changed game is discarded. The room lock is never held across a search: the lock is taken only for the short read in `read_hint_position` and the write in `_complete_reply`. The engine has a bounded FIFO queue and a one-restart policy, and a search that overruns by 5 s counts as a crash. Shutdown cancels the reply tasks first and then stops the engine. A hint is cancelled when the client disconnects. Only positions replayed from storage reach UCI, and the engine's move is checked to be legal before use. The computer's seat has no token, so only seat A can act. Tokens stay out of URLs and logs, `/api/engine` exposes no binary path, and per-address limits and the queue cap are in place. The `is_repetition(3)` / `is_fifty_moves()` deviation, the extra `computer.message` field and the two changed existing tests are sound. The remaining findings are minor: BR4.2's wording is out of date, a failed old-game reply can briefly delay a retry, and the test counts differ between two documents.
