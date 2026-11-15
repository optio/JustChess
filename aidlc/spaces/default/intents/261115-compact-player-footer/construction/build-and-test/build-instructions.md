# Build Instructions

## Prerequisites and Environment

- Python dependencies are locked in `uv.lock`; Node is used only for the existing JavaScript test runner and Chromium browser tests.
- Check the frozen environment with `uv sync --frozen --check`. No compilation or bundle step is configured.
- Frontend/browser tests use temporary SQLite files. PostgreSQL tests require a disposable PostgreSQL 17 service and `JUSTCHESS_TEST_DATABASE_URL` pointing to a dedicated test database; never source `.env` or use the Neon `DATABASE_URL`.
- No numerical coverage threshold or separate performance target applies to this Minimal strategy.

## Test Commands

- Footer client: `node --test tests/js/player-identity.test.mjs`
- Required browser behavior: `uv run --frozen pytest -q tests/test_player_identity_browser.py tests/test_accessibility_browser.py`
- JavaScript regression: `node --test tests/js/`
- Serverless/PostgreSQL extension: `uv run --frozen pytest -q tests/test_serverless.py` with the isolated PostgreSQL test URL above.
- Full regression: `uv run --frozen pytest -q`; if the runner is externally terminated, use the complete disjoint batches and exact commands recorded in `../code-generation/code-summary.md`.

## Verification

Confirm each command exits zero, record optional environment-dependent skips and existing warnings, and record the test database/service used. Actual Vercel startup, ephemeral Stockfish download/execution, production-like WebSockets and Preview smoke are owned by Deployment Execution and must be reported there; local tests do not establish those runtime facts.
