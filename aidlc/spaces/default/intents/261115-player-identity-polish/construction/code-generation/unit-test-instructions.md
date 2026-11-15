# Player Identity Test Instructions

Use existing pytest, Node test runner and repository browser tooling. No new numerical coverage threshold. Methodology is test-after per layer; baseline before app edits.

Feature commands after files exist:

- `uv run --frozen pytest -q tests/test_players.py tests/test_player_api.py`
- `node --test tests/js/player-identity.test.mjs`
- `uv run --frozen pytest -q tests/test_player_identity_browser.py`
- `env JUSTCHESS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/justchess_test uv run --frozen pytest -q tests/test_postgres.py tests/test_players.py tests/test_player_api.py`

Adjust these exact feature file names if implementation follows an existing test convention and record the final commands here. Cover FR1-FR7/NFR1-NFR2, happy paths per new component plus invalid credentials, revocation, unauthorized seat access and invalid nicknames. Existing regression suites remain green.

Use tmp_path SQLite databases and JUSTCHESS_TEST_DATABASE_URL-only isolated PostgreSQL schemas. No normal DATABASE_URL or real app files. Reuse available postgres:17 disposable image if needed, localhost-only tmpfs and clean teardown. Use sentinel credentials and validate no logs/URLs/errors leak them. Two independent browser contexts simulate devices. Use available real browser tooling to inspect rendered growth/confetti and reduced-motion behavior; Node/DOM-only checks do not establish real browser success. Do not install unplanned tooling; report unavailable checks.

Build and Test runs full suites; feature tests do not weaken existing thresholds or represent skipped optional cases as passed.
