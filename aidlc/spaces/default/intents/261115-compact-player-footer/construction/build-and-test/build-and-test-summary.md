# Build and Test Summary

## Inventory

Sources: current requirements FR1–FR5, NFR1–NFR2, VFR1–VFR6; Code Generation Testing Contract; and stage-level unit-test instructions. Strategy is Minimal, with no numerical coverage floor and no separate performance target. Required outputs include the existing focused client/browser tests, serverless PostgreSQL tests, and the full Python/JavaScript regressions. Vercel Preview behavior and smoke are owned by the later Deployment Execution stage.

## Target Verification Matrix

| Target ID | Source | Expected | Actual | Evidence | Owning Stage | Verdict |
|---|---|---|---|---|---|---|
| FR1 | requirements/FR1 | Compact responsive footer without overflow | 320/375/1280px and dark-theme checks passed | Code Generation screenshots; Chromium in test-results.md | build-and-test | Met |
| FR2 | requirements/FR2 | Nickname display/edit/save/pending/error behavior | Passed, including real-browser transitions | test-results.md | build-and-test | Met |
| FR3 | requirements/FR3 | Clear copy action and usable private-link fallback | Passed, including denied clipboard | test-results.md | build-and-test | Met |
| FR4 | requirements/FR4 | Accessible regeneration dialog with safe cancel/confirm | Passed in real Chromium | test-results.md | build-and-test | Met |
| FR5 | requirements/FR5 | Player-link help explains privacy and bookmark behavior | Passed in real Chromium | test-results.md | build-and-test | Met |
| NFR1 | requirements/NFR1 | Accessibility and existing behavior regressions | Browser and JS suites passed | test-results.md | build-and-test | Met |
| NFR2 | requirements/NFR2 | Portable checkpoint for another AI tool | Handover updated at this stage | HANDOVER.md | build-and-test | Met |
| VFR1-LOCAL | requirements/VFR1 | Vercel-safe config, no local env fallback, ephemeral engine path and pinned installer | Isolated tests and installer tests passed | tests/test_serverless.py; tests/test_stockfish_install.py; test-results.md | build-and-test | Met |
| VFR1-PREVIEW | requirements/VFR1 | Actual Vercel FastAPI startup, Stockfish download/execution and bundled assets | Not run yet; Preview is a later stage | Deployment Execution smoke evidence, pending | deployment-execution | Unverified |
| VFR2 | requirements/VFR2 | PostgreSQL serializes conflicting moves across instances | Passed on disposable PostgreSQL 17 | tests/test_serverless.py; test-results.md | build-and-test | Met |
| VFR3 | requirements/VFR3 | Cross-instance WebSocket events, shared presence and reconnect resync | Passed on disposable PostgreSQL 17 | tests/test_serverless.py; test-results.md | build-and-test | Met |
| VFR4 | requirements/VFR4 | Bounded engine work, stale-result rejection, retry after abandoned lease | Passed in serverless and computer regressions | tests/test_serverless.py; test-results.md | build-and-test | Met |
| VFR5 | requirements/VFR5 | Durable targeted push retry, relevance/coalescing, safe global maintenance | Passed with isolated database/fake push transport | tests/test_serverless.py; tests/test_push_api.py; test-results.md | build-and-test | Met |
| VFR6-BRANCH | requirements/VFR6 | Vercel production branch set to `production` while retaining repository link | Remote setting verified | HANDOVER.md deployment record | build-and-test | Met |
| VFR6-PREVIEW | requirements/VFR6 | Deploy and smoke a Preview without deploying Production | Not run yet; Preview deployment is a later stage | Deployment Execution URL and smoke results, pending | deployment-execution | Unverified |
| TC-REQ | plan/Testing Contract | Requirement-driven checks and regressions remain green | All executed suites passed | test-results.md | build-and-test | Met |

## Readiness

The frozen dependency check, full JavaScript suite, focused real-browser checks, serverless/PostgreSQL tests and complete recorded Python regression are green. Code and test readiness are supported by the evidence below. Overall stage readiness remains **incomplete** because the two explicitly deployment-owned Preview targets are Unverified until a Preview exists. No production deployment is claimed.
