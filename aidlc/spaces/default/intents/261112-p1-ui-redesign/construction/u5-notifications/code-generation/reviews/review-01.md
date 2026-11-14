## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-11-13
**Iteration:** 1
**Verdict Dictated:** no

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | justchess/notifications.py:241-264 `validate_endpoint` and `host_allowed` (217-226); tests/test_notifications.py:222-237 | The endpoint allowlist can be bypassed with a backslash in the host. I ran `validate_endpoint("https://127.0.0.1\.push.apple.com/x")` and it was accepted: Python's `urlsplit` reads the host as `127.0.0.1.push.apple.com`, which matches `*.push.apple.com`, and the IP-literal check never fires because the string is not an IP. `requests` and urllib3 parse the same URL as host `127.0.0.1` (confirmed with `urllib3.util.parse_url`), and `evil.com.push.apple.com` resolves to `evil.com` the same way. Any anonymous player can create a room, post such an endpoint, and have the server send a blind HTTPS POST on port 443 to a loopback, internal or arbitrary host. This defeats the SSRF control the plan promised: allowlist, IP literal and port checks. The parametrized refusal list has no case for it. | After the existing checks, require the hostname to match a strict pattern (`^[a-z0-9]([a-z0-9-]*[a-z0-9])?(.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$`). This refuses ``, `%`, `!` and similar characters. Also compare the host urllib3 would use against the one validated. Add refusal tests for `https://127.0.0.1.push.apple.com/x`, `https://evil.com.push.apple.com/x` and `https://a.b!.push.apple.com/x`. Do this before approval. | New |
| R-02 | Minor | justchess/notifications.py:406-423 `WebPushSender.__call__` and 469-483 `_send_all`; 443-459 `dispatch` | The sender catches only `WebPushException`, `requests.RequestException`, `ValueError` and `TypeError`. Any other exception from py_vapid or cryptography escapes `_send_all` and `dispatch_safely` logs it. The claim then stays `claimed` forever, the seat's remaining subscriptions get nothing, and subscriptions already found gone are not deleted. "Stuck claims are never resent" was meant to cover a crash, not an ordinary exception in a loop. | Catch `Exception` per subscription in `_send_all`, log only the exception type and host, count the subscription as failed, and carry on so `_finish` always runs. Add a test with a sender that raises. | New |
| R-03 | Minor | justchess/db.py:275-278 `prepare_database`; tests/core/test_db.py | A database with a schema version newer than 3 now stops startup. Before U5, any non-current file was moved aside. The plan's table only says versions below 2 and unmarked files are moved aside, and no test covers a newer file. The behaviour is defensible but unrecorded. | Record the decision in the code summary and README, and add a test for a version-4 file. Or restore move-aside for newer files if BR4.1 requires it. | New |
| R-04 | Minor | aidlc/spaces/default/intents/261112-p1-ui-redesign/inception/domain-design/decisions.md ADR-006 (lines 64-73); code-summary.md "ADR-006 amendment" | The plan says the ADR-006 amendment is recorded in the code summary and README, and it is (README.md:43). ADR-006 itself still says "no data migration" and the log of ADR decisions is unchanged. A reader of the shared contract gets the wrong rule for version 2 files. | Add a one-line "Amended by U5" note to ADR-006 at the next decisions update, or point the README text at the ADR so the two cannot drift. | New |
| R-05 | Minor | static/js/notifications.js:188-201 `disable`; justchess/notifications.py:324-328 | Turning notifications off unsubscribes the browser and posts the endpoint for the current room only. The same endpoint stays stored for the person's other rooms until a push to it returns 410 and the housekeeping or send path removes it. The result is correct, because the push service refuses the dead endpoint, but until then the server holds live-looking rows for a device that turned alerts off (BR3.4). | Optionally add a delete by endpoint across all of this client's rooms, or document that other rooms clean up on the first 404/410. | New |
| R-06 | Minor | justchess/vapid.py:140-155 `_read_key_file` | The key file is refused when inside the project, but its permissions are not checked. A group- or world-readable key file loads without a warning. The generator writes 0600, but a hand-made file may not. | Log one warning (path only) when the mode allows group or other access. | New |
| R-07 | Minor | pyproject.toml:8,13 | The dependency diff changes `fastapi` to `fastapi[standard]` and adds `pyyaml`. Only `pywebpush` is a U5 dependency, and the plan does not mention the other two. They may belong to another unit, but this unit's manifest lists `pyproject.toml` and `uv.lock` as its own writes. | Confirm which unit owns `fastapi[standard]` and `pyyaml`. If neither is needed here, drop them from this unit's manifest or explain them in the code summary. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| `node --test tests/js/` | PASS: 130 tests, 0 failures, 0 skipped | Includes notify-core and notifications tests. The check that `static/sw.js` and `notify-core.js` carry identical shared blocks passes. |
| `uv run --frozen pytest -q` | PASS: 169 passed in 26.97 s | Whole suite green, so the existing tests are intact. |
| Endpoint probe (`validate_endpoint` against `requests.Request(...).prepare()` and `urllib3.util.parse_url`, no network) | FAIL for backslash hosts | Confirms the Major finding. Only the backslash variants and `a.b!.push.apple.com` were wrongly accepted. Other bypass attempts (user info, trailing dot, port, `%2f@`) were refused. |

