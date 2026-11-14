# PostgreSQL Support Requirements

## Intent Analysis

Allow the owner to select PostgreSQL by configuring DATABASE_URL while retaining the existing self-contained SQLite setup. This is a cross-cutting persistence change to an existing application, with no intended gameplay or public API changes.

## Sources

- [desc] Initial description: Support PostgreSQL via DATABASE_URL in .env, falling back to the built-in SQLite
- [scope] Workflow-selected scope: express; Minimal depth and test strategy.
- [Q1] No automatic SQLite data transfer; switching selects a separate database.
- [Q2] Create and upgrade PostgreSQL application tables at startup; owner provides database and schema permissions.
- [Q3] Invalid, unsupported or unreachable configured database stops startup with credential-safe errors.
- [code] Approved Reverse Engineering: aidlc/spaces/default/codekb/JustChess/, especially architecture.md, component-inventory.md and code-quality-assessment.md.
- [handover] HANDOVER.md: preserve JUSTCHESS_DB defaults, isolated test databases, one-worker operation, secret handling and existing application behavior.
- [user] Owner requested removing completed handover items to prevent overlapping future sessions.

## Functional Requirements

All requirements below are Must-have.

### FR1 — Select database from configuration

After the existing .env loader runs, a nonempty DATABASE_URL selects PostgreSQL. Accept PostgreSQL connection URLs using postgresql:// or postgres://. Existing process environment precedence over .env is preserved. An unset or empty DATABASE_URL uses the existing JUSTCHESS_DB path or built-in justchess.sqlite3 default. [desc, handover]

Acceptance: given each configuration combination, startup selects the documented backend and location; configuring both DATABASE_URL and JUSTCHESS_DB selects PostgreSQL. Whitespace-only or unsupported nonempty URLs fail under FR4 rather than silently selecting SQLite.

### FR2 — Preserve persistence behavior on both backends

Rooms, seats, join requests, games, move history, game summaries, housekeeping and push delivery state retain their existing behavior on SQLite and PostgreSQL. Preserve transaction atomicity, uniqueness, referential rules, authorization checks and stale-move protection. Backend differences in SQL, placeholders, generated IDs and exceptions must not change public API responses or stored game semantics. [desc, code]

Acceptance: equivalent isolated scenarios on both backends cover room/seat creation and lookup, joining, game creation and moves, summaries, cleanup, and push event/subscription state; rejected or failed writes leave no partial domain state. Existing Python and JavaScript regressions remain green.

### FR3 — Initialize and upgrade schema at startup

Create application tables for an empty selected PostgreSQL database and apply supported schema upgrades at startup. Retain SQLite's existing schema and data upgrade behavior. Track versions using a schema-version table; reject unsupported newer schema versions without downgrading or destroying their data. The owner creates the PostgreSQL database and grants the necessary schema permissions. [Q2, code]

Acceptance: startup on an empty database creates a usable schema; repeated startup preserves existing records; supported legacy SQLite upgrades still work; unsupported schema or missing PostgreSQL permissions prevents startup with a safe diagnostic.

### FR4 — Fail safely for configured PostgreSQL errors

Malformed or unsupported nonempty DATABASE_URL, connection failure, missing dependency, schema failure or permission failure stops startup. Do not fall back to SQLite when PostgreSQL was selected. Diagnostics identify the failure category without exposing the URL, password or other credentials. [Q3]

Acceptance: representative failures stop initialization, create no fallback SQLite database, and expose no test credentials through application logs, exceptions surfaced by the entry point or HTTP responses.

### FR5 — Document configuration and verification

Add the PostgreSQL driver dependency and reproducible lock update; document DATABASE_URL in .env.example, the env-file test's allowed list and README. Explain precedence, SQLite fallback, schema permissions/startup upgrades, independent databases, connection failures, one-worker operation and isolated PostgreSQL test setup. [desc, handover, Q1–Q3]

Acceptance: documented setup starts against an owner-provided PostgreSQL database; the default SQLite instructions continue to work; PostgreSQL integration tests run against an explicitly supplied disposable database and skip with an explicit reason when it is absent. Missing PostgreSQL test infrastructure is reported as a verification limit, not a successful PostgreSQL run.

## Non-Functional Requirements

### NFR1 — Protect secrets and real data

Never include database credentials or bearer seat/request tokens in URLs exposed to players, logs or error bodies. Tests use temporary SQLite databases and an explicitly dedicated disposable PostgreSQL database; they never open or migrate the real justchess.sqlite3. Existing SQLite data is not copied, deleted or modified when selecting PostgreSQL. [handover, Q1, Q3]

Acceptance: credential-sentinel failure checks pass; tests demonstrably select isolated databases even when normal environment configuration exists; backend-switch tests preserve SQLite fixture bytes/records.

### NFR2 — Retain deployment and gameplay constraints

Continue supporting the existing single-worker server, gameplay.yaml configuration and browser/API behavior. PostgreSQL selection does not claim multi-worker safety. Use the project's uv workflow and retain a reproducible frozen dependency installation. [code, handover]

Acceptance: existing regression checks pass; operating instructions retain one worker; uv run --frozen resolves the updated dependencies.

## Constraints

- Use psycopg for PostgreSQL and retain built-in SQLite support.
- Run Python through uv run --frozen after the dependency lock is updated.
- No commit, push or production deployment without the owner's request.
- Keep HANDOVER.md limited to outstanding work and the active checkpoint; remove completed items as they finish. [user]
- Application owns its tables; no server/database provisioning is included.

## Assumptions & Open Questions

None. Implementation choices such as the internal adapter shape and PostgreSQL schema upgrade mechanics are resolved during Code Generation against these acceptance criteria.

## Out of Scope

- SQLite-to-PostgreSQL data transfer or migration tooling. [Q1]
- Multi-worker or multi-instance coordination, distributed sockets/locks and shared rate limits.
- New gameplay features, UI redesign and unrelated optional review follow-ups.
- Automatic PostgreSQL installation, hosting or database creation.

## Verification Mapping

FR1: configuration precedence and selection tests. FR2: backend parity/domain integration tests and existing regressions. FR3: schema startup/version/upgrade tests. FR4: safe startup-failure tests. FR5: environment example/docs checks and PostgreSQL test invocation. NFR1: isolation, retained SQLite data and secret-sentinel checks. NFR2: frozen dependency check and existing regression suites.
