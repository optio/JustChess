## Developer Code Scan Results

### Scan Coverage

- **Analyzed deeply:** justchess/, static/js/, static/css/, static/sw.js, templates/, lessons/, endgames/, app.py, stockfish_install.py, scripts/curate_puzzles.py, gameplay.yaml, pyproject.toml, .env.example, tests/core/test_db.py, tests/core/conftest.py, tests/test_envfile.py.
- **Skimmed/inventoried:** broader tests/ (Python, Node, browser, fake/real engine and opt-in push), README operational/product sections, selected uv.lock records, generated puzzles/, static/demo/, asset metadata and binary asset inventory.
- **Excluded:** .env and secrets; real SQLite files/backups; ignored dependencies, generated outputs and caches; installed engines; .git and AI-DLC framework/workspace as application source.
- Runtime coverage is application-wide. Scope remains partial because broad tests and generated/binary assets were not individually deeply read.

### Packages Found

justchess is a FastAPI modular monolith. static/js is a plain ES-module frontend with pure state/view functions and DOM shells. lessons and endgames provide authored content; puzzles holds generated catalogs. scripts/curate_puzzles.py is offline tooling. tests/core, tests and tests/js cover domain, API, frontend and integrations.

### Build System

uv manages a non-packaged Python >=3.11 project using pyproject.toml and uv.lock. FastAPI serves Jinja2 and static modules without a JavaScript bundler. Node's built-in runner supports JavaScript tests. No build or install was performed.

### APIs Discovered

Room creation/join/continuation, mode and join-request actions, versioned moves, draw/win/rematch, computer controls and room summaries; viewer-specific WebSocket snapshots; engine status; lessons/stateless position moves; puzzle catalog/check/hint; endgame replay/engine defence; web-push subscriptions. Detailed endpoint inventory is in staged api-documentation.md.

### Frameworks & Libraries

FastAPI, Starlette, Pydantic, Uvicorn and Jinja2; python-chess; PyYAML; pywebpush. SQLite stdlib is the sole database driver. No PostgreSQL driver/ORM/DATABASE_URL selection is implemented. Selected locked versions are recorded in technology-stack.md.

### Test Coverage

Database constraints, version/replacement behavior and .env loading were deeply inspected in isolated temporary SQLite fixtures. Other suites were inventoried and test references inspected, including pure JavaScript state/DOM helpers, fake engine, optional browser, real engine and push checks. No tests ran and no coverage percentage or current pass count is asserted.

### Code Quality Indicators

Server-authoritative replay, optimistic versions, transaction boundaries, hashed credentials and safe content/push validation are established patterns. Engine results are revalidated after asynchronous work. Frontend state is separated from effects. No formatter/linter/type-checker/coverage configuration is declared in pyproject.toml. Large API/shell orchestration and synchronous SQL within async handlers remain maintenance and latency considerations.

### Technical Debt Signals

- PostgreSQL touches schema/connection setup, SQL syntax/placeholders, row/cursor behavior, generated IDs and sqlite3 exception catches across API/live/cleanup/push.
- Schema version is 4 in schema_version, correcting the old HANDOVER premise. Local older/unmarked database replacement must not become an external database destruction policy.
- Summary reads require transaction consistency; notification event claims require deduplication.
- app.py resolves configuration at import; direct create_app callers resolve in lifespan. Tests setting JUSTCHESS_DB need isolation from a future DATABASE_URL.
- SQLite DDL uses AUTOINCREMENT, instr/GLOB checks; transactions use BEGIN IMMEDIATE; inserts use lastrowid and INSERT OR IGNORE.
- One-worker coordination persists in locks, live presence, limiter, decline memory and engine scheduling.
- Configured database errors must be sanitized and startup/fallback policy explicit; existing data transfer is an unresolved requirement.

## Handoff Summary

Nine fresh, concise candidate artifacts replace historical stale prose under .aidlc-engine/codekb-stage-JustChess/. The component inventory restores verified runtime/frontend/content coverage while accurately retaining shallow test/generated-asset coverage. scope-draft-JustChess.md mirrors the candidate timestamp.

No application changes, test/build execution, routing or publication occurred. The conductor should compare and publish the checked candidate, then present the required gate. Requirements should resolve external schema/version policy, configured-URL failure behavior and whether SQLite-to-PostgreSQL data transfer is included.

