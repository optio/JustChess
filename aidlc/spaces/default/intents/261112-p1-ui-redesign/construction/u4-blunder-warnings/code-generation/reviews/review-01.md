## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-11-13
**Iteration:** 1
**Verdict Dictated:** no

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Minor | static/js/hooks.js > runBeforeMove (lines 62-69) | The widened hook result is documented as `{allow: false, ...}`, but any object is treated as a refusal and the `allow` field is never read. A hook that returned `{allow: true}` would silently refuse the move. No current hook does this. | Either read `allow` (an object with `allow: true` allows the move) or state in the header that the object form always refuses. | New |
| R-02 | Minor | static/js/blunder.js > decide (line 144) and static/js/room-flow.js > submitMove (lines 135-139) | A 403 from check-move is turned into a flash message only. The 403 "This isn't your seat" case that `actionAnswer` handles for `/moves` (forget the seat and token, then watch) is not reached on the check path. The following real move POST would still hit that path. | Optional: when the check answers 403 with the seat-refused text, skip the check and let the move POST take the existing seat-lost path. Otherwise record it as accepted. | New |
| R-03 | Minor | tests/test_check_move_api.py > test_the_check_answers_within_300_ms (lines 193-203); tests/test_analysis.py > test_an_exhausted_budget_keeps_the_warning (line 149) | The timing test uses wall-clock asserts on the max of 5 runs. Measured 4-9 ms, so it is robust today. The "every move allows mate" fixture has only 2 legal moves, so the sweep's worst case (many legal moves, none free) is not timed. The budget path is only tested with `budget_ms=0`. The code summary already admits the 2-move fixture. | Add one analysis-level test with a position of 30 or more legal moves where no move is free, asserting that `analyse` returns within the budget plus a margin. Keep the route timing test as is. | New |
| R-04 | Minor | justchess/analysis.py > analyse (lines 333-337) and `_Clock` | The 250 ms budget bounds only the no-alternative sweep. The before-position scan, the mate scan and the first `new_hanging(move)` are not budgeted. They cost under 1 ms in practice (a 84k-move random-position run had a maximum of 5.9 ms), so this is documentation only. | Say in the module header that the budget covers the sweep, not the scans before it. | New |
| R-05 | Minor | justchess/api.py > check_move (lines 479-497) | Each check runs in the default thread pool, which is shared with Stockfish preparation, and there is no per-room or per-seat cap. A seated client can queue many analysis threads on a Pi. The cost per check is low and the route is token-gated, so this is a hardening note only. | Optional: note it in the README or code summary, or add a small concurrency limit if a limit is wanted later. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| `node --test tests/js/` | PASS: 115 tests, 0 failed, 0 skipped | Matches the code summary's 115 (100 before the unit). |
| `uv run --frozen pytest -q` | PASS: 121 passed in 19.39 s | Matches the code summary. The timing test printed: busy middlegame median 4.3 ms and max 4.9 ms; every-move-allows-mate median 6.1 ms and max 8.5 ms, against the 300 ms budget. |
| Own chess checks (python-chess, scratch scripts) | Positions checked: Fool's mate g4 gives mate_in_one Qh4#; a rook trade gives no warning; a queen taking a pawn defended by a pawn gives hanging; an x-ray rook behind a rook is handled by pushing real captures; en passant gives no warning; a defended queen promotion (d7xe8=Q with Rf8 and Re1) gives none, while an undefended d8=Q gives hanging by Rf8; mover in check gives none. Random-game cross-check: 84,447 judged moves with no exception and a maximum of 5.9 ms (14,304 warnings). 340 mate warnings were all confirmed by brute force. In 934 sampled positions where the move allows a mate and no mate warning was given, every case was explained by a mate threat that already existed (before position, null move) or by every other move also allowing mate. | The mate scan restricted to checking replies is complete for mate in one. SEE, offset, identity and mover-in-check behave as the plan states. |

### Summary

The unit is implementable and correct as built. I found no Critical or Major problems. The checking-replies-only mate scan, the legal-capture exchange evaluation, the promotion offset, the before/after identity and the per-kind sweep all behave as designed on my own positions and on a large random cross-check. The route reads under the room lock only, in U1's real order (seat, playing, version, turn, legality), and analyses in a worker thread outside the lock. The hook maps every failure as planned and never throws. The widened hook result is handled in `runBeforeMove`, `submitMove`, `applyRefusal` and `app.js` without breaking the existing tests. The dialog has the required alertdialog semantics, a focus trap, capture-phase Escape and focus return. The findings above are Minor polish.
