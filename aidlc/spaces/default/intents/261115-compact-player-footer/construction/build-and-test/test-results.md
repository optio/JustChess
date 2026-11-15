# Test Results

## Commands run during this Build and Test stage

| Command | Exit | Result |
|---|---:|---|
| `uv sync --frozen --check` | 0 | 81 locked packages checked; no changes needed |
| `node --test tests/js/` | 0 | 226 passed, 0 failed, 0 skipped (0.54s) |
| `uv run --frozen pytest -q tests/test_player_identity_browser.py tests/test_accessibility_browser.py` | 0 | 7 passed in real Chromium (31.01s); one existing asyncio event-loop deprecation warning |
| `aidlc engine sensor-traceability --stage build-and-test` | 0 | pass=true; all 13 requirement IDs covered, uncovered=[] |

## Full regression and extension evidence from this code state

The authorized Code Generation extension was implemented and regression-tested immediately before this stage. To avoid repeating the previously observed external termination of monolithic pytest runs, the complete 447 unique Python cases were run in disjoint batches; every case is accounted for exactly once except the explicitly listed focused rerun overlap:

| Disjoint batch | Result |
|---|---|
| A — serverless, core, computer, notifications, push API and PostgreSQL | 223 passed (71.55s) |
| B — remaining non-browser files | 163 passed, 1 skipped (46.40s) |
| C — primary gameplay/identity/accessibility Chromium | 17 passed (61.58s) |
| D — U1–U6 Chromium | 13 passed (63.34s) |
| E — engine/NFR/installer | 27 passed (20.44s) |
| Total unique Python cases | **446 passed, 1 skipped** |

Exact batch commands and the dedicated database setup are preserved in `../code-generation/code-summary.md`. `tests/test_serverless.py` has 14 cases; its isolated PostgreSQL focused run passed 13 cases (13.09s), then the final failed-reply cooldown regression passed in a 2-case selection (2 passed, 12 deselected, 2.22s; one overlap). Real PostgreSQL 17 ran in a disposable tmpfs container on localhost port 55439; each test used and dropped only its unique schema. The container was stopped and removed after the run. No Neon or `.env` value was used.

The complete Node suite passed 226 tests in the recorded extension regression. This stage independently reran the same JavaScript suite successfully. Browser interactions were exercised in real Chromium, not only in Node: compact footer, nickname changes, clipboard fallback, help and regeneration dialogs, focus/Escape behavior, accessibility and existing game flows. Credential-masked screenshots at mobile/desktop widths and light/dark themes were visually inspected.

## Skips, warnings, and limits

- One optional real external Web Push E2E case was skipped because it requires external browser credentials. Fake transport tests cover targeting, retry, expiry and coalescing; closed-tab phone delivery remains manual.
- Python-chess asyncio-policy and websockets legacy deprecation warnings remain.
- Actual Vercel Preview startup, writable Stockfish download/execution, deployed static/training assets, Vercel WebSocket reconnect and Preview smoke have not run. They are explicitly owned by Deployment Execution and remain Unverified, so this stage cannot report complete readiness yet.
- The Vercel Production branch setting is verified as `production`. No Preview or Production deployment has occurred in this stage; no Production deployment is authorized.
- No numerical coverage target applies. No test altered a real Neon schema or used normal application data.

## Final target verification

| Target | Actual | Evidence | Owning stage | Verdict |
|---|---|---|---|---|
| FR1–FR5, NFR1 | Responsive footer, edit/recovery/dialog/accessibility behavior passed in Chromium and JS checks | Commands and screenshots above / Code Generation screenshots | build-and-test | Met |
| NFR2 | Handover records current state and exact next action | HANDOVER.md | build-and-test | Met |
| VFR1 local implementation | Runtime path/env guards, pinned installer and isolated startup behavior passed | tests/test_serverless.py, tests/test_stockfish_install.py | build-and-test | Met |
| VFR1 deployed runtime | Preview startup, Stockfish download/execution and assets not yet exercised | Preview smoke evidence pending | deployment-execution | Unverified |
| VFR2–VFR5 | Multi-instance PostgreSQL locks/events/presence, bounded engine retry and durable targeted push behavior passed | Disjoint batches A/B and focused serverless runs | build-and-test | Met |
| VFR6 production-branch setting | Remote branch reports `production`; GitHub link retained | HANDOVER.md | build-and-test | Met |
| VFR6 Preview | Preview deployment and smoke not yet run | Deployment Execution evidence pending | deployment-execution | Unverified |
| Testing Contract | Frozen dependencies and recorded required regression suites passed | Results above | build-and-test | Met |

## Loop-Back Log

None.
