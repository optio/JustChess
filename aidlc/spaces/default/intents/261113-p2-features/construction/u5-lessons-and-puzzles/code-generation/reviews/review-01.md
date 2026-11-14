## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-11-14T00:00:00Z
**Iteration:** 1
**Verdict Dictated:** no

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Minor | justchess/puzzles.py > check_move and hint | The check route answers "correct" or "wrong" with no attempt limit, and the hint route's "solution" level returns the whole line without any prior attempt. A client can therefore read or probe the solution. This matches BR2.4's hint levels and the project's local, unauthenticated model, so it is by design and not a leak in the detail route. | Optionally state in the design notes that the answer is intentionally obtainable through hint and check. No code change is needed. | New |
| R-02 | Minor | justchess/puzzles.py > check_move (deviation 3) | Any checkmating player move counts as "solved", even when it is not the expected move. This is sound for mateIn1 and mateIn2 and for the end of a tactic line. The extra response fields (fen, check, legalMoves, replyFen) carry only positions the player has already reached, so nothing is leaked. | Record this as an accepted deviation in the unit's design notes, so BR2.4 and the code agree. | New |
| R-03 | Minor | justchess/api.py > PuzzleCheckRequest and PuzzleHintRequest | The request bodies are typed as `object`. The validators in `justchess.puzzles` do reject every bad value with a 400, and the tests cover this, but no explicit body-size cap is set beyond FastAPI's defaults. | Optional: add a small request-body size limit. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| uv run --frozen pytest -q (the six unit-scoped Python test files) | 65 passed | The lesson, puzzle, API, curation and browser tests are green. |
| node --test (hub-tabs, trainer-progress, puzzle-state, trainer-state) | 30 pass, 0 fail | The JS unit tests are green. |

### Summary

The unit is implementable and consistent with its design. `validate_puzzle` replays every move, enforces the mate and player-move counts, and rejects unknown fields. Loading is bounded (2 MB per file, no symlinks, no files opened by a name taken from a request). The puzzle routes are read-only with no runtime downloads. `public_detail` returns the set-up move and the position after it, but never the solution. I checked Legal's Mate and the Fishing Pole lessons move by move: the lines are correct and the notes are in original wording. `puzzles/LICENSE.md` names the Lichess CC0 source, and the credit shows in the UI (`puzzle.js` and `hub.js`). The three findings are minor and none blocks approval.
