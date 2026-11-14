# Build Instructions

Run from the repository root with Python 3.11+ and uv. Node is required for JavaScript regression tests. The app has no compile/bundle stage.

1. For installation, use uv sync --frozen. Verify without changing the environment using `uv sync --frozen --check`.
2. For isolated PostgreSQL verification using the already available image: `docker run --rm -d --name justchess-postgresql-verification -p 127.0.0.1:55439:5432 --tmpfs /var/lib/postgresql/data -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=justchess_test postgres:17`.
3. Run `env JUSTCHESS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/justchess_test uv run --frozen pytest -q`.
4. Run the feature command from Code Generation instructions: `env JUSTCHESS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/justchess_test uv run --frozen pytest -q tests/test_postgres.py tests/test_envfile.py`.
5. Run `node --test tests/js/`.
6. Stop/remove the disposable service using `docker stop justchess-postgresql-verification`.

The PostgreSQL URL is a disposable localhost test service; never substitute the normal DATABASE_URL. Test fixtures allocate and drop a unique schema per PostgreSQL case and use temporary SQLite files. Tests suppress ambient DATABASE_URL. Do not open or migrate the real SQLite file. No production service is started or restarted here.

If uv cannot write its cache under the workspace sandbox, use the approved elevated run; this is a tooling permission failure, not a test failure. If PostgreSQL is unavailable, report the failure rather than treating skipped PostgreSQL cases as verified. A Docker forwarding warning may be harmless for loopback access; judge the actual connection/test result.
