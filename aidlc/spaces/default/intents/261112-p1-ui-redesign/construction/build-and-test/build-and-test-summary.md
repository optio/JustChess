# Build and Test Summary — JustChess P1 redesign

## Build status

- **Build:** passed. There is no compile step. `uv sync --frozen` is satisfied, and the app starts through `create_app`.
- **Prerequisites:** Python 3.11+ with uv, and Node 20+ for the frontend tests. Chromium is optional and only needed for the browser checks.

## Test types run

| Type | Where | Run 2 result |
|---|---|---|
| Unit (Python): rules, rooms, games, analysis, lessons, notifications | pytest | passed |
| Unit (frontend logic): board geometry and interaction, settings, view model, screen state, trainer, blunder hook, notification decisions, contrast | Node `node --test` (logic only, no DOM) | 130 passed |
| Integration over HTTP and WebSocket | FastAPI TestClient | passed |
| Integration against a real server: concurrency, delivery time | uvicorn plus threads and sockets | 3 passed |
| End-to-end in a real browser engine: two-player game, blunder dialog, trainer, background notification, phone-width accessibility | headless Chromium | passed |
| Real Web Push | headless Chromium plus a vendor push service | **skipped**: this Chromium build cannot subscribe |

Totals: **177 passed, 1 skipped** (`uv run --frozen pytest -q`), plus **130 passed** in Node.

## Coverage expectations

No coverage floor applies. The scope is refactor, and no team or project rule sets one. The Standard strategy's volume of 5–8 tests per component, plus integration tests at the key boundaries, is met in every unit (see each unit's `unit-test-instructions.md`).

## Target Verification Matrix

| Target ID | Source | Expected | Actual | Evidence | Owning Stage | Verdict |
|---|---|---|---|---|---|---|
| TC-STRATEGY | All units' Testing Contract (standard) | 5–8 tests per component, plus integration at key boundaries | Met in every unit (per-unit tables); integration in `integration-test-instructions.md` | per-unit `unit-test-instructions.md`, test files | build-and-test | Met |
| TC-SCOPE-GREEN | Testing Contract scope floor (refactor) | Existing suite stays green | 177 passed, 1 skipped; 130 passed | `test-results.md` run 2 | build-and-test | Met |
| TC-CI | org Testing Posture (CI before merge) | n/a | The plan runs no CI Pipeline | `aidlc-state.md`: ci-pipeline SKIP | — | N/A |
| NFR1 | requirements.md | A move with only the room code is rejected | 403 without a valid seat token | `tests/core/test_api.py`, `tests/core/test_rooms.py` | build-and-test | Met |
| NFR2 | requirements.md | Database holds no plaintext token; invite links hold only the code | Only SHA-256 hashes stored; tokens kept out of URLs and logs | `tests/core/test_rooms.py` (hash-only), `tests/js/api.test.mjs` (no token in URLs), `tests/test_notifications.py` (logs) | build-and-test | Met |
| NFR3-NOTE | requirements.md | A deployment note lists the HTTPS options | README "Notifications" section and `build-instructions.md` | README.md | build-and-test | Met |
| NFR3-PUSH | requirements.md | Push works on localhost | Not observed: this machine's headless Chromium refuses push registration (`AbortError: Registration failed - permission denied`) | `tests/test_push_e2e.py` (skipped) | build-and-test | Unverified |
| NFR3a | requirements.md | No private key in the repository; clear log line and push off when keys are missing | Key scan found none; missing key logs a warning and returns 404 on `/api/push/key` | grep scan in `test-results.md`; `tests/test_notifications.py`, `tests/test_push_api.py` | build-and-test | Met |
| NFR4 | requirements.md | Concurrent joins seat one Black; concurrent moves apply one | 8 joiners × 5 rounds gave 1 seat each round; 4 moves × 5 rounds gave 1 applied each round; never a 500 | `tests/test_nfr_integration.py` (real server, threads) | build-and-test | Met |
| NFR5 | requirements.md | 95% of moves reach the opponent within 1 s on LAN or 4G under 100 ms latency | Server-side delivery p95 22.7 ms (median 18.4, max 47.4) over 40 moves on the host; adding a 100 ms network budget stays far below 1 s | `tests/test_nfr_integration.py` | build-and-test | Met |
| NFR6 | requirements.md, accessibility-checklist.md | AA contrast in both themes; 44 px targets; keyboard play; square labels; status never colour-only | 0 contrast failures over every token pair; at 390 px squares are 46 px (44.25 px with frame labels) and the logo link is 44 × 44; Enter and arrow-key play works; every square named | `tests/js/contrast.test.mjs`; `tests/test_accessibility_browser.py` (Chromium); `tests/test_game_screen.py` | build-and-test | Met |
| NFR8a | requirements.md | Foreign-origin requests refused | 403 on POST and on the socket | `tests/core/test_api.py`, `tests/core/test_live.py`, `tests/test_push_api.py`, `tests/test_lessons_api.py` | build-and-test | Met |
| NFR9 | requirements.md | Suite passes with `uv run pytest`; each named area has at least one test | All areas covered; suite passes | `test-results.md` run 2 | build-and-test | Met |
| U4-BR2.2 | u4 rules.md | Blunder check p95 ≤ 300 ms on the host | 4–9 ms | `tests/test_check_move_api.py` | build-and-test | Met |

## Readiness

- **Build-ready:** yes.
- **Test-ready:** yes. 177 Python and 130 Node tests pass.
- **Deployment-ready:** for localhost and LAN play over plain HTTP, yes. Web Push still needs a check on a browser with a push service, then HTTPS hosting, which is still an open decision.

## Known limitations and open items

- **NFR3-PUSH is Unverified.** A real push could not be shown on this machine, because Debian's headless Chromium refuses push registration. Everything up to the push service is tested: subscription storage, signing, the send path with a faked transport, and the service worker showing a notification.
- **U1's written check order (BR2.1) differs from the code.** The code checks version before turn, so a stale request from the wrong seat gets 409 with a snapshot instead of 403. Every client handles both answers. This is recorded here as an accepted deviation.
- **Piece-set licence credit.** The UI shows "CC BY-SA 3.0", but the lichess copy is marked GPLv2+. The owner still has to decide.
- **Accepted reviewer minors:**
  - The demo page's self-check counter omits the arrow pairs.
  - On phones narrower than about 332 px, the trainer drawer scrolls sideways.
  - The 50-move draw claim is tested on a position built directly, not by replaying 100 moves.
