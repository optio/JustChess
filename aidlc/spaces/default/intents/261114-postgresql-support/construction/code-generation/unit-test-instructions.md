# PostgreSQL Support Test Instructions

Use existing pytest configuration and Node built-in test runner; no added coverage threshold. Methodology: test-after per layer. Verify baseline before application edits with uv run --frozen pytest -q and node --test tests/js/; full regressions are also checked in Build and Test.

Feature-scoped command after test creation: uv run --frozen pytest -q tests/test_postgres.py tests/test_envfile.py

Add tests/test_postgres.py for selection, URL validation/redaction, SQLite retention, schema setup/idempotence/version refusal, transactions/constraints and backend parity. At least one check per FR1-FR5/NFR1-NFR2; existing tests supply unchanged-component happy paths. Use fake connections only for deterministic failure cases; backend parity needs a real dedicated PostgreSQL service.

PostgreSQL integration cases use JUSTCHESS_TEST_DATABASE_URL exclusively, create a uniquely named schema and clean it up, and skip explicitly if the test URL is absent. Never read .env or use the normal DATABASE_URL for tests; explicit temporary db_path overrides ambient configuration in app tests. Tests must not open or migrate real justchess.sqlite3. Use credential sentinel values for redaction tests.

Record actual command results and skips. No numerical coverage floor is imposed by this express contract; every requirement must still be verified. Missing PostgreSQL infrastructure is a reported limit.
