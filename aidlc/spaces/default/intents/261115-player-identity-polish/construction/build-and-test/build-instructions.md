# Build Instructions

The existing Python/plain-JavaScript app has no compile or bundle stage. Use Python 3.11+, uv, Node and existing Chromium/browser-test tooling. Verify dependencies with `uv sync --frozen --check`; install from lock with `uv sync --frozen` if needed.

For PostgreSQL checks use the existing image: `docker run --rm -d --name justchess-identity-verification -p 127.0.0.1:55439:5432 --tmpfs /var/lib/postgresql/data -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=justchess_test postgres:17`.

Run each distinct command from ../code-generation/unit-test-instructions.md once, then run full regression with `env JUSTCHESS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/justchess_test uv run --frozen pytest -q` and `node --test tests/js/`.

Stop/remove the disposable service with `docker stop justchess-identity-verification`. Never substitute the ordinary DATABASE_URL or open real app databases. Fixtures create isolated schemas and temporary SQLite files; browser servers use temporary databases. Schema 5 may require app database recreation as authorized, but verification does not perform that on normal data. PostgreSQL fixtures manage only their own temporary schemas.

Troubleshooting: uv cache/browser permissions may require the approved elevated test run; missing browser infrastructure is an explicit verification limit. Optional PostgreSQL skips do not establish PostgreSQL success. The Docker forwarding warning is judged against actual loopback connectivity and tests. No service restart, commit/push or deployment occurs here.