### Plan findings table: verified against the code

| Plan decision | Result |
|---|---|
| Fresh-visible rule and `last_heard` | Met. `live.py:96-99` and `247-251` set `last_heard` on hello, ping and visibility. `api.py:169-172` reads presence in the handler. The page sends `visibility: false` on `pagehide` (`live.js:58-68`). |
| A hidden page always shows a local notification, with a shared tag | Met. `decide` returns `local` for a hidden page whenever the setting is on and permission is granted. Tag is `<code>:<key>` with `renotify: false` on all three paths. |
| SSRF: allowlist, port, IP literal, userinfo, no redirects | Mostly met. Redirects and the other checks are tested, but the backslash bypass in the Major finding defeats the allowlist. |
| Background dispatch, presence read in the handler | Met. `schedule_alert` captures presence before the response. The worker runs in `asyncio.to_thread` and never reads hub state. |
| Tag includes the room | Met. Server `AlertEvent.tag`, `notify-core.make` and `sw.js` all agree. |
| v2 to v3 upgrade in one transaction | Met. `_upgrade_in_place` creates both tables and bumps the version in one transaction; a rollback test exists. The ADR text is only partly updated (see the Minor finding). |
| Seat transfer deletes subscriptions | Met. It runs in the same transaction as the continue redeem (`api.py:529-530`) and is tested. |
| Unsubscribe requires an endpoint | Met. 400 without one (`api.py:683-684`). |
| Client key derivation | Met. `eventFor` uses snapshot fields only (`code`, `game`, `status`, `endReason`, `result`, `turn`, `seats`, `moveList`). I checked them against `games.py:352-375`. The target colour logic matches the server for move ends, claimed draws and abandonment. |
| VAPID formats, realpath, rotation cleanup, generator refuses in-repo paths | Met. PEM and raw base64url keys load, `is_inside` resolves symlinks, and 400/403 key mismatches delete the subscription. The generator writes mode 0600 with `O_EXCL`. |
| De-duplication across paths | Sound. `INSERT OR IGNORE` on (room, slot, key) is the single claim. Client `shownKeys` and the shared tag cover the page and push paths. The remaining double alert (a visible page whose socket is older than 6 s) is shown silently by the service worker. |
| Secrets in logs and in the repo | No endpoint, key or token is logged; the log test covers the dispatch path. No private key is tracked, and the key file must be outside the project. |
| Service worker and click URL | Safe. The click path is rebuilt from a validated 6-character room code, and a URL taken from the payload is never opened. Every push shows a notification. |
| Cascade delete decision | Sound. Housekeeping runs `delete_room_data` first, and `ON DELETE CASCADE` with `foreign_keys = ON` is the safety net. |

### Summary

The unit is close to done: both test suites pass, the plan's decisions are implemented, and de-duplication holds across the push, local and banner paths. One exploitable gap remains in the endpoint allowlist, which a backslash in the host defeats; it has a small fix and should be closed before approval. The remaining findings are minor.
