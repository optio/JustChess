# Test Results

## Executed Commands

| Command | Exit | Result |
|---|---|---|
| uv sync --frozen --check | 0 | 81 packages checked; no changes needed |
| env JUSTCHESS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/justchess_test uv run --frozen pytest -q | 0 | 405 passed, 1 skipped, 3 warnings; 185.49 seconds |
| env JUSTCHESS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/justchess_test uv run --frozen pytest -q tests/test_postgres.py tests/test_envfile.py | 0 | 25 passed, 1 warning; 2.61 seconds |
| node --test tests/js/ | 0 | 221 passed, no skips/failures; 0.67 seconds |
| aidlc engine sensor-traceability --stage build-and-test | 0 | pass=true, uncovered=[]; all FR/NFR IDs covered |

The feature-scoped 25 tests are a subset of the full Python suite, not additional unique passing tests. All PostgreSQL cases executed in both relevant commands against PostgreSQL 17. The sole full-suite skip is existing real Web Push E2E, which requires a real provider/device; no PostgreSQL case skipped.

## Environment and Isolation

Disposable postgres:17 container, loopback port 55439, tmpfs data and unique schema per integration case. Started using the documented build instructions and stopped/automatically removed after execution. No normal DATABASE_URL or real SQLite database was used as test input. SQLite app tests use temporary files; ambient DATABASE_URL is suppressed by tests/conftest.py. The independent-writer finding about the real SQLite file from Code Generation remains recorded in HANDOVER.md; no file restoration or investigation into its contents occurred here.

Initial sandbox attempts of uv commands failed before test collection because the uv cache was read-only. Approved elevated reruns above passed. The Docker host emitted an IPv4 forwarding warning, but actual loopback PostgreSQL connections and every integration check passed.

## Findings and Limits

No test failures or uncovered requirement IDs. Existing python-chess event-loop-policy and websockets connect-style deprecation warnings remain. No new performance/load target or numerical coverage threshold was specified. Real PostgreSQL verification was local; remote network latency, production readiness and multi-worker support are not implied.

Schema acceptance is interpreted against the approved implementation plan: SQLite retains its established archive/recreate policy for older formats, and PostgreSQL supports version 4 initialization/idempotence while refusing unsupported versions unchanged. No legacy data migration was added.

## Loop-Back Log

None.
