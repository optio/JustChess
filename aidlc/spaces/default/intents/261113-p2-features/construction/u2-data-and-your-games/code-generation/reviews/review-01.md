## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-11-13T00:00:00Z
**Iteration:** 1
**Verdict Dictated:** no

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Minor | static/js/your-games.js > seatsToSend; static/js/seat-store.js > validSeat | The seat store accepts tokens up to 256 characters but the summaries route accepts at most 128. A stored seat with a token of 129 to 256 characters is skipped in the request but never removed from the store, and never appears in the list. BR2.1 says malformed entries are skipped and removed. Real tokens are about 43 characters, so this is unlikely to occur. | Make the seat store's token limit 128, or remove seats that `seatsToSend` rejects. | New |
| R-02 | Minor | static/js/your-games.js > meta | A game in status waiting reads "You play White · last move just now" although no move has been made. | For status waiting, show only "You play <colour>", or the time since the room was created. | New |
| R-03 | Minor | static/js/screens/lobby.js > showFailure | After a failed refresh, rows from the last good answer stay on screen with the "Couldn't refresh" banner. Stale rows built from the stored seats appear only when no rows are shown yet. BR3.3 says to render stored seats as "Couldn't refresh" rows, so this is a different, arguably better, reading of the rule. It is not recorded among the deviations in code-summary.md. | Add this to the deviations in code-summary.md, or follow BR3.3 literally. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| `uv run --frozen pytest -q` (unit-scoped files) | 87 passed | Matches the summary. Covers schema v4 constraints, move-aside and refusal, failed rename, capture info for normal, en passant, promotion and castling, summaries, and the fixed 400 with no token in the logs. |
| `node --test tests/js/your-games.test.mjs tests/js/seat-store.test.mjs` | 15 passed | Matches the summary. |
| Real `justchess.sqlite3` size and modification time, before and after my run | Unchanged | The tests use `tmp_path` databases and do not touch the real file. |

### Summary

I found no Critical or Major findings. The implementation matches BR1.1 to BR3.6, and the deviations are sound.

- **Schema v4:** the CHECK constraints are right. Start-up keeps v4, refuses a newer version without moving the file, moves older or unreadable files to `.old`, and stops on a failed rename.
- **Capture info:** en passant uses the passed pawn's square, promotion captures are recorded, and castling stores none.
- **Summaries route:** tokens travel only in the request body. Comparison is constant-time over every seat. An unknown room and a wrong token give the same `found:false` answer. The 400 message is fixed. The route's 8 KB body limit is per-path. The route runs in one rolled-back read transaction and touches no last-seen or last-activity time.
- **Client:** seats are reconciled by position and `remove(code, token)` only removes a matching token. A refresh keeps at most one request in flight and keeps focus on the same row.

The three Minor items above are cosmetic or edge cases.
