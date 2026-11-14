## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-11-14T00:00:00Z
**Iteration:** 1
**Verdict Dictated:** no

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | aidlc/spaces/default/intents/261113-p2-features/construction/u6-endgame-trainer/functional-design/rules.md > BR2.2 and BR2.3 | Neither rule handles the defender being checkmated. A player mate in a promote or draw goal falls through to "playing", so the server asks the engine for a move on a finished board. The engine raises no-legal-move, the route answers 503, and the attempt can never finish. | Add a defender-checkmated branch to BR2.2 and BR2.3 (draw goal: passed; promote goal: passed or failed, state which). Add a catch-all so a finished board is never sent to the engine. Add the case to the judging tests. | New |
| R-02 | Major | aidlc/spaces/default/intents/261113-p2-features/construction/u6-endgame-trainer/functional-design/rules.md > BR3.3 and functional-spec.md > Decisions "Waiting is shown as thinking only" | The play route submits to the shared engine until the queue holds 32 requests. Hints are refused at `hint_refusal_queue` (16) so computer-room replies keep their place. Each endgame request costs 1 s, and one address may send 30 a minute, which is about half of the engine. Endgame play can fill the queue and starve live computer games. | Refuse endgame plays once `queued_count()` reaches `hint_refusal_queue`, as hints do, or give them their own lower threshold in the `endgames` settings. Add a test for it. | New |
| R-03 | Minor | aidlc/spaces/default/intents/261113-p2-features/construction/u6-endgame-trainer/functional-design/functional-spec.md > API summary (413 over 8 KB) and rules.md > BR3.2 | `BodyLimitMiddleware` overrides match an exact path, and the play path contains the position id, so an 8 KB override cannot be set. The default is 4 KB. A 300-ply list is about 2.7 KB, so 4 KB already holds it. | State that the default 4 KB limit applies and drop the 8 KB figure. Or extend the middleware to match a path pattern, and say so in the design. | New |
| R-04 | Minor | aidlc/spaces/default/intents/261113-p2-features/construction/u6-endgame-trainer/functional-design/entities.md > Verdict.reason | The enum lists `defender_promoted_mate`, which no rule produces. BR2.1 returns `draw_not_enough` "with the draw kind in the message", while the enum also lists specific draw reasons. The two ways of reporting a draw are inconsistent. | Remove the unused value. Choose one way to report a draw (specific reason, or `draw_not_enough` plus detail) and make BR2.1 to BR2.3 and the client text match. | New |
| R-05 | Minor | aidlc/spaces/default/intents/261113-p2-features/construction/u6-endgame-trainer/functional-design/functional-spec.md > W2 and BR3.3 (disconnect cancel) | The existing `_await_hint` raises a 409 "hint cancelled" error, and the design reuses it without saying so. | Say that a neutral wait helper is extracted or parameterised so no hint wording leaks into the endgame route. Also note that a request can wait behind up to 32 searches, so state a bound on the wait or accept it. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| none listed for this stage | not run | Reviewed by reading against `justchess/engine.py`, `security.py`, `api.py` and `gameplay.yaml`. |

### Summary

The design is implementable and its stateless trade-off is sound. A forged history only affects per-device progress, legality is still checked, and ids never reach file paths. The two Major points to fix before code are the unhandled "defender checkmated" case in the promote and draw goals, and the missing queue-priority threshold that protects live computer games. With two Major findings the verdict stays READY.
