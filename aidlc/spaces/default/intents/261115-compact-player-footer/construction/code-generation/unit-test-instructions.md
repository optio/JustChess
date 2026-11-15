# Compact Footer Test Instructions

## Authorized Vercel Extension Tests

Focused implementation tests are `tests/test_serverless.py` for multi-instance DB locking/events/presence, engine retries and notification outbox relevance/leases/cron auth. Exact new command: `uv run --frozen pytest -q tests/test_serverless.py`. Use disposable postgres:17 via dedicated JUSTCHESS_TEST_DATABASE_URL and temp schemas, never normal Neon URL/.env. Retain Python/Node/browser regressions and prior footer tests. Preview smoke verification is performed later by root, not substituted by local tests. No new numerical coverage floor.

Use existing pytest/real Chromium tooling and Node runner. No added dependencies or numerical coverage threshold. Test-after frontend behavior; baseline full suites before edits.

Exact feature commands:

- `node --test tests/js/player-identity.test.mjs`
- `uv run --frozen pytest -q tests/test_player_identity_browser.py tests/test_accessibility_browser.py`

Cover FR1-FR5/NFR1-NFR2 with client checks and real-browser footer interactions at narrow/desktop widths. Verify saved/edit/empty nickname states, Enter/inline icons/pending/error, copy denied fallback, actual help/regeneration dialogs (no window.confirm stub), focus/Escape/cancel/confirm and old-link invalidation. Preserve cross-device restoration. Browser servers must use temporary SQLite files. No normal DATABASE_URL, .env or production data. No backend changes expected; existing PostgreSQL evidence retained unless new concern requires rerun.

Full regressions in Build and Test: uv run --frozen pytest -q and node --test tests/js/. Explicitly report optional skips and existing warnings. Record screenshots and visual inspection if available; Node DOM tests alone are not browser verification.
