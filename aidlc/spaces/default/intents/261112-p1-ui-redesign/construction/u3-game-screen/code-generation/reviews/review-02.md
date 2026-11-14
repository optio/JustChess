## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-11-13
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
| R-07 | Minor | static/css/app.css:134-147 (frame-label branch) | With frame labels at 390 px the squares are 44.25 px. This meets NFR6 (44 px) but not the checklist figure of 46 px on 374 px boards. The code comment records the 44.25 px figure, but the plan does not record it as a deliberate deviation from the checklist. | Note in code-summary.md that frame-label mode is held to the 44 px floor, not 46 px. | New |
| R-08 | Minor | tests/test_game_screen.py:446-457 | The new layout assertions cover only the game board and the home link. The same phone rules also change `.lobby-board`, including frame-label mode, and no test covers that. | Add a 390 px lobby assertion for square size in both label modes, or state that the browser test's small-target scan is the intended lobby guard. | New |
| R-09 | Minor | static/css/app.css:135 | `.lobby-board` becomes `width: auto; max-width: none` with a -8px margin below 768 px. The 374 px frame width is asserted only for the game board. | Assert the lobby frame width at 390 px, or confirm it from a screenshot. | New |

> R-01 Not re-checked this round

> R-02 Not re-checked this round

> R-03 Not re-checked this round

> R-04 Not re-checked this round

> R-05 Not re-checked this round

> R-06 Not re-checked this round

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| `uv run --frozen pytest tests/test_game_screen.py tests/test_accessibility_browser.py -q` | 11 passed in 20.33s | The 46 px and 44 px square checks, the 44 px home link and the keyboard-play test all pass. |
| `uv run --frozen pytest -q` | 177 passed, 1 skipped, 2 warnings | The suite is green and the repair caused no regression. The warnings are a websockets deprecation in test_nfr_integration.py. |

### Summary

The repair is scoped to a phone-only `@media (max-width: 767px)` block, so desktop and tablet behaviour is unchanged. The test at tests/test_game_screen.py:458 still asserts the 6px frame padding on desktop. The arithmetic matches the Build and Test diagnosis. Inside labels give a 368 px grid and 46 px squares. Frame labels give a 354 px grid and 44.25 px squares, and the frame stays 374 px wide. The Enter key change in tests/test_accessibility_browser.py:31-37 matches real browser key events, because a real Enter keydown carries "\r" text. It also does not weaken the assertion, because the test still checks that focus moves to e4 and that black receives the move.
