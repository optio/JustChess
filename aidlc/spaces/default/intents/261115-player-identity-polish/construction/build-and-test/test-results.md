# Test Results

## Executed Commands

| Command | Exit | Result |
|---|---|---|
| uv sync --frozen --check | 0 | 81 packages, no changes needed |
| uv run --frozen pytest -q tests/test_players.py tests/test_player_api.py | 0 | 20 passed, 3.22s |
| node --test tests/js/player-identity.test.mjs | 0 | 3 passed |
| uv run --frozen pytest -q tests/test_player_identity_browser.py | 0 | 3 real Chromium scenarios passed, 20.79s |
| env JUSTCHESS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/justchess_test uv run --frozen pytest -q tests/test_postgres.py tests/test_players.py tests/test_player_api.py | 0 | 40 passed, 8.68s |
| env JUSTCHESS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/justchess_test uv run --frozen pytest -q | 0 | 429 passed, 1 skipped, 3 warnings, 211.49s |
| node --test tests/js/ | 0 | 224 passed, 1.39s |
| aidlc engine sensor-traceability --stage build-and-test | 0 | pass=true, uncovered=[]; all nine requirement IDs covered |

Targeted runs are subsets of the full suites and are not added to unique-test totals. All distinct Code Generation instruction commands were run once; full regression commands ran once in this stage. PostgreSQL cases ran against real PostgreSQL 17 with no PostgreSQL skip. The sole full-suite skip is existing external Web Push E2E.

## Coverage and Findings

Real Chromium checks cover two-context identity recovery preserving the original device, nickname persistence, replaced bookmark rejection, measured selection scale/deselection, named winner/loser copy, finite winner-only confetti, reopened results and reduced-motion suppression. Existing full-suite browser/accessibility tests also passed. Model/API tests cover hashed capabilities, identity-to-seat authority, retention of sessions after recovery regeneration, invalid requests, origin/body/rate guards, English moderation including simple obfuscations and innocent substrings. PostgreSQL tests exercise the schema and identity/domain behavior with temporary schemas. Node verifies fragment/body-only secret transport and identity replacement.

No failing commands or uncovered requirements. Existing python-chess event-loop-policy and websockets connection-style deprecation warnings remain. No numerical coverage floor or additional latency/load SLO was specified. English filtering is a bounded local vocabulary, not comprehensive moderation. Regeneration revokes recovery only, not existing device sessions. Unsupported PostgreSQL schemas require an empty/recreated app database; no normal database reset occurred in verification.

## Environment and Cleanup

Used the existing postgres:17 image with loopback port 55439, tmpfs data and uniquely named schemas. Browser servers and SQLite tests use temporary databases. Normal DATABASE_URL and .env are not test inputs. Docker reported a forwarding warning; actual loopback integration connections and tests passed. Disposable PostgreSQL was stopped and automatically removed after successful tests. No production deployment, service restart, commit or push occurred.

## Loop-Back Log

None.
