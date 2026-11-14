## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-11-12T00:00:00Z
**Iteration:** 1
**Verdict Dictated:** no

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | static/js/app.js:250-304 (openRoom), :384-409 (onMove); static/js/hooks.js:41-49; tests/js, tests/test_game_screen.py | The riskiest decisions in the plan's findings table have no test that runs them. Nothing tests `runBeforeMove` failing closed (no test mentions `beforeMove`). Nothing tests the stale-seat notice, the 409 room-full path that removes a stored seat, the continue-fragment redeem, a 403 "This isn't your seat" action, or a move that gets 400 or 409. Node tests cover the reducer and view model only. The one browser test is a happy-path Fool's mate and is skipped when Chromium is missing. | Add Node tests that run `startApp` or `openRoom`/`onMove` with fake `fetch`, `WebSocket` and storage. They should cover: a stale stored token, 409 with a stored seat, a redeem of 200/404/network/expired, a 403 seat refusal, a move answered 400 and 409 (board rejected, snapshot applied), and a throwing `beforeMove` hook. Add a small `hooks.test.mjs` for fail-closed behaviour. | New |
| R-02 | Minor | static/js/app.js:312-326 (route), :463-468 | When the address is `/r/<invalid>#continue=<token>`, the code is invalid so the screen goes to the lobby. The fragment is never stripped, so the one-time token stays in the address bar and history, contrary to the "stripped before use" claim in the header comment. | In `route()`, strip a hash with `replaceState` before the lobby is shown, whenever one is present. | New |
| R-03 | Minor | static/js/app.js:83-105 (showScreen), :177-196 | Focus is not managed when the screen changes. After Start a game, Join or the home link, the focused button is removed and focus drops to the page start. `<main tabindex="-1">` exists but is never focused. The game screen also has no `h1`. | Move focus to `#app`, or to the new screen's heading, after a route change. Give the game screen a visually hidden `h1`. | New |
| R-04 | Minor | templates/index.html:44; static/js/screens/game.js:123; static/js/app.js:115-119 | Each snapshot changes both the `role=status` status line and the `#announcer` region, so screen readers hear moves and game over twice. Both regions are specified, but their combined effect is not. | Limit the announcer to the sentence the status line lacks. Or make the status region `aria-live="off"` while the announcer speaks. | New |
| R-05 | Minor | static/js/live.js:206-215; justchess/live.py:230 | The client pings every 5 s but the server never replies, and the client has no idle timeout. A silently dead socket, as after a phone sleeps, never shows "Reconnecting…" until the browser reports the close. The move version check still keeps the board safe. | Record the limit in the design. Optionally treat a long silence after a visibility change to visible as a reason to reconnect. | New |
| R-06 | Minor | static/js/screens/win-sequence.js; static/js/screens/overlay.js; tests/js | The win sequence, the reduced-motion and instant paths, and overlay focus have no Node test (a DOM fake or a `matchMedia` stub would do). The single browser run uses default motion, so BR4.1 is not exercised under reduced motion. The `is-tipped` and `is-glow` classes live on U2's piece images, and nothing checks they survive a board redraw. | Add tests for `playWinSequence` with `instant: true` and with stubbed reduced motion. Check that `clear()` removes every trace and that `cancel()` leaves the end state. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| `node --test tests/js/` | PASS: 71 tests, 0 fail, 0 skipped | Includes the contrast pairs for labels under the last-move highlight. The U3 view-model, reducer, API, live, seat-store and share tests are meaningful, with no always-pass assertions. |
| `uv run --frozen pytest -q` | PASS: 56 passed in 8.08s | The two-player Chromium test ran (chromium is installed): create, join by link, Fool's mate, overlay and focus on Play again, result 0–1, rematch with swapped colours, phone and desktop layout limits, and no console errors. |

Verified against the plan's findings table:
- State after join: the join answer is followed by a `state()` read with the `X-Seat-Token` header (app.js:298). The 409 snapshot is drawn as the watcher view.
- Stale seat: the notice, removal and replacement paths are implemented (app.js:266-290); see the Major finding for the missing tests.
- Screen-state reducer: it has a separate connection flag, and "Game over" comes first in the status (view-model.js:140). Snapshots re-derive the base view, and seat-moved and seat-lost move every room view to `watching`.
- Other table rows: `claimableDrawReason` is mapped (games.py:226 and :348). Result glyphs are correct. `lastMove` is passed as UCI. Legacy fields are removed; the HTTP test checks that.
- `beforeMove` is `Promise<boolean>` and strict-true, so it fails closed (hooks.js:44).
- Overlay: it is `role=region` and labelled; focus goes to Play again and returns to the board on a new game. On phones it sits between the board and the status; on desktop it sits over the lower third of the board.
- Security and storage: tokens go in bodies, the header and the socket `hello`, never in a URL or a log. A valid continue fragment is stripped before any network call (app.js:254). Storage falls back to memory with a notice.
- Live client and layout: `hello` carries the token, pings run every 5 s, visibility is sent, and backoff is 1, 2, 4, 8, then 10 s. Equal-version snapshots pass in both `live.js` and the reducer, matching the documented rationale. The browser run confirmed the top bar is at most 56 px, the phone board top is at most 72 px, the phone board is at least 374 px wide, and the desktop board is 560–640 px wide.
- README and manifest claims match the code.

### Summary

The build is implementable and matches the plan's design-review resolutions. Both validation commands pass, and the browser test runs for real. The one Major finding is test coverage: the stale-seat, 409, redeem, seat-refusal and move-failure orchestration in `app.js`, and the fail-closed move hook, are verified by no test. The other findings are Minor.
