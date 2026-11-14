## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-11-14T00:00:00Z
**Iteration:** 1
**Verdict Dictated:** no

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Minor | justchess/housekeeping.py > run_lapse; code-summary.md deviation 1 | Hourly housekeeping lapses expired requests without a broadcast, so a creator whose page lacks the local countdown (or an older client) can see a stale banner until the next read. The on-read lapse and the page's own countdown cover the normal case. | Accept as documented, or broadcast after the hourly lapse if the hub can be reached. | New |
| R-02 | Minor | justchess/rooms.py > RequestAddressBook; justchess/api.py > _ask_to_join | The address is recorded and the decline block is in memory only, so it resets on restart. A mode switch to waiting declines a pending request without blocking the address, which differs slightly from an explicit decline. | Keep as a documented deviation; note the mode-switch case in the README or rules. | New |
| R-03 | Minor | justchess/ratelimit.py > client_address | When the peer is a trusted proxy and a malformed X-Forwarded-For hop is found, the code returns the proxy address. All clients behind that proxy then share one rate window. | Document this fail-closed behaviour next to JUSTCHESS_TRUSTED_PROXIES. | New |
| R-04 | Minor | justchess/api.py > join_request_status | The status poll has no rate limit. It is bounded by a 256-character token and a hash lookup scoped to the room, so it is not an existence oracle, but it can be called freely. | Optional: add a generous per-address limit later. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| uv run --frozen pytest (the unit-scoped files) | 73 passed | The unit's Python tests are green. |
| node --test pass-along and room-flow | 19 passed, 0 failed | The front-end logic is green. |

### Summary

I read each rule against the code. The checks around the room lock are sound:
- Mode, join, answer and status all run through `mutate` under the room lock.
- The partial unique index `join_requests_one_pending` backs the one-pending rule.
- Accept re-checks mode, seat B and expiry (stale accept gives 409), and `mark_counted` skips finished games.
- One-seat "Play again" requires seat A, pass-along mode and a finished game.

The security checks hold:
- Only seat A can switch the mode or answer a request (403 otherwise).
- Only the hash of the request token is stored.
- The token travels only in request bodies and is not logged.
- Rate limiting uses a sliding window with bounded memory, and trusted-proxy parsing takes the rightmost untrusted hop.

Only minor, documented gaps remain.
