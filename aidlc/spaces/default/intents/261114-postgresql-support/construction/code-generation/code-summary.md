# Code Generation Summary

## Implemented

Optional PostgreSQL persistence now follows DATABASE_URL, accepting postgres:// and postgresql://. Unset/empty URLs keep JUSTCHESS_DB and the built-in SQLite default. Existing .env/process precedence remains. Explicit factory db_path isolates SQLite callers from ambient URLs; app.py injects its URL at startup so normal launches honor configuration.

## Files Created or Modified

- justchess/postgres.py: small psycopg adapter for qmark parameters, named/positional rows, repeatable-read summary snapshots and credential-safe errors compatible with existing service error handlers.
- justchess/db.py: configuration selection, PostgreSQL schema initialization/version refusal and dialect-specific DDL; original SQLite policy retained.
- justchess/api.py and app.py: startup selection and optional URL injection.
- justchess/rooms.py: portable INSERT RETURNING for generated seat/request IDs.
- justchess/notifications.py: portable conflict-targeted alert deduplication.
- pyproject.toml and uv.lock: psycopg[binary] dependency (resolved 3.3.9).
- tests/test_postgres.py: configuration, isolation, redaction, missing-driver, row/SQL adapter and real PostgreSQL schema/domain/API tests.
- tests/conftest.py: empty DATABASE_URL during tests, blocking both ambient config and reintroduction from .env; PostgreSQL tests opt in through their dedicated URL only.
- tests/test_envfile.py: DATABASE_URL allowlist and environment-precedence check.
- .env.example, README.md: PostgreSQL configuration, schema permissions, test setup, failure policy and single-worker requirement.
- HANDOVER.md: removed completed implementation work and retained outstanding verification/gates and unrelated follow-ups, with active intent pointers.
- This directory's traceability.json maps every FR/NFR to existing implementation/test/docs paths; plan completion boxes are ticked.

## Decisions and Limits

The adapter keeps the existing service/domain structure and sqlite3 error hierarchy rather than introducing an ORM or replacing every SQL caller. Driver messages are suppressed at the boundary because they can reveal credentials or stored capability hashes. Failed transactions roll back as a whole; constraints are not recovered statement by statement.

PostgreSQL DDL retains constraints and partial indexes while using identity IDs, double-precision timestamps, position and regex checks. New schema initialization is atomic and serialized by a PostgreSQL advisory transaction lock. Only schema version 4 currently exists for PostgreSQL: older/newer/unversioned occupied schemas are refused unchanged. There is no supported historical PostgreSQL upgrade to apply yet. Existing SQLite older-file archive/recreate behavior remains unchanged; no data-transfer or SQLite migration tool was added.

One worker remains required: room locks, WebSocket fan-out and rate limits remain process-local. Synchronous remote database access can add request latency; multi-worker coordination and async database conversion were outside scope. No production config, database or VAPID keys were read or modified by implementation tools; no commit, push or deployment occurred.

## Local Database Change Investigation

The completion check detected a change to the ignored real justchess.sqlite3 during the build window. Read-only filesystem metadata showed mtime 2026-11-14 22:26:07 UTC, then another change to 22:29:00 UTC after all implementation tests and the disposable PostgreSQL container had finished. During the latter interval this agent ran only read-only metadata/source/process-list checks, with no application invocation. This is evidence of concurrent external activity; the writer was not identified, and historical writes cannot be attributed conclusively from these observations alone.

Test call-path inspection found explicit tmp_path database arguments or fixture-set temporary JUSTCHESS_DB paths throughout the suite. The one existing app.py import test replaces app_module.DB with a temporary path before starting TestClient. The new fixture additionally keeps DATABASE_URL empty to block ambient/.env production selection. No implementation tool directly opened the real database, and its content was not inspected, restored, deleted or otherwise changed during this investigation. The .old file metadata remained unchanged. Do not overwrite either user-owned database based on the completion check.

## Verification

- Before application edits: `uv run --frozen pytest -q` — 386 passed, 1 skipped, 186.30 seconds. `node --test tests/js/` — 221 passed.
- After implementation: `uv run --frozen pytest -q` — 398 passed, 6 skipped, 186.47 seconds. Five optional PostgreSQL cases lacked a dedicated URL in this full run; existing push E2E was the remaining skip. This run collected before the final test-environment and computer-constraint cases were added; those final cases ran in the targeted command below.
- Final PostgreSQL/SQLite schema/configuration suite: `env JUSTCHESS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/justchess_test uv run --frozen pytest -q tests/test_postgres.py tests/core/test_db.py tests/test_envfile.py` — 40 passed, 2.32 seconds. This used an isolated disposable PostgreSQL 17 container from an already installed image, with one fresh schema per integration test. Verified startup/idempotence/version refusal, unversioned rejection, atomic rollback, timestamp precision, room/seat/request IDs, computer seats/captures, pending uniqueness, stale moves, push upsert/deduplication, summaries, cleanup and actual app URL selection.
- Post-change Node suite: 221 passed.
- Implementation-scoped `git diff --check` passed. The whole-workspace check separately reports existing blank-EOF warnings in CodeKB scan documents; those were outside this implementation's ownership and were left unchanged.
- Existing python-chess and websockets deprecation warnings remain. No new coverage floor was introduced or weakened.

The PostgreSQL container used no production connection or credentials, stored data in a container tmpfs, and was stopped/automatically removed after verification. To repeat it with the available image, run `docker run --rm -d --name justchess-postgresql-verification -p 127.0.0.1:55439:5432 --tmpfs /var/lib/postgresql/data -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=justchess_test postgres:17`, run the dedicated test command above, then `docker stop justchess-postgresql-verification`. This is a disposable local verification service; normal database settings are never used for tests.

## Unexecuted Tests

Existing real Web Push end-to-end remains unexecuted because it needs the external service/real-device setup. Every new PostgreSQL case was executed against a real service; none is represented as verified merely from its optional skip.

## Deviations

No application scope deviation. The handover's schema premise was corrected earlier in Reverse Engineering. The plan explicitly preserved the actual SQLite archive/recreate policy instead of inventing legacy data upgrades. Temporary isolated PostgreSQL verification used an existing Docker image because the host's PostgreSQL install includes clients but no server binaries.
