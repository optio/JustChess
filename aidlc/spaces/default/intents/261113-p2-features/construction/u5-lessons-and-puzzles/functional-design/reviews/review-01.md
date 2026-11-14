## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-11-13
**Iteration:** 1
**Verdict Dictated:** no

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | aidlc/spaces/default/intents/261113-p2-features/construction/u5-lessons-and-puzzles/functional-design/rules.md > BR2.4 and functional-spec.md > W3 route table | The check route cannot serve Hint or Show solution. It needs a `{ply, uci}` body, yet the first hint press and Show solution happen with no move submitted. `solution?` has no defined shape: it is one move or the whole line. The client needs the whole remaining line to play it at 800 ms per move. Ply validity is also undefined. The server is stateless, so only odd indexes below `len(moves)` can be player plies. `?reveal=1` on a wrong move would also leak the full solution to any caller. | Define a reveal contract. For example, a separate `POST .../hint` that returns the next move, and `POST .../solution` that returns the remaining moves from a given ply. Or state exactly what `check?reveal=1` returns with no `uci`. Define the valid ply values (odd, below `len(moves)`) and the 400 case. State that a mate on a non-final ply counts as solved only when the position is actually checkmate. | New |
| R-02 | Major | aidlc/spaces/default/intents/261113-p2-features/construction/u5-lessons-and-puzzles/functional-design/functional-spec.md > W4.4 | `/learn/tactics/<theme>` is a two-segment page path. The existing app serves only `/learn` and `/learn/{lesson_id}` (`justchess/api.py` lines 419–427). A direct load or refresh of a puzzle URL would return 404. The spec adds no page route and does not say whether puzzle navigation is client-only. | Add a page route for `/learn/tactics/{theme}`, and optionally `/{id}`, that serves `index.html`. Alternatively, say the puzzle screen is reachable only through client navigation and add that to the edge cases. Also say how a lesson id of `tactics` is prevented from clashing. | New |
| R-03 | Minor | aidlc/spaces/default/intents/261113-p2-features/construction/u5-lessons-and-puzzles/functional-design/functional-spec.md > W2.2 and W2.4 | Curation filters on theme, popularity, plays and rating only. BR2.1 then skips any puzzle with more than 4 player moves, an illegal line, or a mate theme that does not end in mate. Sampling before validating can leave a theme under the 250 floor, and the script then fails with no recovery step. The Lichess CSV also needs the FEN, Moves and Themes columns to be read exactly as documented. | Run the BR2.1 validators inside the script before sampling, so 300 valid puzzles are drawn. Write the remedy for under-250 (widen the filter). Say that `Moves[0]` is the opponent's set-up move and that the FEN is the position before it. | New |
| R-04 | Minor | aidlc/spaces/default/intents/261113-p2-features/construction/u5-lessons-and-puzzles/functional-design/rules.md > BR3.2 | "Lesson practice finished without the arrow" has no basis in the code. `static/js/training/trainer-state.js` resets `arrow` and `misses` on completion, and keeps no "arrow was shown" flag. The `complete` phase also has no progress-write effect. | Add a flag to the trainer state, such as `arrowShown`, and an effect that writes progress. Record both as changes to the existing trainer. | New |
| R-05 | Minor | aidlc/spaces/default/intents/261113-p2-features/construction/u5-lessons-and-puzzles/functional-design/functional-spec.md > W1 and W4.5 | The loader's `KNOWN_FIELDS` rejects unknown fields, so `kind` must be added there and to `summaries()`. The client's `isSummary` check in `lessons-api.js` and the `choosing` phase of the existing trainer overlap with the hub's lesson lists. The spec does not say which one owns lesson selection. | Name the exact changes (`KNOWN_FIELDS`, `summaries`, `isSummary`, the `kind` query parameter on `lessons-api.js`). State whether the `choosing` phase stays or is bypassed by the hub. | New |
| R-06 | Minor | aidlc/spaces/default/intents/261113-p2-features/construction/u5-lessons-and-puzzles/functional-design/functional-spec.md > W2.1 | Puzzle generation depends on downloading the Lichess `.zst` dump (hundreds of MB). The tests that require 250–400 puzzles per theme need `puzzles/` committed. There is no fallback if the download is unavailable during Code Generation. | Record who generates `puzzles/` and when. Add a fallback, such as a small hand-verified set that is flagged as provisional, so the build is not blocked. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| traceability.json cross-check | All 8 FR targets name BR IDs that exist in rules.md | OK |
| Reference check against code | Loader, routes and trainer inspected | Gaps are in the findings above |

### Summary

The design is mostly sound and covers FR7, FR8.1 and FR8.3–FR8.6. Licensing, read-only routes and traceability hold up. Two Major gaps should be fixed at the gate: the undefined hint and solution API, and the missing page route for puzzle URLs. The Minor items are cleanups.
