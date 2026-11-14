## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-11-13
**Iteration:** 1
**Verdict Dictated:** no

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | aidlc/spaces/default/intents/261113-p2-features/construction/u2-data-and-your-games/functional-design/traceability.json > upstream_ids and coverage | FR1.5 (single-player games appear in the same list) is assigned to U2 in unit-of-work.md and is cited as a source of BR2.2 in rules.md, but it is missing from upstream_ids and coverage. NFR4 (tokens never in URLs or logs), which BR2.1 cites, is also missing. | Add FR1.5 with OK targets BR2.2 and BR3.2. Add NFR4 with target BR2.1, or state why it is out of the matrix. | New |
| R-02 | Minor | aidlc/spaces/default/intents/261113-p2-features/construction/u2-data-and-your-games/functional-design/functional-spec.md > W4 table, "Malformed body", and BR2.1 | The 400 answer carries a free-text `detail`. If it is built from framework validation errors, it can echo the submitted tokens. This would break the rule that tokens never appear in logs. | Say that `detail` is a fixed message that never contains submitted values. Add a test that a 400 response and the logs contain no token. | New |
| R-03 | Minor | aidlc/spaces/default/intents/261113-p2-features/construction/u2-data-and-your-games/functional-design/rules.md > BR2.1 and BR3.3 | One malformed stored seat (for example a bad code or an over-long token) makes the whole batch return 400. BR3.3 keeps every seat on a 400, so the list never loads again. The only recovery is clearing browser storage. | Have the client validate each seat's shape before sending and drop or skip entries that are malformed. Alternatively have the server answer `found:false` for a bad entry instead of rejecting the whole body. | New |
| R-04 | Minor | aidlc/spaces/default/intents/261113-p2-features/construction/u2-data-and-your-games/functional-design/functional-spec.md > W4 step 2 | "Each distinct code" does not say what happens when the same code appears twice with different tokens. This can happen when one browser holds both seats of a room (U3 pass-along). It is not clear which token is used or whether the answer is the seat A or seat B view. | Dedupe by code and token pair, or state which seat wins. | New |
| R-05 | Minor | aidlc/spaces/default/intents/261113-p2-features/construction/u2-data-and-your-games/functional-design/rules.md > BR2.2 and BR3.2 | The summary has no `result` for a finished game with no result (for example `abandoned`). BR3.2 has no pill for a game still in status `waiting` or for a finished game without a result. Those rows have no defined pill. | Define the pill or the result for a finished game with no result, and for a `waiting` game. | New |
| R-06 | Minor | aidlc/spaces/default/intents/261113-p2-features/construction/u2-data-and-your-games/functional-design/functional-spec.md > W5 state diagram | The list goes to Empty only when every seat comes back `found:false`. If every found game is filtered out by BR3.1 (older than 7 days), the list renders no rows and the state is not named. The Stale rows on a first-load failure have only the code, kind and level to show, and no layout is given for them. | Say that an empty filtered result also shows the Empty panel. Say what a Stale row shows when it has no live data. | New |
| R-07 | Minor | aidlc/spaces/default/intents/261113-p2-features/construction/u2-data-and-your-games/functional-design/rules.md > BR1.1 and functional-spec.md W1 | The old database is overwritten if a `.old` file exists. The spec also moves aside a file with a newer version than 4, where the current code in `justchess/db.py` refuses to start. A rollback of the code would therefore destroy newer data. The rename failing (for example for permissions) is not specified. | Record this as accepted under NFR7, or refuse a newer version. State that a failed rename raises DatabaseStartupError. | New |
| R-08 | Minor | aidlc/spaces/default/intents/261113-p2-features/construction/u2-data-and-your-games/functional-design/rules.md > BR2.1 | The size limit is a single global constant, `MAX_BODY_BYTES = 4096` in `justchess/security.py`. "Raised for this route to 8 KB" does not say how a per-route limit is done. Fifty entries with a 128-character token come to about 7.5 KB, close to the limit. Nothing limits how often a client can call the route, and each call loads up to 50 rooms. | State how the per-route limit is set (a route-aware parameter on the size-limit middleware). Note that rate limiting arrives with U3. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| Manual cross-check of traceability.json against unit-of-work.md U2 and requirements.md | FR1.1–FR1.4 and FR2.1 resolve to BR IDs in rules.md. FR1.5 and NFR4 are missing. BR1.1 is explained in reverse as NFR7 (N/A). | One Major finding (the traceability gap above). The BR1.1 reverse entry is acceptable. |
| Code check (`justchess/security.py`, `justchess/api.py`, `justchess/db.py`) | The origin check and size limit exist. `POST /api/rooms/summaries` does not clash with the existing `/api/rooms/{code}/...` routes. The schema is version 3 with in-place upgrade code that this design removes. | The design is feasible against the current code. |

### Summary

The design is implementable. The rules are mostly testable, and security is sound on tokens in the body and no existence oracle (a wrong token and an unknown room get the same answer). One Major finding remains, which is the missing FR1.5 and NFR4 rows in the traceability matrix. The Minor findings are edge cases to settle before or during Code Generation.
