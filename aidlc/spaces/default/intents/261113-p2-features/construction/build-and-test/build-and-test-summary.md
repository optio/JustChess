# Build and Test Summary — JustChess P2

## Build status
**Success.** There is no compile step: Python runs from source and the front end is native ES modules. Dependencies are installed with `uv sync --frozen`. See `build-instructions.md`.

## Test types generated
- **Unit tests** for each Unit (pytest and node:test), listed in each Unit's `unit-test-instructions.md`.
- **Integration tests** (TestClient, temporary database, fake engine), described in `integration-test-instructions.md`.
- **End-to-end tests in a real browser engine** (headless Chromium over CDP): one or more per Unit.
- **A real-engine performance check** for NFR1 (`tests/test_engine_real.py`), plus a 20-reply in-stage sample.

The test strategy is Standard, so no separate performance or security instruction files are generated. The security checks (no tokens in logs, rate limits, origin checks, validation of input and files) live in the integration suites.

## Coverage expectations
The refactor scope has no line-coverage floor. Each component has 5 to 8 tests (Standard), and the existing suite must stay green.

| Unit | Python tests | JS tests |
|---|---|---|
| U1 game screen polish | 7 browser | 29 |
| U2 data and your games | 88 | 15 |
| U3 pass-along | 73 | 19 |
| U4 play the computer | 64 | 14 |
| U5 lessons and puzzles | 65 | 30 |
| U6 endgame trainer | 56 | 11 |

The unit commands overlap, so these counts add up to more than the suite total.

## Target Verification Matrix

| Target ID | Source | Expected | Actual | Evidence | Owning Stage | Verdict |
|---|---|---|---|---|---|---|
| TC-SUITE-GREEN | every Unit's code-generation-plan.md › Testing Contract › scope_floor | the existing suite stays green | 386 passed, 1 skipped (the pre-existing push end-to-end skip), 0 failed; node 221 passed | test-results.md › Project-wide runs | build-and-test | Met |
| TC-STD-VOLUME | Testing Contract › strategy_volume | 5 to 8 tests per component, unit plus integration for key boundaries | every new component has at least 5 tests; boundary tests are listed in integration-test-instructions.md | each Unit's code-summary.md; integration-test-instructions.md | build-and-test | Met |
| TC-CI | Testing Contract (refactor scope) | CI before merge | — | aidlc-state.md: ci-pipeline is SKIP | — | N/A (the plan runs no CI Pipeline) |
| NFR1 | requirements.md › NFR1 | one search at a time, 2 threads or fewer, 64 MB hash or less, FIFO, reply 3 s or less at p95 on the Pi | serial queue tested; Threads=2 and Hash=64 configured; p95 1.004 s over 20 Maximum replies | tests/test_engine.py; tests/test_engine_real.py; test-results.md › NFR1 sample | build-and-test | Met |
| NFR2 | requirements.md › NFR2 | capture animation 300 ms or less, honours reduced motion | 260 ms; no animation under reduced motion | tests/test_u1_polish_browser.py (Chromium) | build-and-test | Met |
| NFR3 | requirements.md › NFR3 | board fits above the fold at every FR4.1 size | passes at all 7 sizes | tests/test_u1_polish_browser.py::test_board_fits_the_viewport_at_the_fr41_sizes (Chromium) | build-and-test | Met |
| NFR4 | requirements.md › NFR4 | no tokens in URLs or logs; creator-only answers; 1 pending request and 5 per minute; encoded share links and local QR; validated content files | all asserted | tests/core/test_join_requests_api.py, tests/test_rate_limit.py, tests/js/share.test.mjs, tests/js/qr.test.mjs, tests/test_lessons.py, tests/test_puzzles.py | build-and-test | Met |
| NFR5 | requirements.md › NFR5 | labelled modal with focus trap and Escape; animation never the only signal; 44 px tap targets | all asserted | tests/test_u1_polish_browser.py, tests/test_u4_computer_browser.py (Chromium) | build-and-test | Met |
| NFR6 | requirements.md › NFR6 | puzzle data 5 MB or less; no start-up downloads for trainers | 296 KB; loaded from disk | `du -sh puzzles`; tests/test_puzzles.py | build-and-test | Met |
| NFR7 | requirements.md › NFR7 | an older schema is moved to .old and a fresh v4 created; tests never open the real database | asserted | tests/core/test_db.py; every test uses a temporary database | build-and-test | Met |
| NFR8 | requirements.md › NFR8 | suite green; every FR has an automated test | 386 passed; 45 of 45 FRs traced | test-results.md; cross-unit-traceability.md | build-and-test | Met |

## Readiness
- **Build-ready:** yes.
- **Test-ready:** yes. Every command passed, and every applicable target is Met.
- **Deployment-ready:** ready for the person's own deployment on the Pi. This plan has no deployment stages.

## Known limitations
- **Push delivery end to end** cannot run here, because this Chromium has no push service. The test is skipped, as it was before P2. It needs a manual check on a real device.
- **PostgreSQL support through `DATABASE_URL`**, requested during this work, is noted as a separate piece of work for after this one.
- **Cross-unit traceability tool** lists the NFRs as uncovered, because the Unit designs traced FRs only. Each NFR is verified above and in `cross-unit-traceability.md`.
- **Gameplay tuning:** the computer levels were made easier at your request, and all tuning now lives in `gameplay.yaml`.
