# Code Quality Assessment

## Verified strengths

Server-authoritative legal moves and replayed histories preserve repetition and outcomes. Version checks, short explicit transactions and per-room locks protect local mutation ordering. Tokens are hashed at rest and omitted from invitation links/logging. Origin/body controls, push destination checks and safe content loaders constrain input. Engine results are revalidated after asynchronous computation. Frontend pure reducers and injected clocks/network/storage support isolated tests.

## Current risks and intent implications

SQLite is coupled through DDL (AUTOINCREMENT, instr, GLOB), question-mark parameters, sqlite3.Row, lastrowid, INSERT OR IGNORE, explicit BEGIN IMMEDIATE and sqlite3 exception catches. Room summaries explicitly begin/roll back a consistent read transaction. Preserve row access, generated identifiers, constraint errors, deduplication and transaction behavior when introducing PostgreSQL.

Schema version is 4 in schema_version. Local startup preserves version 4, refuses newer versions, and renames/replaces older, unmarked or invalid SQLite files; this file policy must not be applied to an external database. Configured connection failures need sanitized errors and an explicit fallback policy. app.py resolves a DB path at import while factory callers resolve in lifespan. Test fixtures currently set JUSTCHESS_DB without clearing DATABASE_URL.

One worker remains required. Synchronous DB operations may block async requests; a remote database adds latency. api.py and the frontend shell have substantial orchestration responsibilities. Push event claims intentionally have no retry after a crash. In-memory rate/decline records reset on restart. These are observed limits, not changes made here.

## Verification boundary

The runtime, frontend, content loaders, authored lesson/endgame content and configuration were deeply read. Database/environment regression files were deeply read; remaining Python/Node/browser tests were inventoried and selected test names inspected. Tests include temporary SQLite fixtures, fake UCI, optional real-engine/browser/push checks. SQLite introspection/IntegrityError assertions should remain backend-specific. No test, build, live database, coverage measurement or security audit ran. README historical pass counts are not current verification. No committed deployment automation was discovered in the root inventory.

